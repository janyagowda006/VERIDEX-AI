import re
import time
import math
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple, Union

from app.schemas.evidence import EvidenceItem, EvidenceType
from app.schemas.verification import (
    VerificationClaim,
    VerificationRequest,
    VerificationResponse
)


@dataclass(frozen=True)
class EvidenceCandidate:
    """
    Candidate numerical or date value extracted from structured evidence.
    """
    evidence_id: str
    value: Union[float, str]
    unit: str  # "currency", "percent", "count", "date", "number"
    source_context: str
    entity: Optional[str] = None
    metric: Optional[str] = None
    evidence_type: str = "FACT"
    sql: Optional[str] = None
    calculation_dict: Optional[Dict[str, Any]] = None


@dataclass
class RawClaim:
    """
    Intermediate extracted claim span.
    """
    claim_text: str
    sentence: str
    normalized_value: Union[float, str]
    unit: str  # "currency", "percent", "count", "date", "number"
    span_start: int
    span_end: int


# =====================================================================
# DETERMINISTIC EXTRACTION PATTERNS
# =====================================================================

# Patterns to skip (Entity IDs, version strings, hashes, alphanumeric codes, metadata counts)
NON_CLAIM_PATTERNS = [
    re.compile(r"\b(?:ORD|CUST|PRD|ITEM|CMP|INV|ACC|USR)[-_]\d+(?:[-_][A-Za-z0-9]+)*\b", re.IGNORECASE),
    re.compile(r"\bev_(?:fact|derived|did|exp|ctrl|region)_[a-zA-Z0-9_]+\b", re.IGNORECASE),
    re.compile(r"\b[A-Za-z]{1,6}[-_]?\d{1,8}\b"),  # e.g., E123, O123, C123, P101, PRD-101
    re.compile(r"\b(?:order|customer|product|item|campaign|evidence|invoice|account|user|seed|hash|commit|turn|step|epoch|batch)\s*(?:id|#|no\.?|num\.?)?\s*[:=]?\s*\d+\b", re.IGNORECASE),
    re.compile(r"\b(?:v|version)\s*\d+(?:\.\d+)*\b", re.IGNORECASE),
    re.compile(r"\bpython\s*\d+\.\d+\b", re.IGNORECASE),
    re.compile(r"\bsha-?256:?\s*[a-fA-F0-9]+\b", re.IGNORECASE),
    re.compile(r"\bturn_\d+\b", re.IGNORECASE),
    re.compile(r"\bstep_\d+\b", re.IGNORECASE),
]

# Date Pattern: YYYY-MM-DD
DATE_ISO_PATTERN = re.compile(r"\b(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b")

# Month name dates: e.g. July 1, 2025 or 15 August 2025
MONTH_NAMES = "January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
DATE_TEXT_PATTERN = re.compile(rf"\b(?:({MONTH_NAMES})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})|(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTH_NAMES}),?\s+(\d{{4}}))\b", re.IGNORECASE)

# Percentage Range: e.g. 15–18%, 15 - 18%, 15% to 18%
PERCENTAGE_RANGE_PATTERN = re.compile(
    r"([+-]?\d+(?:,\d{3})*(?:\.\d+)?)\s*%?\s*(?:–|—|-|\bto\b)\s*([+-]?\d+(?:,\d{3})*(?:\.\d+)?)\s*%",
    re.IGNORECASE
)

# Percentage: [+-]?digits(,\d{3})*(.\d+)?%
PERCENTAGE_PATTERN = re.compile(r"([+-]?\d+(?:,\d{3})*(?:\.\d+)?)\s*%", re.IGNORECASE)

# Currency with Lakh / Crore / K / M / B notation
# e.g. ₹48.2 lakh, 48.2L, ₹2.4 crore, 2.4Cr, ₹4.82M, ₹48,200, $1,250, -₹1,250
CURRENCY_PREFIX_PATTERN = re.compile(
    r"([+-]?)\s*(?:₹|Rs\.?|INR|\$)\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(lakhs?|l|crores?|cr|m|millions?|b|billions?|k)?\b",
    re.IGNORECASE
)
CURRENCY_POSTFIX_LAKH_CRORE = re.compile(
    r"\b([+-]?\d+(?:,\d{3})*(?:\.\d+)?)\s*(lakhs?|l|crores?|cr|m|millions?|b|billions?)\b",
    re.IGNORECASE
)

# Counts: e.g. 31 customers, 7 orders, 16 units
COUNT_PATTERN = re.compile(
    r"(?<!\w)([+-]?\d+(?:,\d{3})*)\s+(customers?|orders?|items?|products?|users?|accounts?|records?|units?|drivers?|regions?|categories?|segments?)\b",
    re.IGNORECASE
)

# Plain Decimals or Integers: e.g. 1250.50, 1250, -600
PLAIN_NUMBER_PATTERN = re.compile(r"(?<!\w)([+-]?\d+(?:,\d{3})*(?:\.\d+)?)\b")


def parse_clean_float(raw_str: str) -> float:
    """Parses a cleaned numerical string removing formatting commas."""
    return float(raw_str.replace(",", "").strip())


def is_percent_semantic(name: str, formula: str = "", desc: str = "") -> bool:
    """Returns True if the identifier or formula represents a percentage/share."""
    nl = name.lower()
    fl = formula.lower()
    dl = desc.lower()
    return (
        any(w in nl for w in ("percent", "pct", "share", "rate", "margin"))
        or "* 100" in fl
        or "%" in dl
    )



def is_currency_semantic(name: str) -> bool:
    """Returns True if the identifier represents a financial/currency value."""
    nl = name.lower()
    return any(w in nl for w in (
        "revenue", "rev", "delta", "change", "did", "total", "amount",
        "price", "cost", "discount", "margin", "baseline", "diff",
        "spend", "sales", "gmv", "val"
    ))


def is_count_semantic(name: str) -> bool:
    """Returns True if the identifier represents a discrete count or sample size."""
    nl = name.lower()
    if nl in ("n", "n_exposed", "n_control", "sample_size", "sample_count"):
        return True
    if nl.startswith("n_") or nl.endswith("_n"):
        return True
    return any(w in nl for w in (
        "count", "customers", "orders", "quantity", "qty",
        "units", "items", "accounts", "users", "records", "drivers"
    ))


def split_sentences(text: str) -> List[str]:
    """
    Splits text into sentences deterministically without breaking decimal points or abbreviations.
    """
    # Normalize line breaks
    cleaned = text.strip()
    if not cleaned:
        return []
    # Split by period followed by whitespace and capital letter/digit, or by double newlines
    raw_sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9₹\$\"'\-])|\n+", cleaned)
    return [s.strip() for s in raw_sentences if s.strip()]


def extract_claims_from_sentence(sentence: str) -> List[RawClaim]:
    """
    Deterministically extracts numerical and date claims from a single sentence.
    Avoids duplicate or overlapping spans and skips false-positive identifiers.
    """
    claims: List[RawClaim] = []
    occupied_spans: List[Tuple[int, int]] = []

    def is_overlapping(start: int, end: int) -> bool:
        return any(not (end <= s or start >= e) for s, e in occupied_spans)

    # 1. Mark non-claim identifiers (IDs, version numbers, hashes) to exclude their spans
    for pattern in NON_CLAIM_PATTERNS:
        for match in pattern.finditer(sentence):
            occupied_spans.append((match.start(), match.end()))

    # 2. Extract ISO Dates (YYYY-MM-DD)
    for match in DATE_ISO_PATTERN.finditer(sentence):
        if not is_overlapping(match.start(), match.end()):
            val_str = match.group(0)
            claims.append(RawClaim(
                claim_text=val_str,
                sentence=sentence,
                normalized_value=val_str,
                unit="date",
                span_start=match.start(),
                span_end=match.end()
            ))
            occupied_spans.append((match.start(), match.end()))

    # 3. Extract Named Dates (e.g. July 1, 2025)
    for match in DATE_TEXT_PATTERN.finditer(sentence):
        if not is_overlapping(match.start(), match.end()):
            raw_str = match.group(0)
            try:
                # Normalize to YYYY-MM-DD
                dt = datetime.strptime(re.sub(r"(st|nd|rd|th)", "", raw_str), "%B %d, %Y")
                iso_str = dt.strftime("%Y-%m-%d")
            except Exception:
                iso_str = raw_str
            claims.append(RawClaim(
                claim_text=raw_str,
                sentence=sentence,
                normalized_value=iso_str,
                unit="date",
                span_start=match.start(),
                span_end=match.end()
            ))
            occupied_spans.append((match.start(), match.end()))

    # 3b. Extract Percentage Ranges (e.g. 15–18%, 15% to 18%)
    for match in PERCENTAGE_RANGE_PATTERN.finditer(sentence):
        if not is_overlapping(match.start(), match.end()):
            low_f = parse_clean_float(match.group(1))
            high_f = parse_clean_float(match.group(2))
            if low_f > high_f:
                low_f, high_f = high_f, low_f
            claims.append(RawClaim(
                claim_text=match.group(0),
                sentence=sentence,
                normalized_value=f"{low_f}–{high_f}%",
                unit="percent",
                span_start=match.start(),
                span_end=match.end()
            ))
            occupied_spans.append((match.start(), match.end()))

    # 4. Extract Percentages (e.g. 12.5%, -100%, +60%)
    for match in PERCENTAGE_PATTERN.finditer(sentence):
        if not is_overlapping(match.start(), match.end()):
            raw_val_str = match.group(1)
            pct_val = parse_clean_float(raw_val_str)
            claims.append(RawClaim(
                claim_text=match.group(0),
                sentence=sentence,
                normalized_value=pct_val,
                unit="percent",
                span_start=match.start(),
                span_end=match.end()
            ))
            occupied_spans.append((match.start(), match.end()))

    # 5. Extract Currency with Prefix (e.g. ₹48.2 lakh, $1,250, -₹1,250, ₹4.82M)
    for match in CURRENCY_PREFIX_PATTERN.finditer(sentence):
        if not is_overlapping(match.start(), match.end()):
            sign = -1.0 if match.group(1) == "-" else 1.0
            num = parse_clean_float(match.group(2))
            multiplier_word = (match.group(3) or "").lower()

            multiplier = 1.0
            if multiplier_word in ("lakh", "lakhs", "l"):
                multiplier = 100000.0
            elif multiplier_word in ("crore", "crores", "cr"):
                multiplier = 10000000.0
            elif multiplier_word in ("m", "million", "millions"):
                multiplier = 1000000.0
            elif multiplier_word in ("b", "billion", "billions"):
                multiplier = 1000000000.0
            elif multiplier_word in ("k",):
                multiplier = 1000.0

            final_val = round(sign * num * multiplier, 2)
            raw_text = match.group(0)
            l_strip = len(raw_text) - len(raw_text.lstrip())
            r_strip = len(raw_text) - len(raw_text.rstrip())
            claims.append(RawClaim(
                claim_text=raw_text.strip(),
                sentence=sentence,
                normalized_value=final_val,
                unit="currency",
                span_start=match.start() + l_strip,
                span_end=match.end() - r_strip
            ))
            occupied_spans.append((match.start() + l_strip, match.end() - r_strip))

    # 6. Extract Currency with Postfix Lakh/Crore/M/B (e.g. 48.2 lakh, 4.82M)
    for match in CURRENCY_POSTFIX_LAKH_CRORE.finditer(sentence):
        if not is_overlapping(match.start(), match.end()):
            num = parse_clean_float(match.group(1))
            multiplier_word = match.group(2).lower()
            if multiplier_word in ("lakh", "lakhs", "l"):
                multiplier = 100000.0
            elif multiplier_word in ("crore", "crores", "cr"):
                multiplier = 10000000.0
            elif multiplier_word in ("m", "million", "millions"):
                multiplier = 1000000.0
            elif multiplier_word in ("b", "billion", "billions"):
                multiplier = 1000000000.0
            else:
                multiplier = 1.0

            final_val = round(num * multiplier, 2)
            claims.append(RawClaim(
                claim_text=match.group(0),
                sentence=sentence,
                normalized_value=final_val,
                unit="currency",
                span_start=match.start(),
                span_end=match.end()
            ))
            occupied_spans.append((match.start(), match.end()))

    # 7. Extract Counts (e.g. 31 customers, 7 orders)
    for match in COUNT_PATTERN.finditer(sentence):
        if not is_overlapping(match.start(), match.end()):
            cnt_val = int(parse_clean_float(match.group(1)))
            claims.append(RawClaim(
                claim_text=match.group(0),
                sentence=sentence,
                normalized_value=cnt_val,
                unit="count",
                span_start=match.start(),
                span_end=match.end()
            ))
            occupied_spans.append((match.start(), match.end()))

    # 8. Extract Plain Numbers (Integers & Decimals)
    for match in PLAIN_NUMBER_PATTERN.finditer(sentence):
        if not is_overlapping(match.start(), match.end()):
            raw_text = match.group(1)
            try:
                num_val = parse_clean_float(raw_text)
                claims.append(RawClaim(
                    claim_text=raw_text,
                    sentence=sentence,
                    normalized_value=num_val,
                    unit="number",
                    span_start=match.start(),
                    span_end=match.end()
                ))
                occupied_spans.append((match.start(), match.end()))
            except ValueError:
                pass

    # Sort claims by appearance in sentence
    claims.sort(key=lambda c: c.span_start)
    return claims


# =====================================================================
# CANDIDATE EVIDENCE EXTRACTION & METRIC/ENTITY HELPERS
# =====================================================================

KNOWN_ENTITIES: List[str] = [
    "karnataka", "tamil nadu", "maharashtra", "delhi", "gujarat", "kerala",
    "andhra pradesh", "telangana", "uttar pradesh", "west bengal",
    "north", "south", "east", "west", "central",
    "electronics", "clothing", "furniture", "food",
    "consumer", "corporate", "home office"
]


def extract_entity_from_text(s: str) -> Optional[str]:
    """Deterministically extracts known geographic or segment entity from text."""
    if not s:
        return None
    sl = s.lower()
    for ent in KNOWN_ENTITIES:
        if re.search(rf"\b{re.escape(ent)}\b", sl):
            return ent
    return None


def extract_metric_from_text(s: str) -> Optional[str]:
    """Deterministically extracts known business metric type from text."""
    if not s:
        return None
    sl = s.lower()
    if any(w in sl for w in ("customer count", "count of customers", "order count", "number of orders", "number of customers", "total customers", "customer sample")):
        return "count"
    if any(w in sl for w in ("revenue", "sales", "spend", "cost", "margin", "gmv", "amount")):
        return "revenue"
    if any(w in sl for w in ("percent", "percentage", "share", "rate")):
        return "percent"
    return None


def extract_candidates_from_evidence(evidence_list: List[EvidenceItem]) -> List[EvidenceCandidate]:
    """
    Extracts structured candidate numerical and date values from EvidenceItem objects.
    
    HARD INVARIANT:
    - EvidenceType.INFERENCE items are strictly skipped; INFERENCE can NEVER be used
      as numerical evidence.
    - Each candidate preserves its entity, metric, formula, and source provenance.
    """
    candidates: List[EvidenceCandidate] = []

    for item in evidence_list:
        # Hard Invariant: INFERENCE is qualitative interpretation and must NEVER be used as numerical evidence
        if item.evidence_type == EvidenceType.INFERENCE or str(item.evidence_type) == "INFERENCE":
            continue

        eid = item.evidence_id
        ev_type_str = item.evidence_type.value if hasattr(item.evidence_type, "value") else str(item.evidence_type)
        item_ent = extract_entity_from_text(item.description or "")

        # 1. Calculation Output & Inputs (DERIVED_FACT evidence)
        if item.calculation:
            calc = item.calculation
            out_val = calc.output
            fname = calc.formula_name or ""
            fexpr = calc.formula or ""
            calc_dict = calc.model_dump() if hasattr(calc, "model_dump") else dict(calc)
            sql_str = item.source.sql if item.source else None

            calc_ent = extract_entity_from_text(str(calc.inputs)) or item_ent
            calc_met = extract_metric_from_text(fname) or extract_metric_from_text(item.description or "")

            if isinstance(out_val, (int, float)):
                out_f = float(out_val)
                # Assign single strict semantic unit (check percent first, then currency, then count)
                if is_percent_semantic(fname, fexpr, item.description or ""):
                    candidates.append(EvidenceCandidate(
                        eid, out_f, "percent", f"calc.output:{fname}",
                        entity=calc_ent, metric=calc_met or "percent",
                        evidence_type=ev_type_str, sql=sql_str, calculation_dict=calc_dict
                    ))
                elif is_currency_semantic(fname):
                    candidates.append(EvidenceCandidate(
                        eid, out_f, "currency", f"calc.output:{fname}",
                        entity=calc_ent, metric=calc_met or "revenue",
                        evidence_type=ev_type_str, sql=sql_str, calculation_dict=calc_dict
                    ))
                elif is_count_semantic(fname):
                    candidates.append(EvidenceCandidate(
                        eid, out_f, "count", f"calc.output:{fname}",
                        entity=calc_ent, metric=calc_met or "count",
                        evidence_type=ev_type_str, sql=sql_str, calculation_dict=calc_dict
                    ))
                else:
                    candidates.append(EvidenceCandidate(
                        eid, out_f, "number", f"calc.output:{fname}",
                        entity=calc_ent, metric=calc_met,
                        evidence_type=ev_type_str, sql=sql_str, calculation_dict=calc_dict
                    ))

            # Scan inputs dict with single strict semantic unit
            if isinstance(calc.inputs, dict):
                for k, v in calc.inputs.items():
                    input_ent = extract_entity_from_text(k) or calc_ent
                    input_met = extract_metric_from_text(k)
                    if isinstance(v, (int, float)):
                        vf = float(v)
                        if is_percent_semantic(k):
                            candidates.append(EvidenceCandidate(
                                eid, vf, "percent", f"calc.inputs.{k}",
                                entity=input_ent, metric=input_met or "percent",
                                evidence_type=ev_type_str, sql=sql_str, calculation_dict=calc_dict
                            ))
                        elif is_currency_semantic(k):
                            candidates.append(EvidenceCandidate(
                                eid, vf, "currency", f"calc.inputs.{k}",
                                entity=input_ent, metric=input_met or "revenue",
                                evidence_type=ev_type_str, sql=sql_str, calculation_dict=calc_dict
                            ))
                        elif is_count_semantic(k):
                            candidates.append(EvidenceCandidate(
                                eid, vf, "count", f"calc.inputs.{k}",
                                entity=input_ent, metric=input_met or "count",
                                evidence_type=ev_type_str, sql=sql_str, calculation_dict=calc_dict
                            ))
                        else:
                            candidates.append(EvidenceCandidate(
                                eid, vf, "number", f"calc.inputs.{k}",
                                entity=input_ent, metric=input_met,
                                evidence_type=ev_type_str, sql=sql_str, calculation_dict=calc_dict
                            ))
                    elif isinstance(v, str) and DATE_ISO_PATTERN.match(v):
                        candidates.append(EvidenceCandidate(
                            eid, v, "date", f"calc.inputs.{k}",
                            entity=input_ent, metric="date",
                            evidence_type=ev_type_str, sql=sql_str, calculation_dict=calc_dict
                        ))

        # 2. Database Source Rows (FACT evidence)
        if item.source and item.source.relevant_rows:
            sql_str = item.source.sql
            for row in item.source.relevant_rows:
                if isinstance(row, dict):
                    row_ent = extract_entity_from_text(str(row)) or item_ent
                    for col, val in row.items():
                        col_met = extract_metric_from_text(col)
                        if isinstance(val, (int, float)):
                            vf = float(val)
                            if is_percent_semantic(col):
                                candidates.append(EvidenceCandidate(
                                    eid, vf, "percent", f"source.row.{col}",
                                    entity=row_ent, metric=col_met or "percent",
                                    evidence_type=ev_type_str, sql=sql_str
                                ))
                            elif is_currency_semantic(col):
                                candidates.append(EvidenceCandidate(
                                    eid, vf, "currency", f"source.row.{col}",
                                    entity=row_ent, metric=col_met or "revenue",
                                    evidence_type=ev_type_str, sql=sql_str
                                ))
                            elif is_count_semantic(col):
                                candidates.append(EvidenceCandidate(
                                    eid, vf, "count", f"source.row.{col}",
                                    entity=row_ent, metric=col_met or "count",
                                    evidence_type=ev_type_str, sql=sql_str
                                ))
                            else:
                                candidates.append(EvidenceCandidate(
                                    eid, vf, "number", f"source.row.{col}",
                                    entity=row_ent, metric=col_met,
                                    evidence_type=ev_type_str, sql=sql_str
                                ))
                        elif isinstance(val, str) and DATE_ISO_PATTERN.match(val):
                            candidates.append(EvidenceCandidate(
                                eid, val, "date", f"source.row.{col}",
                                entity=row_ent, metric="date",
                                evidence_type=ev_type_str, sql=sql_str
                            ))

        # 3. Description Field Extraction
        if item.description:
            desc_claims = extract_claims_from_sentence(item.description)
            for dc in desc_claims:
                if dc.unit in ("currency", "percent", "count", "date"):
                    candidates.append(EvidenceCandidate(
                        eid, dc.normalized_value, dc.unit, "description",
                        entity=item_ent, metric=extract_metric_from_text(item.description),
                        evidence_type=ev_type_str
                    ))

    return candidates


# =====================================================================
# EVIDENCE MATCHING & HARD INVARIANT VERIFICATION
# =====================================================================

def is_compatible_unit(claim_unit: str, candidate_unit: str) -> bool:
    """
    Enforces strict semantic unit compatibility:
    - 'percent' claims ONLY match 'percent' candidates.
    - 'date' claims ONLY match 'date' candidates.
    - 'currency' claims ONLY match 'currency' candidates.
    - 'count' claims ONLY match 'count' candidates.
    - 'number' claims (plain digits in text without currency or count words)
      can match 'currency', 'count', or 'number' candidates.
    """
    if claim_unit == "percent":
        return candidate_unit == "percent"
    if claim_unit == "date":
        return candidate_unit == "date"
    if claim_unit == "currency":
        return candidate_unit == "currency"
    if claim_unit == "count":
        return candidate_unit == "count"
    if claim_unit == "number":
        return candidate_unit in ("number", "currency", "count")
    return False


def check_entity_compatibility(cand_entity: Optional[str], sentence: str, claim_span: Optional[Tuple[int, int]] = None) -> bool:
    """
    Evaluates entity compatibility between evidence candidate and sentence claim.
    Fails if the evidence belongs to entity A (e.g. 'North') but the sentence/clause asserts entity B (e.g. 'South').
    """
    if not cand_entity:
        return True

    cand_entity_lower = cand_entity.lower()
    sentence_lower = sentence.lower()

    # Find all known entities mentioned in sentence
    mentioned_entities = [e for e in KNOWN_ENTITIES if re.search(rf"\b{re.escape(e)}\b", sentence_lower)]
    if not mentioned_entities:
        return True

    # If sentence mentions one or more entities and cand_entity is NOT among them -> Conflict!
    if cand_entity_lower not in mentioned_entities:
        return False

    # If sentence mentions multiple entities (e.g. "North generated ₹4.82M while South generated ₹3.1M"):
    if len(mentioned_entities) > 1 and claim_span:
        c_start, c_end = claim_span
        preceding_text = sentence_lower[:c_start]
        closest_ent = None
        closest_idx = -1
        for e in mentioned_entities:
            idx = preceding_text.rfind(e)
            if idx > closest_idx:
                closest_idx = idx
                closest_ent = e
        if closest_ent and closest_ent != cand_entity_lower:
            return False

    return True


def check_metric_compatibility(
    cand_metric: Optional[str],
    cand_unit: str,
    sentence: str,
    claim_span: Optional[Tuple[int, int]] = None
) -> bool:
    """
    Evaluates metric compatibility for the claim.
    Fails if the claim asserts 'Customer count was ₹48,200' while evidence is revenue, or vice versa.
    Uses local text around claim_span to prevent false positive cross-talk in compound sentences.
    """
    sentence_lower = sentence.lower()
    if claim_span:
        c_start, c_end = claim_span
        preceding = sentence_lower[max(0, c_start - 35):c_start]
        following = sentence_lower[c_end:min(len(sentence_lower), c_end + 25)]
        local_text = preceding + " " + following
    else:
        local_text = sentence_lower

    is_claim_count = any(w in local_text for w in (
        "customer count", "count of customers", "order count", "number of orders",
        "number of customers", "total customers", "customer base", "customers were", "orders were"
    ))
    is_claim_revenue = any(w in local_text for w in (
        "revenue was", "revenue of", "sales of", "sales were", "total revenue", "revenue reached", "net revenue"
    ))

    if is_claim_count and (cand_metric == "revenue" or cand_unit == "currency"):
        return False
    if is_claim_revenue and (cand_metric == "count" or cand_unit == "count"):
        return False

    return True


def check_direction_compatibility(
    cand: EvidenceCandidate,
    sentence: str,
    claim_span: Optional[Tuple[int, int]] = None
) -> bool:
    """
    Evaluates directional assertion compatibility for change/delta metrics.
    Fails if evidence is negative (e.g. -18.3%) but claim asserts an increase/growth,
    or if evidence is positive (e.g. +18.3% change) but claim asserts a decrease/decline.
    """
    try:
        cand_val = float(cand.value)
    except (ValueError, TypeError):
        return True

    # Direction checking only applies when candidate represents a directional change/delta,
    # or candidate value is negative.
    cand_metric = (cand.metric or "").lower()
    source_ctx = (cand.source_context or "").lower()
    is_delta = (
        cand_val < 0
        or any(w in cand_metric for w in ("delta", "change", "did", "growth"))
        or any(w in source_ctx for w in ("delta", "change", "did", "growth"))
    )
    if not is_delta:
        return True

    # Inspect text surrounding the specific claim span (within 40 chars preceding the claim)
    sentence_lower = sentence.lower()
    if claim_span:
        c_start, c_end = claim_span
        preceding = sentence_lower[max(0, c_start - 40):c_start]
        following = sentence_lower[c_end:min(len(sentence_lower), c_end + 30)]
        local_text = preceding + " " + following
    else:
        local_text = sentence_lower

    decline_kws = ("decline", "declined", "declining", "decreas", "fall", "fell", "falling", "drop", "dropped", "dropping", "down", "loss", "reduc")
    increase_kws = ("increas", "growth", "grew", "grow", "gain", "rose", "rise", "rising", "upward", "positive")

    has_decline = any(kw in local_text for kw in decline_kws)
    has_increase = any(kw in local_text for kw in increase_kws)

    # If candidate is negative (e.g. -18.3%), local claim asserting an increase is a HARD CONFLICT!
    if cand_val < 0 and has_increase and not has_decline:
        return False

    # If candidate is a positive delta/growth (e.g. +18.3%), local claim asserting a decrease is a HARD CONFLICT!
    if cand_val > 0 and has_decline and not has_increase:
        return False

    return True


def matches_candidate(
    claim_val: Union[float, str],
    claim_unit: str,
    cand: EvidenceCandidate,
    sentence: str = "",
    claim_span: Optional[Tuple[int, int]] = None,
    tolerance: float = 0.05
) -> bool:
    """
    Evaluates whether an extracted claim matches a candidate evidence value within tolerance.
    Enforces all deterministic hard invariants:
    1. Unit compatibility (percent, currency, count, date, number)
    2. Entity compatibility (North vs South, Karnataka, etc.)
    3. Metric compatibility (revenue vs customer count)
    4. Direction compatibility (increased vs decreased)
    5. Numerical tolerance (absolute comparison with epsilon safeguard)
    """
    cand_val = cand.value
    cand_unit = cand.unit

    if not is_compatible_unit(claim_unit, cand_unit):
        return False

    if not check_entity_compatibility(cand.entity, sentence, claim_span=claim_span):
        return False

    if not check_metric_compatibility(cand.metric, cand.unit, sentence, claim_span=claim_span):
        return False

    # Date match: exact string comparison
    if claim_unit == "date" or cand_unit == "date":
        return str(claim_val).strip() == str(cand_val).strip()

    # Percentage Range match: e.g. "15.0–18.0%"
    if isinstance(claim_val, str) and ("–" in claim_val or "-" in claim_val) and cand_unit == "percent":
        m = re.match(r"([+-]?\d+(?:\.\d+)?)\s*–\s*([+-]?\d+(?:\.\d+)?)", claim_val)
        if m:
            low = float(m.group(1))
            high = float(m.group(2))
            try:
                ef = float(cand_val)
                ef_abs = abs(ef)
                if (low - tolerance - 1e-9) <= ef_abs <= (high + tolerance + 1e-9):
                    return True
                if (low - tolerance - 1e-9) <= ef <= (high + tolerance + 1e-9):
                    return True
            except (ValueError, TypeError):
                pass
        return False

    # Numerical scalar match
    try:
        cf = float(claim_val)
        ef = float(cand_val)
    except (ValueError, TypeError):
        return False

    if not check_direction_compatibility(cand, sentence, claim_span=claim_span):
        return False

    # Direct absolute difference tolerance (with floating-point epsilon safeguard)
    if abs(cf - ef) <= tolerance + 1e-9:
        return True

    # Directional language support for negative deltas / changes:
    # e.g., "Revenue declined by 37.5%" or "Revenue fell by ₹600"
    # where evidence is -37.5% or -600.0.
    if ef < 0 and cf > 0:
        decline_keywords = (
            "decline", "declined", "declining",
            "decreas", "fall", "fell", "falling",
            "drop", "dropped", "dropping",
            "down", "loss", "reduc"
        )
        if any(kw in sentence.lower() for kw in decline_keywords):
            if abs(-cf - ef) <= tolerance + 1e-9:
                return True

    return False


MAX_ALLOWED_TOLERANCE: float = 0.10


def verify_answer(
    llm_text: str,
    evidence_list: List[EvidenceItem],
    tolerance: float = 0.05
) -> VerificationResponse:
    """
    Deterministically verifies all numerical claims in an LLM-generated answer against structured evidence.

    CORE PRINCIPLE:
    'AI for reasoning, code for correctness.'
    The LLM is NOT used to evaluate its own claims. Every numerical claim is parsed,
    unit-normalized, and checked against evidence candidates within an explicit tolerance.

    PASS/FAIL Semantics:
    - If ANY relevant numerical claim is unsupported: status = 'FAIL'.
    - If ALL relevant numerical claims are supported: status = 'PASS'.
    - If zero numerical claims are detected: status = 'PASS' with informational summary.

    Parameters:
    - llm_text: Raw answer text generated by LLM
    - evidence_list: Structured deterministic EvidenceItem list
    - tolerance: Comparison tolerance (default: 0.05, max allowed: 0.10)
    """
    if tolerance < 0.0:
        raise ValueError("Tolerance must be non-negative.")
    if tolerance > MAX_ALLOWED_TOLERANCE:
        raise ValueError(
            f"Tolerance {tolerance} exceeds maximum allowable threshold ({MAX_ALLOWED_TOLERANCE}). "
            "Arbitrary large tolerance is disallowed to prevent bypass of numerical correctness."
        )

    start_time = time.perf_counter()

    evidence_by_id = {item.evidence_id: item for item in evidence_list}

    # 1. Extract candidates from evidence (skipping INFERENCE items)
    candidates = extract_candidates_from_evidence(evidence_list)

    # 2. Split LLM answer into sentences and extract claims
    sentences = split_sentences(llm_text)
    raw_claims: List[RawClaim] = []
    for s in sentences:
        raw_claims.extend(extract_claims_from_sentence(s))

    verified_claims: List[VerificationClaim] = []
    unverified_claims: List[VerificationClaim] = []

    # 3. Match each extracted claim against candidate evidence
    for rc in raw_claims:
        matching_cand_ids: List[str] = []
        matching_contexts: List[str] = []
        primary_candidate: Optional[EvidenceCandidate] = None

        claim_span = (rc.span_start, rc.span_end)

        for cand in candidates:
            if matches_candidate(rc.normalized_value, rc.unit, cand, sentence=rc.sentence, claim_span=claim_span, tolerance=tolerance):
                if cand.evidence_id not in matching_cand_ids:
                    matching_cand_ids.append(cand.evidence_id)
                    matching_contexts.append(f"{cand.evidence_id} ({cand.value} {cand.unit})")
                    if primary_candidate is None:
                        primary_candidate = cand

        if matching_cand_ids and primary_candidate:
            primary_ev = evidence_by_id.get(matching_cand_ids[0])
            ev_type = primary_ev.evidence_type.value if primary_ev else primary_candidate.evidence_type
            src = "SQL" if (primary_ev and primary_ev.source) else ("calculation" if (primary_ev and primary_ev.calculation) else "DERIVED_FACT")
            sql_query = primary_ev.source.sql if (primary_ev and primary_ev.source) else primary_candidate.sql
            calc_dict = primary_ev.calculation.model_dump() if (primary_ev and primary_ev.calculation) else primary_candidate.calculation_dict

            verified_claims.append(VerificationClaim(
                claim_text=rc.claim_text,
                sentence=rc.sentence,
                normalized_value=rc.normalized_value,
                unit=rc.unit,
                status="VERIFIED",
                matching_evidence_ids=matching_cand_ids,
                reason=f"Matched evidence: {', '.join(matching_contexts)}",
                verified=True,
                evidence_type=ev_type,
                source=src,
                query=sql_query,
                calculation=calc_dict,
                text=rc.sentence,
                claim=rc.claim_text,
                evidence_ids=matching_cand_ids
            ))
        else:
            unverified_claims.append(VerificationClaim(
                claim_text=rc.claim_text,
                sentence=rc.sentence,
                normalized_value=rc.normalized_value,
                unit=rc.unit,
                status="UNVERIFIED",
                matching_evidence_ids=[],
                reason=f"No compatible evidence found for {rc.normalized_value} ({rc.unit}).",
                verified=False,
                evidence_type=None,
                source=None,
                query=None,
                calculation=None,
                text=rc.sentence,
                claim=rc.claim_text,
                evidence_ids=[]
            ))

    total_claims = len(raw_claims)
    verified_count = len(verified_claims)
    unverified_count = len(unverified_claims)

    # Determine overall status
    if unverified_count > 0:
        overall_status = "FAIL"
        summary = f"Verification FAILED: {unverified_count} of {total_claims} numerical claim(s) unsupported by evidence."
    elif total_claims == 0:
        overall_status = "PASS"
        summary = "Verification PASSED: No relevant numerical claims detected in text."
    else:
        overall_status = "PASS"
        summary = f"Verification PASSED: All {verified_count} numerical claim(s) verified against evidence."

    execution_time_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    return VerificationResponse(
        status=overall_status,
        verified=verified_claims,
        unverified=unverified_claims,
        total_claims=total_claims,
        verified_count=verified_count,
        unverified_count=unverified_count,
        summary=summary,
        disclaimer="Deterministic numerical verification against provided evidence. Qualitative interpretations and non-numerical assertions are not evaluated.",
        execution_metadata={
            "execution_time_ms": execution_time_ms,
            "tolerance": tolerance,
            "total_sentences_evaluated": len(sentences),
            "evidence_candidates_evaluated": len(candidates)
        }
    )


# =====================================================================
# OPTIONAL REGENERATION HELPER
# =====================================================================

def prepare_regeneration_prompt(verification: VerificationResponse) -> Optional[str]:
    """
    Deterministic helper for at most ONE retry attempt if verification failed.
    Adheres strictly to the rule:
    - maximum exactly ONE retry.
    - never loop indefinitely.
    - retry instruction must be exactly: 'use only numbers from the evidence list'.
    """
    if verification.status == "PASS":
        return None
    return "use only numbers from the evidence list"
