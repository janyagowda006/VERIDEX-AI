from typing import List, Dict, Any, Optional
from app.schemas.evidence import EvidenceItem, EvidenceType, DerivedFactCalculation


class EvidenceCalculator:
    """
    Deterministic arithmetic calculation layer for creating DERIVED_FACT evidence.
    Core Principle: "AI for reasoning, code for correctness."
    Handles division-by-zero safely and preserves calculation provenance.
    """

    def __init__(self):
        self._counter = 0

    def generate_evidence_id(self, prefix: str = "ev_derived") -> str:
        self._counter += 1
        return f"{prefix}_{self._counter}"

    def percentage_change(
        self,
        val_a: float,
        val_b: float,
        label_a: str = "Value A",
        label_b: str = "Value B",
        input_evidence_ids: Optional[List[str]] = None
    ) -> EvidenceItem:
        """
        Calculates percentage change from val_b to val_a: ((val_a - val_b) / val_b) * 100
        """
        ev_id = self.generate_evidence_id()
        input_ids = input_evidence_ids or []
        limitations: List[str] = []

        if val_b == 0.0:
            limitations.append("Division by zero: baseline value B is 0. Percentage change is undefined.")
            calc = DerivedFactCalculation(
                formula_name="percentage_change",
                formula=f"(({label_a} - {label_b}) / {label_b}) * 100",
                inputs={label_a: val_a, label_b: val_b},
                output=None,
                input_evidence_ids=input_ids
            )
            return EvidenceItem(
                evidence_id=ev_id,
                evidence_type=EvidenceType.DERIVED_FACT,
                description=f"Percentage change between {label_a} ({val_a}) and {label_b} ({val_b}) is undefined (division by zero).",
                source=None,
                calculation=calc,
                limitations=limitations
            )

        pct = round(((val_a - val_b) / abs(val_b)) * 100, 2)
        direction = "higher" if pct > 0 else "lower" if pct < 0 else "equal to"
        calc = DerivedFactCalculation(
            formula_name="percentage_change",
            formula=f"(({label_a} - {label_b}) / |{label_b}|) * 100",
            inputs={label_a: val_a, label_b: val_b},
            output=pct,
            input_evidence_ids=input_ids
        )
        desc = f"{label_a} ({val_a}) is {abs(pct)}% {direction} than {label_b} ({val_b})."

        return EvidenceItem(
            evidence_id=ev_id,
            evidence_type=EvidenceType.DERIVED_FACT,
            description=desc,
            source=None,
            calculation=calc,
            limitations=limitations
        )

    def difference(
        self,
        val_a: float,
        val_b: float,
        label_a: str = "Value A",
        label_b: str = "Value B",
        input_evidence_ids: Optional[List[str]] = None
    ) -> EvidenceItem:
        """
        Calculates absolute difference: val_a - val_b
        """
        ev_id = self.generate_evidence_id()
        input_ids = input_evidence_ids or []
        diff = round(val_a - val_b, 2)

        calc = DerivedFactCalculation(
            formula_name="difference",
            formula=f"{label_a} - {label_b}",
            inputs={label_a: val_a, label_b: val_b},
            output=diff,
            input_evidence_ids=input_ids
        )
        desc = f"Difference between {label_a} ({val_a}) and {label_b} ({val_b}) is {diff}."

        return EvidenceItem(
            evidence_id=ev_id,
            evidence_type=EvidenceType.DERIVED_FACT,
            description=desc,
            source=None,
            calculation=calc,
            limitations=[]
        )

    def ratio(
        self,
        val_a: float,
        val_b: float,
        label_a: str = "Value A",
        label_b: str = "Value B",
        input_evidence_ids: Optional[List[str]] = None
    ) -> EvidenceItem:
        """
        Calculates ratio: val_a / val_b
        """
        ev_id = self.generate_evidence_id()
        input_ids = input_evidence_ids or []
        limitations: List[str] = []

        if val_b == 0.0:
            limitations.append("Division by zero: denominator is 0. Ratio is undefined.")
            calc = DerivedFactCalculation(
                formula_name="ratio",
                formula=f"{label_a} / {label_b}",
                inputs={label_a: val_a, label_b: val_b},
                output=None,
                input_evidence_ids=input_ids
            )
            return EvidenceItem(
                evidence_id=ev_id,
                evidence_type=EvidenceType.DERIVED_FACT,
                description=f"Ratio of {label_a} ({val_a}) to {label_b} ({val_b}) is undefined (division by zero).",
                source=None,
                calculation=calc,
                limitations=limitations
            )

        res = round(val_a / val_b, 4)
        calc = DerivedFactCalculation(
            formula_name="ratio",
            formula=f"{label_a} / {label_b}",
            inputs={label_a: val_a, label_b: val_b},
            output=res,
            input_evidence_ids=input_ids
        )
        desc = f"Ratio of {label_a} ({val_a}) to {label_b} ({val_b}) is {res}."

        return EvidenceItem(
            evidence_id=ev_id,
            evidence_type=EvidenceType.DERIVED_FACT,
            description=desc,
            source=None,
            calculation=calc,
            limitations=limitations
        )

    def share_of_total(
        self,
        part: float,
        total: float,
        part_label: str = "Part Value",
        total_label: str = "Total Value",
        input_evidence_ids: Optional[List[str]] = None
    ) -> EvidenceItem:
        """
        Calculates percentage share of total: (part / total) * 100
        """
        ev_id = self.generate_evidence_id()
        input_ids = input_evidence_ids or []
        limitations: List[str] = []

        if total == 0.0:
            limitations.append("Division by zero: total value is 0. Share of total is undefined.")
            calc = DerivedFactCalculation(
                formula_name="share_of_total",
                formula=f"({part_label} / {total_label}) * 100",
                inputs={part_label: part, total_label: total},
                output=None,
                input_evidence_ids=input_ids
            )
            return EvidenceItem(
                evidence_id=ev_id,
                evidence_type=EvidenceType.DERIVED_FACT,
                description=f"Share of {part_label} ({part}) out of {total_label} ({total}) is undefined (total is zero).",
                source=None,
                calculation=calc,
                limitations=limitations
            )

        share = round((part / total) * 100, 2)
        calc = DerivedFactCalculation(
            formula_name="share_of_total",
            formula=f"({part_label} / {total_label}) * 100",
            inputs={part_label: part, total_label: total},
            output=share,
            input_evidence_ids=input_ids
        )
        desc = f"{part_label} ({part}) represents {share}% of total {total_label} ({total})."

        return EvidenceItem(
            evidence_id=ev_id,
            evidence_type=EvidenceType.DERIVED_FACT,
            description=desc,
            source=None,
            calculation=calc,
            limitations=limitations
        )
