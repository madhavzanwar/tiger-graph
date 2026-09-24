"""Grounding check for generated text (SAR narratives, summaries).

Every amount, number and identifier that appears in LLM-written text must exist in the evidence store for the
case. Unsupported claims are returned so the caller can regenerate (or fall back to the template).
"""
from __future__ import annotations

import json
import re

_NUM = re.compile(r"(?<![\w.])\$?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?(?![\w])|(?<![\w.])\$?\d+(?:\.\d+)?%?(?![\w])")
_ID = re.compile(r"\b(?:CARD|CUST|CC|HHG|FP|DEV|EV|RQ|AC)-[A-Za-z0-9-]+\b|\b\d{6,}\b")
_IGNORE = {"24", "1", "2", "3", "4", "5", "0", "100", "80", "90", "10", "30", "48", "6", "12"}


def _norm_num(s: str) -> str | None:
    s = s.replace("$", "").replace(",", "").rstrip("%")
    try:
        f = float(s)
    except ValueError:
        return None
    return f"{f:.2f}"


def allowed_tokens(*objs) -> tuple[set[str], set[str]]:
    blob = json.dumps(objs, default=str)
    nums = {n for n in (_norm_num(m) for m in _NUM.findall(blob)) if n}
    # probabilities are often rendered as percentages or rounded
    for m in re.findall(r"0\.\d+", blob):
        f = float(m)
        nums |= {f"{f:.2f}", f"{f * 100:.2f}", f"{round(f * 100):.2f}", f"{round(f, 1):.2f}", f"{round(f, 2):.2f}"}
    for m in re.findall(r"\d+\.\d+", blob):
        f = float(m)
        nums |= {f"{round(f):.2f}", f"{round(f, 1):.2f}"}
    ids = set(_ID.findall(blob))
    return nums, ids


def check(text: str, *evidence) -> list[str]:
    nums, ids = allowed_tokens(*evidence)
    bad = []
    for m in _ID.findall(text or ""):
        if m not in ids:
            bad.append(m)
    for m in _NUM.findall(text or ""):
        raw = m.replace("$", "").replace(",", "").rstrip("%")
        if raw in _IGNORE or re.fullmatch(r"20\d\d", raw):
            continue
        n = _norm_num(m)
        if n and n not in nums and not any(m.strip("$") in i for i in ids):
            bad.append(m)
    return sorted(set(bad))
