import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.evidence import EvidenceItem, EvidenceType, EvidenceSource, DerivedFactCalculation
from app.schemas.verification import VerificationResponse, VerificationClaim
from app.services.claim_checker import (
    verify_answer,
    prepare_regeneration_prompt,
    extract_candidates_from_evidence,
    split_sentences
)


# Helper fixture for synthetic structured evidence
@pytest.fixture
def sample_evidence_list():
    return [
        EvidenceItem(
            evidence_id="ev_derived_region_karnataka",
            evidence_type=EvidenceType.DERIVED_FACT,
            description="Decomposition driver 'Karnataka' (region): delta of -600.00 represents 60.00% of total change (-1000.00).",
            calculation=DerivedFactCalculation(
                formula_name="region_contribution_percentage",
                formula="(region_delta / total_delta) * 100",
                inputs={
                    "region_delta": -600.0,
                    "total_delta": -1000.0,
                    "revenue_a": 1000.0,
                    "revenue_b": 400.0,
                    "group_label": "Karnataka"
                },
                output=60.0,
                input_evidence_ids=[]
            ),
            limitations=["Observational evidence."]
        ),
        EvidenceItem(
            evidence_id="ev_derived_exp_before",
            evidence_type=EvidenceType.DERIVED_FACT,
            description="Exposed cohort before-period average revenue: ₹200.00 across 16 customers.",
            calculation=DerivedFactCalculation(
                formula_name="average_revenue_per_customer",
                formula="sum(customer_revenue_before) / N_exposed",
                inputs={
                    "customer_count": 16,
                    "total_revenue": 3200.0,
                    "window": "2025-04-01"
                },
                output=200.0,
                input_evidence_ids=[]
            ),
            limitations=["Observational cohort."]
        ),
        EvidenceItem(
            evidence_id="ev_derived_did",
            evidence_type=EvidenceType.DERIVED_FACT,
            description="Difference-in-Differences estimate: ₹100.00 (SE: 2.5820).",
            calculation=DerivedFactCalculation(
                formula_name="difference_in_differences",
                formula="exposed_change - control_change",
                inputs={
                    "exposed_change": 150.0,
                    "control_change": 50.0,
                    "control_se": 2.5820
                },
                output=100.0,
                input_evidence_ids=[]
            ),
            limitations=["Observational evidence; causation not proven."]
        ),
        EvidenceItem(
            evidence_id="ev_fact_revenue_total",
            evidence_type=EvidenceType.DERIVED_FACT,
            description="Total annual enterprise revenue reached ₹48,20,000 (₹48.2 lakh).",
            calculation=DerivedFactCalculation(
                formula_name="total_revenue",
                formula="sum(net_revenue)",
                inputs={"order_count": 1500},
                output=4820000.0,
                input_evidence_ids=[]
            ),
            limitations=["Net revenue excludes cancelled orders."]
        ),
        EvidenceItem(
            evidence_id="ev_fact_crore_example",
            evidence_type=EvidenceType.DERIVED_FACT,
            description="Total portfolio gross merchandise value was ₹24,000,000 (₹2.4 crore).",
            calculation=DerivedFactCalculation(
                formula_name="total_gmv",
                formula="sum(gross_revenue)",
                inputs={"active_customers": 500},
                output=24000000.0,
                input_evidence_ids=[]
            ),
            limitations=[]
        ),
        EvidenceItem(
            evidence_id="ev_derived_duplicate_val",
            evidence_type=EvidenceType.DERIVED_FACT,
            description="Alternate scenario confirmed baseline revenue was ₹1000.00.",
            calculation=DerivedFactCalculation(
                formula_name="alternate_baseline",
                formula="sum(scenario_revenue)",
                inputs={},
                output=1000.0,
                input_evidence_ids=[]
            ),
            limitations=[]
        )
    ]


# -------------------------------------------------------------
# 1. Exact Numeric Match (Integer & Decimal)
# -------------------------------------------------------------
def test_exact_numeric_match(sample_evidence_list):
    text = "The baseline revenue in Period A was 1000, and later revenue was 400.0."
    res = verify_answer(text, sample_evidence_list)
    assert res.status == "PASS"
    assert res.verified_count == 2
    assert res.unverified_count == 0
    assert any(c.normalized_value == 1000.0 for c in res.verified)
    assert any(c.normalized_value == 400.0 for c in res.verified)


# -------------------------------------------------------------
# 2. Rounded Numeric Match
# -------------------------------------------------------------
def test_rounded_numeric_match(sample_evidence_list):
    # Evidence has control_se: 2.5820. Answer has rounded: 2.58
    text = "The control group standard error was estimated at 2.58."
    res = verify_answer(text, sample_evidence_list, tolerance=0.01)
    assert res.status == "PASS"
    assert res.verified_count == 1
    assert res.verified[0].normalized_value == 2.58


# -------------------------------------------------------------
# 3. Currency Match
# -------------------------------------------------------------
def test_currency_match(sample_evidence_list):
    text = "Average before revenue for exposed accounts was ₹200.00, yielding a DiD of ₹100.00."
    res = verify_answer(text, sample_evidence_list)
    assert res.status == "PASS"
    assert res.verified_count == 2
    assert res.unverified_count == 0
    assert all(c.unit == "currency" for c in res.verified)


# -------------------------------------------------------------
# 4. Percentage Match
# -------------------------------------------------------------
def test_percentage_match(sample_evidence_list):
    text = "Karnataka accounted for 60.0% of the observed regional decline."
    res = verify_answer(text, sample_evidence_list)
    assert res.status == "PASS"
    assert res.verified_count == 1
    assert res.verified[0].unit == "percent"
    assert res.verified[0].normalized_value == 60.0
    assert "ev_derived_region_karnataka" in res.verified[0].matching_evidence_ids


# -------------------------------------------------------------
# 5. Indian Lakh Normalization
# -------------------------------------------------------------
def test_lakh_normalization(sample_evidence_list):
    # Evidence has ₹48,20,000.0
    text = "Total revenue was ₹48.2 lakh across all territories."
    res = verify_answer(text, sample_evidence_list)
    assert res.status == "PASS"
    assert res.verified_count == 1
    assert res.verified[0].normalized_value == 4820000.0
    assert res.verified[0].unit == "currency"
    assert "ev_fact_revenue_total" in res.verified[0].matching_evidence_ids


# -------------------------------------------------------------
# 6. Indian Crore Normalization
# -------------------------------------------------------------
def test_crore_normalization(sample_evidence_list):
    # Evidence has ₹24,000,000.0
    text = "The overall portfolio value reached ₹2.4 crore."
    res = verify_answer(text, sample_evidence_list)
    assert res.status == "PASS"
    assert res.verified_count == 1
    assert res.verified[0].normalized_value == 24000000.0
    assert res.verified[0].unit == "currency"
    assert "ev_fact_crore_example" in res.verified[0].matching_evidence_ids


# -------------------------------------------------------------
# 7. Negative Number Match
# -------------------------------------------------------------
def test_negative_number_match(sample_evidence_list):
    text = "Karnataka experienced a delta of -₹600.00 while total delta was -1000."
    res = verify_answer(text, sample_evidence_list)
    assert res.status == "PASS"
    assert res.verified_count == 2
    assert any(c.normalized_value == -600.0 for c in res.verified)
    assert any(c.normalized_value == -1000.0 for c in res.verified)


# -------------------------------------------------------------
# 8. Wrong-Unit Rejection
# -------------------------------------------------------------
def test_wrong_unit_rejection(sample_evidence_list):
    # 60% exists in evidence as percent. But here the answer claims "60 customers".
    # It must NOT match 60% to 60 customers!
    text = "We acquired 60 customers in Karnataka."
    res = verify_answer(text, sample_evidence_list)
    assert res.status == "FAIL"
    assert res.unverified_count == 1
    assert res.unverified[0].unit == "count"
    assert res.unverified[0].normalized_value == 60


# -------------------------------------------------------------
# 9. Unsupported Number => Overall FAIL
# -------------------------------------------------------------
def test_unsupported_number_fails(sample_evidence_list):
    text = "Revenue grew by ₹99,999.00 unexpectedly."
    res = verify_answer(text, sample_evidence_list)
    assert res.status == "FAIL"
    assert res.verified_count == 0
    assert res.unverified_count == 1
    assert res.unverified[0].normalized_value == 99999.0


# -------------------------------------------------------------
# 10. Mixed Verified and Unverified => Overall FAIL
# -------------------------------------------------------------
def test_mixed_verified_and_unverified(sample_evidence_list):
    # 60.0% is verified; 42% is invented/unsupported
    text = "Karnataka contributed 60% of the decline, but online traffic rose by 42%."
    res = verify_answer(text, sample_evidence_list)
    assert res.status == "FAIL"
    assert res.verified_count == 1
    assert res.unverified_count == 1
    assert res.unverified[0].normalized_value == 42.0
    assert res.verified[0].normalized_value == 60.0


# -------------------------------------------------------------
# 11. Multiple Claims in One Sentence
# -------------------------------------------------------------
def test_multiple_claims_in_one_sentence(sample_evidence_list):
    text = "Exposed customers averaged ₹200.00 while the overall DiD was ₹100.00 across 16 customers."
    res = verify_answer(text, sample_evidence_list)
    assert res.status == "PASS"
    assert res.verified_count == 3
    assert res.unverified_count == 0


# -------------------------------------------------------------
# 12. Multiple Sentences Evaluation
# -------------------------------------------------------------
def test_multiple_sentences_evaluation(sample_evidence_list):
    text = (
        "In Karnataka, the delta was -600.00. "
        "This represented 60% of the total decline. "
        "Baseline revenue was 1000."
    )
    res = verify_answer(text, sample_evidence_list)
    assert res.status == "PASS"
    assert res.verified_count == 3
    assert len(set(c.sentence for c in res.verified)) == 3


# -------------------------------------------------------------
# 13. Duplicate Evidence Values Link Multiple IDs
# -------------------------------------------------------------
def test_duplicate_evidence_values(sample_evidence_list):
    # 1000.0 is present in ev_derived_region_karnataka (revenue_a) AND ev_derived_duplicate_val
    text = "The baseline revenue was 1000.0."
    res = verify_answer(text, sample_evidence_list)
    assert res.status == "PASS"
    claim = res.verified[0]
    assert len(claim.matching_evidence_ids) >= 2
    assert "ev_derived_region_karnataka" in claim.matching_evidence_ids
    assert "ev_derived_duplicate_val" in claim.matching_evidence_ids


# -------------------------------------------------------------
# 14. Date Parsing Does Not Split Into Numbers
# -------------------------------------------------------------
def test_date_parsing_isolation(sample_evidence_list):
    # Date 2025-04-01 is in ev_derived_exp_before inputs
    text = "The measurement period commenced on 2025-04-01 for all cohorts."
    res = verify_answer(text, sample_evidence_list)
    assert res.status == "PASS"
    assert res.verified_count == 1
    assert res.verified[0].unit == "date"
    assert res.verified[0].normalized_value == "2025-04-01"
    # Ensure 2025, 4, 1 were NOT extracted as three distinct numbers
    assert res.total_claims == 1


# -------------------------------------------------------------
# 15. No-Number Answer Returns PASS with Informational Note
# -------------------------------------------------------------
def test_no_number_answer_passes(sample_evidence_list):
    text = "The regional market experienced downward pressure due to seasonal adjustments."
    res = verify_answer(text, sample_evidence_list)
    assert res.status == "PASS"
    assert res.total_claims == 0
    assert res.verified_count == 0
    assert "No relevant numerical claims detected" in res.summary


# -------------------------------------------------------------
# 16. Sentence-Level Output Details
# -------------------------------------------------------------
def test_sentence_level_output(sample_evidence_list):
    text = "Period A revenue was 1000.00."
    res = verify_answer(text, sample_evidence_list)
    assert res.status == "PASS"
    claim = res.verified[0]
    assert claim.sentence == "Period A revenue was 1000.00."
    assert claim.claim_text == "1000.00"
    assert claim.status == "VERIFIED"


# -------------------------------------------------------------
# 17. Evidence IDs Attached to Verified Claims
# -------------------------------------------------------------
def test_evidence_ids_attached(sample_evidence_list):
    text = "The DiD estimate was ₹100.00."
    res = verify_answer(text, sample_evidence_list)
    assert res.status == "PASS"
    assert "ev_derived_did" in res.verified[0].matching_evidence_ids


# -------------------------------------------------------------
# 18. Deterministic Repeated Execution
# -------------------------------------------------------------
def test_repeated_execution_determinism(sample_evidence_list):
    text = "Karnataka had a delta of -600 and a 60% contribution."
    res1 = verify_answer(text, sample_evidence_list)
    res2 = verify_answer(text, sample_evidence_list)
    assert res1.status == res2.status
    assert res1.total_claims == res2.total_claims
    assert [c.normalized_value for c in res1.verified] == [c.normalized_value for c in res2.verified]


# -------------------------------------------------------------
# 19. Malformed / Empty Evidence Handling
# -------------------------------------------------------------
def test_empty_and_malformed_evidence():
    text = "Revenue grew by ₹1,250."
    # Empty evidence list
    res = verify_answer(text, [])
    assert res.status == "FAIL"
    assert res.unverified_count == 1

    # Evidence item with empty calculation and empty description
    empty_item = EvidenceItem(
        evidence_id="ev_empty",
        evidence_type=EvidenceType.DERIVED_FACT,
        description="",
        limitations=[]
    )
    res2 = verify_answer(text, [empty_item])
    assert res2.status == "FAIL"


# -------------------------------------------------------------
# 20. Regeneration Helper (No Infinite Loop & Exact Instruction)
# -------------------------------------------------------------
def test_regeneration_helper(sample_evidence_list):
    text_failed = "Revenue grew by ₹99,999.00."
    res_failed = verify_answer(text_failed, sample_evidence_list)
    assert res_failed.status == "FAIL"

    retry_prompt = prepare_regeneration_prompt(res_failed)
    assert retry_prompt == "use only numbers from the evidence list"

    # When verification passes, prompt is None
    text_passed = "The DiD estimate was ₹100.00."
    res_passed = verify_answer(text_passed, sample_evidence_list)
    assert res_passed.status == "PASS"
    assert prepare_regeneration_prompt(res_passed) is None


# -------------------------------------------------------------
# 21. Non-Claim Identifier Skipping (ORD-0001, E123, v1.0, etc.)
# -------------------------------------------------------------
def test_non_claim_identifiers_not_extracted(sample_evidence_list):
    text = (
        "Order ORD-00001 for customer CUST-0018 was logged in turn_1 under v2.0. "
        "The actual revenue delta was ₹100.00."
    )
    res = verify_answer(text, sample_evidence_list)
    assert res.status == "PASS"
    # Only 100.00 should be extracted; ORD-00001, CUST-0018, turn_1, v2.0 should NOT be claims!
    assert res.total_claims == 1
    assert res.verified[0].normalized_value == 100.0


# -------------------------------------------------------------
# 22. API Endpoint POST /verify and /api/verify
# -------------------------------------------------------------
def test_api_endpoint_verify(sample_evidence_list):
    client = TestClient(app)
    payload = {
        "llm_text": "Karnataka contributed 60% of the decline with a delta of -600.",
        "evidence_list": [item.model_dump() for item in sample_evidence_list],
        "tolerance": 0.05
    }

    # Test /verify
    response = client.post("/verify", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PASS"
    assert data["verified_count"] == 2
    assert data["unverified_count"] == 0

    # Test /api/verify alias
    alias_resp = client.post("/api/verify", json=payload)
    assert alias_resp.status_code == 200
    assert alias_resp.json()["status"] == "PASS"

    # Test failed verification via API
    fail_payload = {
        "llm_text": "Revenue surged by 9999% in North region.",
        "evidence_list": [item.model_dump() for item in sample_evidence_list]
    }
    fail_resp = client.post("/verify", json=fail_payload)
    assert fail_resp.status_code == 200
    fail_data = fail_resp.json()
    assert fail_data["status"] == "FAIL"
    assert fail_data["unverified_count"] == 1


# -------------------------------------------------------------
# 23. Direct Audit Case 1: Percentage vs Raw Number
# -------------------------------------------------------------
def test_audit_case_1_percentage_vs_raw_number():
    # Evidence contains revenue_delta = -600, customer_count = 31, percentage_change = -37.5%
    evidence = [
        EvidenceItem(
            evidence_id="ev_test_decomp",
            evidence_type=EvidenceType.DERIVED_FACT,
            description="Decomposition fact",
            calculation=DerivedFactCalculation(
                formula_name="revenue_decomposition",
                formula="delta / total",
                inputs={
                    "revenue_delta": -600.0,
                    "customer_count": 31,
                    "percentage_change": -37.5
                },
                output=-37.5,
                input_evidence_ids=[]
            )
        )
    ]
    # Answer: "Revenue declined by 31%."
    # 31 exists as a count, but no compatible 31% evidence exists.
    res = verify_answer("Revenue declined by 31%.", evidence)
    assert res.status == "FAIL"
    assert res.unverified_count == 1
    assert res.unverified[0].claim_text == "31%"
    assert res.unverified[0].unit == "percent"


# -------------------------------------------------------------
# 24. Direct Audit Case 2: Currency vs Count
# -------------------------------------------------------------
def test_audit_case_2_currency_vs_count():
    # Evidence contains customer_count = 1250, revenue = ₹48200
    evidence = [
        EvidenceItem(
            evidence_id="ev_test_customers",
            evidence_type=EvidenceType.DERIVED_FACT,
            description="Customer count fact",
            calculation=DerivedFactCalculation(
                formula_name="customer_summary",
                formula="count(customers)",
                inputs={"customer_count": 1250, "revenue": 48200.0},
                output=48200.0,
                input_evidence_ids=[]
            )
        )
    ]
    # Answer: "Revenue was ₹1,250."
    # 1250 is a count, not currency evidence.
    res = verify_answer("Revenue was ₹1,250.", evidence)
    assert res.status == "FAIL"
    assert res.unverified_count == 1
    assert res.unverified[0].unit == "currency"
    assert res.unverified[0].normalized_value == 1250.0


# -------------------------------------------------------------
# 25. Direct Audit Case 3: Count vs Currency
# -------------------------------------------------------------
def test_audit_case_3_count_vs_currency():
    # Evidence contains revenue = ₹1250, customer_count = 31
    evidence = [
        EvidenceItem(
            evidence_id="ev_test_rev",
            evidence_type=EvidenceType.DERIVED_FACT,
            description="Revenue fact",
            calculation=DerivedFactCalculation(
                formula_name="revenue_metric",
                formula="sum(revenue)",
                inputs={"revenue": 1250.0, "customer_count": 31},
                output=1250.0,
                input_evidence_ids=[]
            )
        )
    ]
    # Answer: "There were 1250 customers."
    # 1250 is currency, not customer-count evidence.
    res = verify_answer("There were 1250 customers.", evidence)
    assert res.status == "FAIL"
    assert res.unverified_count == 1
    assert res.unverified[0].unit == "count"
    assert res.unverified[0].normalized_value == 1250


# -------------------------------------------------------------
# 26. Direct Audit Case 4 & 5: Wrong vs Correct Percentage
# -------------------------------------------------------------
def test_audit_case_4_and_5_percentages():
    evidence = [
        EvidenceItem(
            evidence_id="ev_test_pct",
            evidence_type=EvidenceType.DERIVED_FACT,
            description="Percentage change fact",
            calculation=DerivedFactCalculation(
                formula_name="percentage_change",
                formula="((rev_b - rev_a) / rev_a) * 100",
                inputs={"percentage_change": -37.5},
                output=-37.5,
                input_evidence_ids=[]
            )
        )
    ]
    # Case 4: Wrong percentage => FAIL
    res_wrong = verify_answer("Revenue declined by 31.0%.", evidence)
    assert res_wrong.status == "FAIL"
    assert res_wrong.unverified_count == 1
    assert res_wrong.unverified[0].normalized_value == 31.0

    # Case 5: Correct percentage with decline semantics => PASS
    res_correct = verify_answer("Revenue declined by 37.5%.", evidence)
    assert res_correct.status == "PASS"
    assert res_correct.verified_count == 1
    assert res_correct.verified[0].normalized_value == 37.5


# -------------------------------------------------------------
# 27. Direct Audit Case 6: Same Raw Number with Different Semantics
# -------------------------------------------------------------
def test_audit_case_6_same_raw_number_different_semantics():
    # Evidence: revenue = ₹600, count = 600, percentage = 60%
    evidence = [
        EvidenceItem(
            evidence_id="ev_test_multi_semantics",
            evidence_type=EvidenceType.DERIVED_FACT,
            description="Multi semantic evidence with percentage change 60%",
            calculation=DerivedFactCalculation(
                formula_name="percentage_change",
                formula="((rev_b - rev_a) / rev_a) * 100",
                inputs={
                    "revenue": 600.0,
                    "customer_count": 600,
                    "percentage_change": 60.0
                },
                output=60.0,
                input_evidence_ids=[]
            )
        )
    ]
    # Answer: "Revenue was 60."
    # Expected: FAIL (60 does not match ₹600, 600 count, or 60% with wrong unit/value)
    res = verify_answer("Revenue was 60.", evidence)
    assert res.status == "FAIL"
    assert res.unverified_count == 1


# -------------------------------------------------------------
# 28. Direct Audit Case 7, 8, 9: IDs, Hashes, Metadata Excluded
# -------------------------------------------------------------
def test_audit_case_7_8_9_identifiers_not_claims():
    evidence = [
        EvidenceItem(
            evidence_id="ev_test_clean",
            evidence_type=EvidenceType.DERIVED_FACT,
            description="Revenue fact",
            calculation=DerivedFactCalculation(
                formula_name="order_revenue",
                formula="sum()",
                inputs={"revenue": 500.0},
                output=500.0,
                input_evidence_ids=[]
            )
        )
    ]
    # Case 7: Evidence ID E123 must not become claim 123
    res7 = verify_answer("Evidence E123 supports revenue of ₹500.", evidence)
    assert res7.status == "PASS"
    assert res7.total_claims == 1
    assert res7.verified[0].normalized_value == 500.0

    # Case 8: Order O123, Customer C123, Product PRD-101
    res8a = verify_answer("Order O123 generated ₹500.", evidence)
    assert res8a.status == "PASS"
    assert res8a.total_claims == 1
    assert res8a.verified[0].normalized_value == 500.0

    res8b = verify_answer("Customer C123 generated ₹500.", evidence)
    assert res8b.status == "PASS"
    assert res8b.total_claims == 1
    assert res8b.verified[0].normalized_value == 500.0

    res8c = verify_answer("Product PRD-101 generated ₹500.", evidence)
    assert res8c.status == "PASS"
    assert res8c.total_claims == 1
    assert res8c.verified[0].normalized_value == 500.0

    # Case 9: SQL hashes, timestamps, metadata
    res9 = verify_answer(
        "Query sha-256:abc456 executed at 2025-07-01 with seed 42 under python 3.13, yielding ₹500.",
        evidence
    )
    # The only business claim verified against evidence is ₹500
    assert any(c.normalized_value == 500.0 for c in res9.verified)
    # Ensure abc456, 42, 3.13 are NOT extracted as numerical claims
    all_claim_texts = [c.claim_text for c in res9.verified + res9.unverified]
    assert not any(t in ("456", "42", "3.13", "13") for t in all_claim_texts)


# -------------------------------------------------------------
# 29. Direct Audit Case 10: Multiple Values Inside One Evidence Item
# -------------------------------------------------------------
def test_audit_case_10_multiple_values_single_evidence():
    evidence = [
        EvidenceItem(
            evidence_id="ev_multi_single",
            evidence_type=EvidenceType.DERIVED_FACT,
            description="Composite item",
            calculation=DerivedFactCalculation(
                formula_name="composite_calculation",
                formula="delta / total",
                inputs={
                    "revenue": 1000.0,
                    "delta": -200.0,
                    "percentage_change": -16.67,
                    "customer_count": 50
                },
                output=-16.67,
                input_evidence_ids=[]
            )
        )
    ]
    # Matching text: PASS
    text_pass = "Revenue was ₹1000 and declined by 16.67%."
    res_pass = verify_answer(text_pass, evidence)
    assert res_pass.status == "PASS"
    assert res_pass.verified_count == 2
    assert res_pass.unverified_count == 0

    # Swapped / wrong units: FAIL
    text_fail = "Revenue was ₹50 and declined by 1000%."
    res_fail = verify_answer(text_fail, evidence)
    assert res_fail.status == "FAIL"
    assert res_fail.unverified_count == 2


# -------------------------------------------------------------
# 30. Tolerance Strictness & Arbitrary "Close" Value Rejection
# -------------------------------------------------------------
def test_large_value_relative_tolerance_rejection():
    # Evidence is ₹48,200
    evidence = [
        EvidenceItem(
            evidence_id="ev_exact_rev",
            evidence_type=EvidenceType.DERIVED_FACT,
            description="Revenue fact",
            calculation=DerivedFactCalculation(
                formula_name="net_revenue",
                formula="sum(net_revenue)",
                inputs={"revenue": 48200.0},
                output=48200.0,
                input_evidence_ids=[]
            )
        )
    ]
    # Answer: ₹48,300 MUST NOT pass merely because it is "close" (0.2% diff)
    res_close = verify_answer("Revenue was ₹48,300.", evidence)
    assert res_close.status == "FAIL"
    assert res_close.unverified_count == 1

    # Exact match: PASS
    res_exact = verify_answer("Revenue was ₹48,200.", evidence)
    assert res_exact.status == "PASS"


# -------------------------------------------------------------
# 31. Documented Tolerance Range (100.04 passes, 100.5 fails)
# -------------------------------------------------------------
def test_rounding_tolerance_boundary():
    evidence = [
        EvidenceItem(
            evidence_id="ev_round_100",
            evidence_type=EvidenceType.DERIVED_FACT,
            description="Baseline 100",
            calculation=DerivedFactCalculation(
                formula_name="base_val",
                formula="100",
                inputs={"val": 100.0},
                output=100.0,
                input_evidence_ids=[]
            )
        )
    ]
    # 100.04 matches within default tolerance 0.05
    res_04 = verify_answer("The value was 100.04.", evidence, tolerance=0.05)
    assert res_04.status == "PASS"

    # 100.5 must fail outside default tolerance 0.05
    res_50 = verify_answer("The value was 100.5.", evidence, tolerance=0.05)
    assert res_50.status == "FAIL"


# -------------------------------------------------------------
# 32. Tolerance Safety & Boundary Enforcement (Phase 4.E)
# -------------------------------------------------------------
def test_tolerance_safety_and_bounds():
    evidence = [
        EvidenceItem(
            evidence_id="ev_tol_safe",
            evidence_type=EvidenceType.DERIVED_FACT,
            description="Safety test",
            calculation=DerivedFactCalculation(
                formula_name="revenue",
                formula="100",
                inputs={"revenue": 100.0},
                output=100.0,
                input_evidence_ids=[]
            )
        )
    ]

    # Valid tolerances within [0.0, 0.10]
    res_00 = verify_answer("Revenue was ₹100.", evidence, tolerance=0.00)
    assert res_00.status == "PASS"

    res_01 = verify_answer("Revenue was ₹100.01.", evidence, tolerance=0.01)
    assert res_01.status == "PASS"

    res_05 = verify_answer("Revenue was ₹100.05.", evidence, tolerance=0.05)
    assert res_05.status == "PASS"

    res_0501 = verify_answer("Revenue was ₹100.0501.", evidence, tolerance=0.0501)
    assert res_0501.status == "PASS"

    # Dangerously large tolerances MUST be rejected to prevent bypass of correctness
    with pytest.raises(ValueError, match="exceeds maximum allowable threshold"):
        verify_answer("Revenue was ₹200.", evidence, tolerance=1.0)

    with pytest.raises(ValueError, match="exceeds maximum allowable threshold"):
        verify_answer("Revenue was ₹200.", evidence, tolerance=100.0)

    with pytest.raises(ValueError, match="exceeds maximum allowable threshold"):
        verify_answer("Revenue was ₹200.", evidence, tolerance=999999.0)

    with pytest.raises(ValueError, match="non-negative"):
        verify_answer("Revenue was ₹100.", evidence, tolerance=-0.01)

    # API Route rejection of dangerous tolerance
    client = TestClient(app)
    resp = client.post("/verify", json={
        "llm_text": "Revenue was ₹100.",
        "evidence_list": [item.model_dump() for item in evidence],
        "tolerance": 100.0
    })
    # Must reject with 422 Unprocessable Entity
    assert resp.status_code == 422


# -------------------------------------------------------------
# 33. Section 6 Hard Invariants (1 to 10)
# -------------------------------------------------------------
def test_hard_invariants_1_to_10():
    # 1. Wrong entity: Evidence North revenue = ₹48.2 lakh, Answer "South revenue was ₹48.2 lakh." MUST FAIL.
    ev_north = EvidenceItem(
        evidence_id="ev_north_rev",
        evidence_type=EvidenceType.DERIVED_FACT,
        description="North driver revenue: ₹48.2 lakh",
        calculation=DerivedFactCalculation(
            formula_name="region_revenue",
            formula="sum(revenue)",
            inputs={"region": "North"},
            output=4820000.0,
            input_evidence_ids=[]
        )
    )
    res_wrong_entity = verify_answer("South revenue was ₹48.2 lakh.", [ev_north])
    assert res_wrong_entity.status == "FAIL"
    assert res_wrong_entity.unverified_count > 0

    # 2. Wrong metric: Evidence revenue = ₹48,200, Answer "Customer count was ₹48,200." MUST FAIL.
    ev_rev = EvidenceItem(
        evidence_id="ev_rev_48200",
        evidence_type=EvidenceType.DERIVED_FACT,
        description="Total net revenue: ₹48,200",
        calculation=DerivedFactCalculation(
            formula_name="net_revenue",
            formula="sum(quantity * price)",
            inputs={"metric": "revenue"},
            output=48200.0,
            input_evidence_ids=[]
        )
    )
    res_wrong_metric = verify_answer("Customer count was ₹48,200.", [ev_rev])
    assert res_wrong_metric.status == "FAIL"

    # 3. Wrong direction: Evidence revenue decreased 18.3%, Answer "Revenue increased 18.3%." MUST FAIL.
    ev_pct_drop = EvidenceItem(
        evidence_id="ev_drop_18",
        evidence_type=EvidenceType.DERIVED_FACT,
        description="Revenue percentage change: -18.30%",
        calculation=DerivedFactCalculation(
            formula_name="percentage_change",
            formula="(rev_b - rev_a) / rev_a * 100",
            inputs={"revenue_delta": -18.3},
            output=-18.3,
            input_evidence_ids=[]
        )
    )
    res_wrong_dir = verify_answer("Revenue increased 18.3%.", [ev_pct_drop])
    assert res_wrong_dir.status == "FAIL"

    # 4. Unsupported number: Evidence has ₹48,200, Answer has ₹55,000. MUST FAIL.
    res_unsupported = verify_answer("Revenue was ₹55,000.", [ev_rev])
    assert res_unsupported.status == "FAIL"

    # 5. Currency / Count mismatch: Evidence is currency, Answer claims count. MUST FAIL.
    res_curr_cnt = verify_answer("Order count was 48,200 orders.", [ev_rev])
    assert res_curr_cnt.status == "FAIL"

    # 6. Count / Currency mismatch: Evidence is count, Answer claims currency. MUST FAIL.
    ev_cnt = EvidenceItem(
        evidence_id="ev_cust_cnt",
        evidence_type=EvidenceType.FACT,
        description="Total active customers: 125 customers",
        source=EvidenceSource(
            query_hash="hash125",
            sql="SELECT COUNT(*) as count FROM customers",
            timestamp="2025-06-01T00:00:00Z",
            relevant_rows=[{"customer_count": 125}]
        )
    )
    res_cnt_curr = verify_answer("Revenue was ₹125.", [ev_cnt])
    assert res_cnt_curr.status == "FAIL"

    # 7. Percentage / Raw scalar mismatch: Evidence is percentage, Answer claims currency. MUST FAIL.
    res_pct_curr = verify_answer("Revenue was ₹18.3.", [ev_pct_drop])
    assert res_pct_curr.status == "FAIL"

    # 8. Wrong date: Evidence date is 2025-05-31, Answer is 2025-06-01. MUST FAIL.
    ev_date = EvidenceItem(
        evidence_id="ev_date_end",
        evidence_type=EvidenceType.FACT,
        description="Campaign concluded on 2025-05-31.",
        calculation=DerivedFactCalculation(
            formula_name="campaign_end_date",
            formula="end_date",
            inputs={"date": "2025-05-31"},
            output="2025-05-31",
            input_evidence_ids=[]
        )
    )
    res_wrong_date = verify_answer("Campaign ended 2025-06-01.", [ev_date])
    assert res_wrong_date.status == "FAIL"

    # 9. INFERENCE used as numerical evidence: Evidence INFERENCE = "North is the strongest candidate", Answer "North generated ₹4.82M." MUST FAIL.
    ev_inf = EvidenceItem(
        evidence_id="ev_inf_north",
        evidence_type=EvidenceType.INFERENCE,
        description="North is the strongest candidate for future promotional targeting.",
        limitations=["Qualitative interpretation; cannot support numerical facts."]
    )
    res_inf = verify_answer("North generated ₹4.82M.", [ev_inf])
    assert res_inf.status == "FAIL"
    assert len(res_inf.unverified) > 0

    # 10. Fabricated number: Answer introduces numbers out of thin air. MUST FAIL.
    res_fab = verify_answer("Sales reached ₹99,999 with 555 customers.", [ev_rev])
    assert res_fab.status == "FAIL"


# -------------------------------------------------------------
# 34. Section 7 Tolerance Safety: Evidence = ₹48,200, Answer = ₹48,300 MUST FAIL
# -------------------------------------------------------------
def test_tolerance_safety_explicit_boundary():
    ev_48200 = EvidenceItem(
        evidence_id="ev_48200",
        evidence_type=EvidenceType.DERIVED_FACT,
        description="Total net revenue is ₹48,200",
        calculation=DerivedFactCalculation(
            formula_name="revenue",
            formula="sum(rev)",
            inputs={"rev": 48200.0},
            output=48200.0,
            input_evidence_ids=[]
        )
    )
    # MUST FAIL: difference is 100, which exceeds max allowable tolerance (0.10)
    res_diff_100 = verify_answer("Revenue was ₹48,300.", [ev_48200], tolerance=0.05)
    assert res_diff_100.status == "FAIL"

    res_diff_100_tol10 = verify_answer("Revenue was ₹48,300.", [ev_48200], tolerance=0.10)
    assert res_diff_100_tol10.status == "FAIL"

    # Exact boundary within tolerance: 48200.05 with tol=0.05 PASSES
    res_exact_bound = verify_answer("Revenue was ₹48,200.05.", [ev_48200], tolerance=0.05)
    assert res_exact_bound.status == "PASS"

    # Unsafe tolerances (>0.10) rejected
    for unsafe_tol in [0.11, 1.0, 100.0, 999999.0]:
        with pytest.raises(ValueError, match="exceeds maximum allowable threshold"):
            verify_answer("Revenue was ₹48,200.", [ev_48200], tolerance=unsafe_tol)


# -------------------------------------------------------------
# 35. Section 8 Edge Cases A to P
# -------------------------------------------------------------
def test_claim_checker_edge_cases_a_through_p():
    # A. Range: "Revenue decreased by 15–18%." with evidence -18.0%
    ev_pct = EvidenceItem(
        evidence_id="ev_drop_18_pct",
        evidence_type=EvidenceType.DERIVED_FACT,
        description="Decline: -18.00%",
        calculation=DerivedFactCalculation(
            formula_name="percentage_change",
            formula="delta / baseline * 100",
            inputs={"delta": -18.0},
            output=-18.0,
            input_evidence_ids=[]
        )
    )
    res_range = verify_answer("Revenue decreased by 15–18%.", [ev_pct])
    assert res_range.status == "PASS"

    # B. Approximate: "Revenue decreased by approximately 18%."
    res_approx = verify_answer("Revenue decreased by approximately 18%.", [ev_pct])
    assert res_approx.status == "PASS"

    # C. Equivalent currency: ₹48.2 lakh, ₹0.482 crore, ₹4.82M all normalize to 4,820,000.0
    ev_large_rev = EvidenceItem(
        evidence_id="ev_large_rev",
        evidence_type=EvidenceType.DERIVED_FACT,
        description="Revenue: 4,820,000",
        calculation=DerivedFactCalculation(
            formula_name="revenue",
            formula="sum(rev)",
            inputs={"rev": 4820000.0},
            output=4820000.0,
            input_evidence_ids=[]
        )
    )
    assert verify_answer("North generated ₹48.2 lakh.", [ev_large_rev]).status == "PASS"
    assert verify_answer("North generated ₹0.482 crore.", [ev_large_rev]).status == "PASS"
    assert verify_answer("North generated ₹4.82M.", [ev_large_rev]).status == "PASS"

    # D. Multiple claims: "Revenue was ₹4.82M, down 18.0%, across 125 customers."
    ev_cust_125 = EvidenceItem(
        evidence_id="ev_cust_125",
        evidence_type=EvidenceType.FACT,
        description="125 active customers",
        source=EvidenceSource(
            query_hash="h125",
            sql="SELECT count(*) as count FROM customers",
            timestamp="2025-06-01T00:00:00Z",
            relevant_rows=[{"customer_count": 125}]
        )
    )
    res_multi_claims = verify_answer(
        "Revenue was ₹4.82M, down 18.0%, across 125 customers.",
        [ev_large_rev, ev_pct, ev_cust_125]
    )
    assert res_multi_claims.status == "PASS"
    assert res_multi_claims.verified_count == 3

    # E. Multiple entities: "North generated ₹4.82M while South generated ₹3.1M."
    ev_north = EvidenceItem(
        evidence_id="ev_north",
        evidence_type=EvidenceType.DERIVED_FACT,
        description="North region revenue: ₹4.82M",
        calculation=DerivedFactCalculation(
            formula_name="region_revenue",
            formula="sum(rev)",
            inputs={"region": "North"},
            output=4820000.0,
            input_evidence_ids=[]
        )
    )
    ev_south = EvidenceItem(
        evidence_id="ev_south",
        evidence_type=EvidenceType.DERIVED_FACT,
        description="South region revenue: ₹3.1M",
        calculation=DerivedFactCalculation(
            formula_name="region_revenue",
            formula="sum(rev)",
            inputs={"region": "South"},
            output=3100000.0,
            input_evidence_ids=[]
        )
    )
    res_multi_entities = verify_answer(
        "North generated ₹4.82M while South generated ₹3.1M.",
        [ev_north, ev_south]
    )
    assert res_multi_entities.status == "PASS"
    assert res_multi_entities.verified_count == 2

    # If South value is fabricated / wrong, it fails:
    res_multi_entities_wrong = verify_answer(
        "North generated ₹4.82M while South generated ₹9.9M.",
        [ev_north, ev_south]
    )
    assert res_multi_entities_wrong.status == "FAIL"

    # F. Duplicate numbers with different metrics:
    ev_cnt_50 = EvidenceItem(
        evidence_id="ev_cnt_50",
        evidence_type=EvidenceType.FACT,
        description="Customer count is 50",
        source=EvidenceSource(query_hash="h50", sql="SELECT 50", timestamp="2025-06-01T00:00:00Z", relevant_rows=[{"customer_count": 50}])
    )
    ev_rev_50 = EvidenceItem(
        evidence_id="ev_rev_50",
        evidence_type=EvidenceType.DERIVED_FACT,
        description="Revenue delta is ₹50",
        calculation=DerivedFactCalculation(formula_name="revenue_delta", formula="delta", inputs={"delta": 50.0}, output=50.0, input_evidence_ids=[])
    )
    assert verify_answer("Customer count was 50 customers.", [ev_cnt_50, ev_rev_50]).status == "PASS"
    assert verify_answer("Revenue was ₹50.", [ev_cnt_50, ev_rev_50]).status == "PASS"


# -------------------------------------------------------------
# 36. Section 9 Sentence-Level Provenance UI Structure
# -------------------------------------------------------------
def test_sentence_level_provenance_ui_structure():
    ev_fact = EvidenceItem(
        evidence_id="ev_sql_1",
        evidence_type=EvidenceType.FACT,
        description="North revenue fact",
        source=EvidenceSource(
            query_hash="hash_sql",
            sql="SELECT SUM(revenue) FROM orders WHERE region = 'North'",
            timestamp="2025-06-01T00:00:00Z",
            relevant_rows=[{"revenue": 4820000.0}]
        )
    )
    res = verify_answer("North generated ₹4.82M revenue. South generated ₹9.9M.", [ev_fact])
    assert res.status == "FAIL"
    assert res.verified_count == 1
    assert res.unverified_count == 1

    # Verified claim provenance matches UI requirements
    v_claim = res.verified[0]
    assert v_claim.verified is True
    assert v_claim.text == "North generated ₹4.82M revenue."
    assert v_claim.claim == "₹4.82M"
    assert v_claim.evidence_ids == ["ev_sql_1"]
    assert v_claim.evidence_type == "FACT"
    assert v_claim.source == "SQL"
    assert "SELECT SUM(revenue)" in v_claim.query
    assert v_claim.calculation is None

    # Unverified claim provenance
    u_claim = res.unverified[0]
    assert u_claim.verified is False
    assert u_claim.evidence_ids == []
    assert u_claim.evidence_type is None
    assert u_claim.source is None
    assert u_claim.query is None
    assert u_claim.calculation is None


# -------------------------------------------------------------
# 37. Section 10 & 11 Real End-to-End Integration: Driver Decomposition
# -------------------------------------------------------------
# 37. Section 10 & 11 Real End-to-End Integration: Driver Decomposition
# -------------------------------------------------------------
def test_real_e2e_driver_decomposition_claim_verification():
    from datetime import date
    from app.services.driver_decomposition import decompose_change
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models.business_data import Base, Customer, Product, Order, OrderItem

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()

    p = Product(product_id="P1", product_name="Item 1", category="Electronics", unit_price=10.0, cost_per_unit=5.0)
    c_kar = Customer(customer_id="C_KAR", customer_name="Cust Karnataka", region="Karnataka", customer_segment="Consumer", signup_date=date(2024, 1, 1), acquisition_channel="Organic")
    c_oth = Customer(customer_id="C_OTH", customer_name="Cust Other", region="Tamil Nadu", customer_segment="Corporate", signup_date=date(2024, 1, 1), acquisition_channel="Organic")
    session.add_all([p, c_kar, c_oth])
    session.commit()

    # Period A: 2025-01-01 to 2025-01-31
    # Kar: 1000, Other: 1000 -> Total: 2000
    o1 = Order(order_id="O1", customer_id="C_KAR", order_date=date(2025, 1, 10), sales_channel="Direct", order_status="completed", discount=0.0)
    i1 = OrderItem(order_item_id="I1", order_id="O1", product_id="P1", quantity=100, unit_price=10.0)

    o2 = Order(order_id="O2", customer_id="C_OTH", order_date=date(2025, 1, 15), sales_channel="Direct", order_status="completed", discount=0.0)
    i2 = OrderItem(order_item_id="I2", order_id="O2", product_id="P1", quantity=100, unit_price=10.0)

    # Period B: 2025-02-01 to 2025-02-28
    # Kar: 400 (delta: -600, 60% of decline), Other: 600 (delta: -400, 40% of decline) -> Total: 1000 (delta: -1000)
    o3 = Order(order_id="O3", customer_id="C_KAR", order_date=date(2025, 2, 10), sales_channel="Direct", order_status="completed", discount=0.0)
    i3 = OrderItem(order_item_id="I3", order_id="O3", product_id="P1", quantity=40, unit_price=10.0)

    o4 = Order(order_id="O4", customer_id="C_OTH", order_date=date(2025, 2, 15), sales_channel="Direct", order_status="completed", discount=0.0)
    i4 = OrderItem(order_item_id="I4", order_id="O4", product_id="P1", quantity=60, unit_price=10.0)

    session.add_all([o1, i1, o2, i2, o3, i3, o4, i4])
    session.commit()

    # Run REAL deterministic tool
    decomp = decompose_change(
        db=session,
        metric="revenue",
        period_a=("2025-01-01", "2025-01-31"),
        period_b=("2025-02-01", "2025-02-28"),
        dimensions=["region"]
    )
    session.close()

    # Pass REAL EvidenceItem objects to Claim Checker
    real_evidence = decomp.evidence
    assert len(real_evidence) > 0
    for item in real_evidence:
        assert isinstance(item, EvidenceItem)
        assert item.evidence_type == EvidenceType.DERIVED_FACT

    # Valid answer using real derived facts
    answer_valid = "Karnataka accounted for 60.0% of the decline with a delta of -600."
    res_valid = verify_answer(answer_valid, real_evidence)
    assert res_valid.status == "PASS"
    assert res_valid.verified_count == 2
    assert res_valid.verified[0].calculation is not None

    # Invalid answer with fabricated number
    answer_invalid = "Karnataka accounted for 90.0% of the decline with a delta of -900."
    res_invalid = verify_answer(answer_invalid, real_evidence)
    assert res_invalid.status == "FAIL"


# -------------------------------------------------------------
# 38. Section 10 & 11 Real End-to-End Integration: Campaign Impact & INFERENCE Isolation
# -------------------------------------------------------------
def test_real_e2e_campaign_impact_claim_verification():
    from datetime import date
    from app.services.campaign_impact import campaign_impact, CampaignDefinition
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models.business_data import Base, Customer, Product, Order, OrderItem

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()

    p = Product(product_id="P1", product_name="Hardware", category="Tech", unit_price=10.0, cost_per_unit=5.0)
    session.add(p)

    # 16 exposed customers, 16 control customers in South
    for i in range(16):
        c_exp = Customer(customer_id=f"EXP_{i}", customer_name=f"Exp {i}", region="South", customer_segment="Consumer", signup_date=date(2024, 1, 1), acquisition_channel="Organic")
        c_ctrl = Customer(customer_id=f"CTRL_{i}", customer_name=f"Ctrl {i}", region="South", customer_segment="Consumer", signup_date=date(2024, 1, 1), acquisition_channel="Organic")
        session.add_all([c_exp, c_ctrl])

        # Exposed: order in before (200), exposure (100), after (400) -> before: 200, after: 400, change: +200
        o_bef = Order(order_id=f"O_E_BEF_{i}", customer_id=f"EXP_{i}", order_date=date(2025, 4, 10), sales_channel="Direct", order_status="completed", discount=0.0)
        i_bef = OrderItem(order_item_id=f"I_E_BEF_{i}", order_id=f"O_E_BEF_{i}", product_id="P1", quantity=20, unit_price=10.0)
        o_exp = Order(order_id=f"O_E_EXP_{i}", customer_id=f"EXP_{i}", order_date=date(2025, 7, 10), sales_channel="Direct", order_status="completed", discount=0.0)
        i_exp = OrderItem(order_item_id=f"I_E_EXP_{i}", order_id=f"O_E_EXP_{i}", product_id="P1", quantity=10, unit_price=10.0)
        o_aft = Order(order_id=f"O_E_AFT_{i}", customer_id=f"EXP_{i}", order_date=date(2025, 10, 10), sales_channel="Direct", order_status="completed", discount=0.0)
        i_aft = OrderItem(order_item_id=f"I_E_AFT_{i}", order_id=f"O_E_AFT_{i}", product_id="P1", quantity=40, unit_price=10.0)

        # Control: order in before (200), NO order in exposure, after (300) -> before: 200, after: 300, change: +100
        o_c_bef = Order(order_id=f"O_C_BEF_{i}", customer_id=f"CTRL_{i}", order_date=date(2025, 4, 10), sales_channel="Direct", order_status="completed", discount=0.0)
        i_c_bef = OrderItem(order_item_id=f"I_C_BEF_{i}", order_id=f"O_C_BEF_{i}", product_id="P1", quantity=20, unit_price=10.0)
        o_c_aft = Order(order_id=f"O_C_AFT_{i}", customer_id=f"CTRL_{i}", order_date=date(2025, 10, 10), sales_channel="Direct", order_status="completed", discount=0.0)
        i_c_aft = OrderItem(order_item_id=f"I_C_AFT_{i}", order_id=f"O_C_AFT_{i}", product_id="P1", quantity=30, unit_price=10.0)

        session.add_all([o_bef, i_bef, o_exp, i_exp, o_aft, i_aft, o_c_bef, i_c_bef, o_c_aft, i_c_aft])

    session.commit()

    camp_def = CampaignDefinition(
        campaign_id="E2E-CAMP-TEST",
        name="E2E Test Campaign",
        region="South",
        exposure_window=(date(2025, 7, 1), date(2025, 9, 30)),
        before_window=(date(2025, 4, 1), date(2025, 6, 30)),
        after_window=(date(2025, 10, 1), date(2025, 12, 31)),
        description="E2E test campaign"
    )

    impact = campaign_impact(
        db=session,
        campaign_id="E2E-CAMP-TEST",
        min_sample_size=15,
        custom_definition=camp_def
    )
    session.close()

    # Real DiD = (400 - 200) - (300 - 200) = 200 - 100 = 100
    assert impact.did == 100.0
    assert impact.status == "SUCCESS"

    # Test Claim Checker with REAL Campaign Impact evidence
    valid_answer = "Exposed cohort average revenue was ₹200.00 before and ₹400.00 after, yielding a DiD of ₹100.00."
    res = verify_answer(valid_answer, impact.evidence)
    assert res.status == "PASS"
    assert res.verified_count == 3

    # Hard Invariant: INFERENCE EvidenceItem cannot support numerical claims
    inf_evidence = EvidenceItem(
        evidence_id="ev_inf_camp_conclusion",
        evidence_type=EvidenceType.INFERENCE,
        description=f"Campaign conclusion: '{impact.inference}'. DiD estimate ₹100.00.",
        limitations=["INFERENCE items must never be used as numerical evidence."]
    )
    # Claiming numbers against only INFERENCE item must fail
    res_inf_only = verify_answer("DiD was ₹100.00.", [inf_evidence])
    assert res_inf_only.status == "FAIL"
    assert res_inf_only.unverified_count == 1

