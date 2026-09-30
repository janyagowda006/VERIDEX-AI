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

    def growth_rate(
        self,
        current: float,
        previous: float,
        current_label: str = "Current",
        previous_label: str = "Previous",
        input_evidence_ids: Optional[List[str]] = None
    ) -> EvidenceItem:
        """
        Calculates deterministic growth rate from previous to current:
        ((current - previous) / previous) * 100
        Handles previous == 0 safely with output=None and explicit limitation.
        """
        ev_id = self.generate_evidence_id()
        input_ids = input_evidence_ids or []
        limitations: List[str] = []

        if previous == 0.0:
            limitations.append("Division by zero: previous baseline value is 0. Growth rate is undefined.")
            calc = DerivedFactCalculation(
                formula_name="growth_rate",
                formula=f"(({current_label} - {previous_label}) / {previous_label}) * 100",
                inputs={current_label: current, previous_label: previous},
                output=None,
                input_evidence_ids=input_ids
            )
            return EvidenceItem(
                evidence_id=ev_id,
                evidence_type=EvidenceType.DERIVED_FACT,
                description=f"Growth rate from {previous_label} ({previous}) to {current_label} ({current}) is undefined (division by zero).",
                source=None,
                calculation=calc,
                limitations=limitations
            )

        rate = round(((current - previous) / previous) * 100, 2)
        direction = "positive growth" if rate > 0 else "negative growth" if rate < 0 else "zero growth"
        calc = DerivedFactCalculation(
            formula_name="growth_rate",
            formula=f"(({current_label} - {previous_label}) / {previous_label}) * 100",
            inputs={current_label: current, previous_label: previous},
            output=rate,
            input_evidence_ids=input_ids
        )
        desc = f"Growth rate from {previous_label} ({previous}) to {current_label} ({current}) is {rate}% ({direction})."

        return EvidenceItem(
            evidence_id=ev_id,
            evidence_type=EvidenceType.DERIVED_FACT,
            description=desc,
            source=None,
            calculation=calc,
            limitations=limitations
        )

    def margin_percent(
        self,
        revenue: float,
        cost: float,
        revenue_label: str = "Revenue",
        cost_label: str = "Cost",
        input_evidence_ids: Optional[List[str]] = None
    ) -> EvidenceItem:
        """
        Calculates profit margin percentage: ((revenue - cost) / revenue) * 100
        Handles revenue == 0 safely with output=None and explicit limitation.
        """
        ev_id = self.generate_evidence_id()
        input_ids = input_evidence_ids or []
        limitations: List[str] = []

        if revenue == 0.0:
            limitations.append("Division by zero: revenue is 0. Margin percentage is undefined.")
            calc = DerivedFactCalculation(
                formula_name="margin_percent",
                formula=f"(({revenue_label} - {cost_label}) / {revenue_label}) * 100",
                inputs={revenue_label: revenue, cost_label: cost},
                output=None,
                input_evidence_ids=input_ids
            )
            return EvidenceItem(
                evidence_id=ev_id,
                evidence_type=EvidenceType.DERIVED_FACT,
                description=f"Margin percentage for {revenue_label} ({revenue}) and {cost_label} ({cost}) is undefined (revenue is zero).",
                source=None,
                calculation=calc,
                limitations=limitations
            )

        margin = round(((revenue - cost) / revenue) * 100, 2)
        calc = DerivedFactCalculation(
            formula_name="margin_percent",
            formula=f"(({revenue_label} - {cost_label}) / {revenue_label}) * 100",
            inputs={revenue_label: revenue, cost_label: cost},
            output=margin,
            input_evidence_ids=input_ids
        )
        desc = f"Margin percentage for {revenue_label} ({revenue}) with {cost_label} ({cost}) is {margin}%."

        return EvidenceItem(
            evidence_id=ev_id,
            evidence_type=EvidenceType.DERIVED_FACT,
            description=desc,
            source=None,
            calculation=calc,
            limitations=limitations
        )

    def statistical_summary(
        self,
        values: List[Any],
        metric_label: str = "Metric Values",
        input_evidence_ids: Optional[List[str]] = None
    ) -> EvidenceItem:
        """
        Calculates deterministic statistical summary: count, min, max, mean, median, and IQR (Q3 - Q1).
        Uses standard Tukey's method for deterministic quartiles without external library dependencies.
        Validates input against empty or non-numeric entries explicitly.
        """
        ev_id = self.generate_evidence_id()
        input_ids = input_evidence_ids or []
        limitations: List[str] = []

        if not values or len(values) == 0:
            limitations.append("Empty dataset: cannot compute statistical summary.")
            calc = DerivedFactCalculation(
                formula_name="statistical_summary",
                formula="count, min, max, mean, median, IQR (Q3 - Q1)",
                inputs={metric_label: []},
                output=None,
                input_evidence_ids=input_ids
            )
            return EvidenceItem(
                evidence_id=ev_id,
                evidence_type=EvidenceType.DERIVED_FACT,
                description=f"Statistical summary for {metric_label} is undefined (empty dataset).",
                source=None,
                calculation=calc,
                limitations=limitations
            )

        # Explicit validation: detect None, boolean (subclass of int in Python), or non-numeric types
        invalid_entries = [v for v in values if v is None or isinstance(v, bool) or not isinstance(v, (int, float))]
        if invalid_entries:
            limitations.append(f"Invalid non-numeric values detected in input: {invalid_entries[:5]}. Statistical summary cannot be calculated.")
            calc = DerivedFactCalculation(
                formula_name="statistical_summary",
                formula="count, min, max, mean, median, IQR (Q3 - Q1)",
                inputs={metric_label: [str(v) for v in values[:10]]},
                output=None,
                input_evidence_ids=input_ids
            )
            return EvidenceItem(
                evidence_id=ev_id,
                evidence_type=EvidenceType.DERIVED_FACT,
                description=f"Statistical summary for {metric_label} could not be computed due to non-numeric input.",
                source=None,
                calculation=calc,
                limitations=limitations
            )

        # Convert to float and sort deterministically
        sorted_vals = sorted([float(v) for v in values])
        n = len(sorted_vals)
        min_val = round(sorted_vals[0], 4)
        max_val = round(sorted_vals[-1], 4)
        mean_val = round(sum(sorted_vals) / n, 4)

        def _calc_median(nums: List[float]) -> float:
            count = len(nums)
            mid = count // 2
            if count % 2 == 1:
                return nums[mid]
            return round((nums[mid - 1] + nums[mid]) / 2.0, 4)

        median_val = _calc_median(sorted_vals)

        # Quartile calculation using Tukey's method (exclusive halves)
        if n == 1:
            q1_val = sorted_vals[0]
            q3_val = sorted_vals[0]
        elif n == 2:
            q1_val = sorted_vals[0]
            q3_val = sorted_vals[1]
        else:
            mid = n // 2
            lower_half = sorted_vals[:mid]
            upper_half = sorted_vals[mid:] if n % 2 == 0 else sorted_vals[mid + 1:]
            q1_val = _calc_median(lower_half)
            q3_val = _calc_median(upper_half)

        iqr_val = round(q3_val - q1_val, 4)

        summary_output = {
            "count": n,
            "min": min_val,
            "max": max_val,
            "mean": mean_val,
            "median": median_val,
            "q1": q1_val,
            "q3": q3_val,
            "iqr": iqr_val
        }

        input_preview = sorted_vals[:10]
        input_preview_dict: Dict[str, Any] = {
            metric_label: input_preview,
            "total_count": n
        } if n > 10 else {metric_label: input_preview}

        calc = DerivedFactCalculation(
            formula_name="statistical_summary",
            formula="count, min, max, mean, median, IQR (Q3 - Q1)",
            inputs=input_preview_dict,
            output=summary_output,
            input_evidence_ids=input_ids
        )
        desc = (
            f"Statistical summary for {metric_label} (N={n}): "
            f"Mean={mean_val}, Median={median_val}, IQR={iqr_val} [Min={min_val}, Max={max_val}]."
        )

        return EvidenceItem(
            evidence_id=ev_id,
            evidence_type=EvidenceType.DERIVED_FACT,
            description=desc,
            source=None,
            calculation=calc,
            limitations=limitations
        )

    def compound_metric(
        self,
        name: str,
        formula_expr: str,
        inputs: Dict[str, Any],
        input_evidence_ids: Optional[List[str]] = None
    ) -> EvidenceItem:
        """
        Deterministic compound metric evaluation using registered safe formula templates.
        SECURITY GUARD: Does NOT use eval(), exec(), or arbitrary dynamic code execution.
        Unrecognized or arbitrary expressions are rejected safely with output=None and security limitation.
        """
        ev_id = self.generate_evidence_id()
        input_ids = input_evidence_ids or []
        limitations: List[str] = []

        # Validate inputs are numeric
        cleaned_inputs: Dict[str, float] = {}
        for k, v in inputs.items():
            if v is None or isinstance(v, bool) or not isinstance(v, (int, float)):
                limitations.append(f"Input '{k}' has invalid non-numeric value: {v}.")
            else:
                cleaned_inputs[k] = float(v)

        if limitations:
            calc = DerivedFactCalculation(
                formula_name=name,
                formula=formula_expr,
                inputs=inputs,
                output=None,
                input_evidence_ids=input_ids
            )
            return EvidenceItem(
                evidence_id=ev_id,
                evidence_type=EvidenceType.DERIVED_FACT,
                description=f"Compound metric '{name}' could not be evaluated due to invalid inputs.",
                source=None,
                calculation=calc,
                limitations=limitations
            )

        norm_expr = formula_expr.strip().lower()
        output: Optional[float] = None

        if norm_expr in ["a - b", "difference", "subtraction", "{a} - {b}"]:
            keys = list(cleaned_inputs.keys())
            if len(keys) >= 2:
                output = round(cleaned_inputs[keys[0]] - cleaned_inputs[keys[1]], 4)
            else:
                limitations.append("Difference requires at least 2 input values.")

        elif norm_expr in ["a + b", "sum", "addition", "{a} + {b}"]:
            keys = list(cleaned_inputs.keys())
            if len(keys) >= 2:
                output = round(cleaned_inputs[keys[0]] + cleaned_inputs[keys[1]], 4)
            else:
                limitations.append("Sum requires at least 2 input values.")

        elif norm_expr in ["a / b", "ratio", "division", "{a} / {b}"]:
            keys = list(cleaned_inputs.keys())
            if len(keys) >= 2:
                denom = cleaned_inputs[keys[1]]
                if denom == 0.0:
                    limitations.append("Division by zero in ratio evaluation.")
                else:
                    output = round(cleaned_inputs[keys[0]] / denom, 4)
            else:
                limitations.append("Ratio requires at least 2 input values.")

        elif norm_expr in ["((a - b) / a) * 100", "margin_percent", "margin"]:
            keys = list(cleaned_inputs.keys())
            rev_key = next((k for k in keys if "rev" in k.lower()), keys[0] if keys else None)
            cost_key = next((k for k in keys if "cost" in k.lower()), keys[1] if len(keys) > 1 else None)
            if rev_key and cost_key:
                rev = cleaned_inputs[rev_key]
                cost = cleaned_inputs[cost_key]
                if rev == 0.0:
                    limitations.append("Division by zero: revenue denominator is 0.")
                else:
                    output = round(((rev - cost) / rev) * 100, 2)
            else:
                limitations.append("Margin formula requires revenue and cost inputs.")

        elif norm_expr in ["((a - b) / b) * 100", "growth_rate", "growth"]:
            keys = list(cleaned_inputs.keys())
            curr_key = next((k for k in keys if "curr" in k.lower()), keys[0] if keys else None)
            prev_key = next((k for k in keys if "prev" in k.lower()), keys[1] if len(keys) > 1 else None)
            if curr_key and prev_key:
                curr = cleaned_inputs[curr_key]
                prev = cleaned_inputs[prev_key]
                if prev == 0.0:
                    limitations.append("Division by zero: previous denominator is 0.")
                else:
                    output = round(((curr - prev) / prev) * 100, 2)
            else:
                limitations.append("Growth formula requires current and previous inputs.")

        elif norm_expr in ["(a / b) * 100", "share_of_total", "share"]:
            keys = list(cleaned_inputs.keys())
            if len(keys) >= 2:
                tot = cleaned_inputs[keys[1]]
                if tot == 0.0:
                    limitations.append("Division by zero: total denominator is 0.")
                else:
                    output = round((cleaned_inputs[keys[0]] / tot) * 100, 2)
            else:
                limitations.append("Share of total requires part and total inputs.")

        else:
            limitations.append(
                f"Security rejection: arbitrary formula '{formula_expr}' is not a registered safe template. "
                "Dynamic code execution (eval/exec) is strictly prohibited."
            )

        calc = DerivedFactCalculation(
            formula_name=name,
            formula=formula_expr,
            inputs=inputs,
            output=output,
            input_evidence_ids=input_ids
        )
        desc = (
            f"Compound metric '{name}' ({formula_expr}): result = {output}."
            if output is not None else
            f"Compound metric '{name}' could not be safely computed."
        )

        return EvidenceItem(
            evidence_id=ev_id,
            evidence_type=EvidenceType.DERIVED_FACT,
            description=desc,
            source=None,
            calculation=calc,
            limitations=limitations
        )
