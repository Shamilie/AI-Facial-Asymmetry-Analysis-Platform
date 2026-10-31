"""
Research summary generation with guardrails.

* ``deterministic_summary`` builds text purely from approved/stored data.
* ``build_llm_messages`` constrains an LLM to explain existing data only.
* ``validate_llm_summary`` rejects LLM output that introduces numbers not
  present in the input (prevents invented measurements).
"""

from __future__ import annotations

import json
import re
from typing import Any

DISCLAIMER = (
    "Research measurement output only. Not a diagnosis, treatment recommendation, "
    "or substitute for clinical judgement."
)

SYSTEM_PROMPT = (
    "You write concise structured research summaries for a facial asymmetry study. "
    "Use ONLY the JSON data provided. Never invent, estimate, or infer measurements, "
    "landmark coordinates, pixel distances, millimetre values, asymmetry indices or clinical findings. "
    "If a value is missing, say it is not available. Do not give diagnoses or treatment advice. "
    "Clearly distinguish approved, examiner-reviewed and AI-predicted (unvalidated) values."
)


def _fmt(v: Any, nd: int = 2) -> str:
    return "not available" if v is None else f"{v:.{nd}f}"


def deterministic_summary(data: dict[str, Any]) -> str:
    lines = [f"Research summary for patient {data.get('patient_code')} — visit {data.get('visit_label', 'all visits')}."]
    ms = data.get("measurements", [])
    approved = [m for m in ms if m.get("status") == "Approved"]
    lines.append(f"{len(ms)} measurement records available; {len(approved)} approved by an examiner.")
    for m in ms:
        lines.append(
            f"- {m['name']} [{m.get('method')}, {m.get('status')}]: right {_fmt(m.get('right_value'))} {m.get('unit', '')}, "
            f"left {_fmt(m.get('left_value'))} {m.get('unit', '')}, asymmetry index {_fmt(m.get('asymmetry_index'))}%."
        )
    unscaled = [m["name"] for m in ms if m.get("status") == "Unscaled"]
    if unscaled:
        lines.append("Unscaled (no physical calibration): " + ", ".join(unscaled) + ".")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def build_llm_messages(data: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Summarise this approved research data:\n" + json.dumps(data, default=str)},
    ]


_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def validate_llm_summary(text: str, data: dict[str, Any]) -> list[str]:
    allowed: set[str] = set()

    def walk(v: Any) -> None:
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            for nd in (0, 1, 2, 3):
                allowed.add(f"{round(float(v), nd):.{nd}f}")
            allowed.add(str(v))
        elif isinstance(v, str):
            allowed.update(_NUM.findall(v))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(data)
    problems = []
    for n in _NUM.findall(text):
        if n not in allowed and n.lstrip("-") not in allowed and not re.fullmatch(r"[0-9]", n):
            problems.append(f"Summary contains a number not present in source data: {n}")
    return problems
