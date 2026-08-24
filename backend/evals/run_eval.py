"""Runs classification over evals/golden.jsonl and prints accuracy plus a
confidence correct-vs-incorrect split -- enough to sanity-check
CONFIDENCE_THRESHOLD, without building a full calibration harness.

Usage (from backend/): python -m evals.run_eval
Requires ANTHROPIC_API_KEY.
"""

import json
from pathlib import Path

from app.config import settings
from app.models import CompanySize, Industry, Urgency
from app.schemas import EnquiryCreate
from app.services.classifier import classify

GOLDEN_PATH = Path(__file__).parent / "golden.jsonl"


def load_golden() -> list[dict]:
    """Read golden.jsonl into a list of dicts, one per hand-labelled example
    (skipping blank lines). Each dict has the enquiry's form fields plus
    `gold_service_line`/`gold_complexity` to compare predictions against."""
    rows = []
    with open(GOLDEN_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    """Classify every golden-set row via the real classifier, print a
    per-row OK/MISS line, then a summary: service line and complexity
    accuracy, and mean confidence split by correct vs. incorrect predictions
    -- the latter is what actually justifies (or doesn't) the current
    CONFIDENCE_THRESHOLD, rather than it just being a guessed number."""
    rows = load_golden()
    correct_confidences = []
    incorrect_confidences = []
    service_line_correct = 0
    complexity_correct = 0

    for row in rows:
        # model_construct bypasses validation: the golden set deliberately
        # includes a below-floor description (row 5) to test insufficient-
        # information handling, which EnquiryCreate's 40-char floor -- a
        # guardrail for the live intake form, not the classifier -- would
        # otherwise reject before classify() ever saw it.
        payload = EnquiryCreate.model_construct(
            contact_name="Eval",
            contact_email="eval@example.com",
            company_name="Eval Co",
            industry=Industry(row["industry"]),
            industry_other="N/A" if row["industry"] == "other" else None,
            company_size=CompanySize(row["company_size"]),
            urgency=Urgency(row["urgency"]),
            description=row["description"],
        )
        result = classify(payload)

        predicted_service_line = result.service_line.value if result.service_line else None
        predicted_complexity = result.complexity.value if result.complexity else None

        sl_match = predicted_service_line == row["gold_service_line"]
        cx_match = predicted_complexity == row["gold_complexity"]

        service_line_correct += int(sl_match)
        complexity_correct += int(cx_match)
        (correct_confidences if sl_match else incorrect_confidences).append(result.confidence)

        print(
            f"[{'OK ' if sl_match else 'MISS'}] gold={row['gold_service_line']!s:<26} "
            f"pred={predicted_service_line!s:<26} conf={result.confidence:.2f} "
            f"complexity gold={row['gold_complexity']!s:<10} pred={predicted_complexity}"
        )

    n = len(rows)
    print("\n--- summary ---")
    print(f"model: {settings.MODEL_ID}")
    print(f"service line accuracy: {service_line_correct}/{n} ({service_line_correct / n:.0%})")
    print(f"complexity accuracy:   {complexity_correct}/{n} ({complexity_correct / n:.0%})")

    def _avg(values: list[float]) -> str:
        """Mean formatted to 2dp, or "n/a" for an empty list (e.g. every
        prediction happened to be correct, leaving no incorrect ones)."""
        return f"{sum(values) / len(values):.2f}" if values else "n/a"

    print(f"mean confidence when correct:   {_avg(correct_confidences)} (n={len(correct_confidences)})")
    print(f"mean confidence when incorrect: {_avg(incorrect_confidences)} (n={len(incorrect_confidences)})")
    print(f"\ncurrent CONFIDENCE_THRESHOLD={settings.CONFIDENCE_THRESHOLD}")


if __name__ == "__main__":
    main()
