"""Policy engine: evaluates policy.yaml rules over a fact dict.

The engine is the final authority on what may be recommended/executed. It never uses ``eval``: conditions are
parsed with ``ast`` and only comparisons, boolean logic, names, constants, tuples/lists and ``in`` are allowed.
"""
from __future__ import annotations

import ast
import operator
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from verdict.config import settings

_CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt,
        ast.GtE: operator.ge, ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b}


class UnsafeExpression(ValueError):
    pass


@lru_cache(maxsize=512)
def _parse(expr: str) -> ast.Expression:
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.Compare, ast.Name,
                                 ast.Load, ast.Constant, ast.Tuple, ast.List, *(_CMP.keys()))):
            raise UnsafeExpression(f"disallowed syntax {type(node).__name__} in '{expr}'")
    return tree


def evaluate(expr: str, facts: dict[str, Any]) -> bool:
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.BoolOp):
            vals = (ev(v) for v in n.values)
            return all(vals) if isinstance(n.op, ast.And) else any(vals)
        if isinstance(n, ast.UnaryOp):
            return not ev(n.operand)
        if isinstance(n, ast.Compare):
            left = ev(n.left)
            for op, comp in zip(n.ops, n.comparators):
                right = ev(comp)
                try:
                    if not _CMP[type(op)](left, right):
                        return False
                except TypeError:
                    return False
                left = right
            return True
        if isinstance(n, ast.Name):
            return facts.get(n.id)
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, (ast.Tuple, ast.List)):
            return tuple(ev(e) for e in n.elts)
        raise UnsafeExpression(type(n).__name__)

    return bool(ev(_parse(expr)))


@dataclass
class PolicyDecision:
    actions: list[dict] = field(default_factory=list)       # [{code, route, clauses, class}]
    forbidden: list[dict] = field(default_factory=list)     # [{code, clause, reason}]
    deferred: list[dict] = field(default_factory=list)
    sar_required: bool = False
    sar_clauses: list[str] = field(default_factory=list)
    fired_rules: list[str] = field(default_factory=list)

    def codes(self) -> list[str]:
        return [a["code"] for a in self.actions]


class PolicyEngine:
    def __init__(self, path: Path | None = None):
        self.path = Path(path or settings.policy_file)
        self.p = yaml.safe_load(self.path.read_text())
        self.catalogue: dict[str, dict] = self.p["actions"]

    @property
    def action_codes(self) -> list[str]:
        return list(self.catalogue)

    def evidence_action_for(self, kind: str) -> str | None:
        for code, a in self.catalogue.items():
            if a.get("evidence_kind") == kind:
                return code
        return None

    def route(self, code: str, facts: dict) -> str:
        a = self.catalogue[code]
        for rr in a.get("route_rules", []):
            if evaluate(rr["when"], facts):
                return rr["route"]
        return a["route"]

    def decision_override(self, facts: dict) -> dict | None:
        for o in self.p.get("decision_overrides", []):
            if evaluate(o["when"], facts):
                return o
        return None

    def is_forbidden(self, code: str, facts: dict) -> dict | None:
        for f in self.p.get("forbid", []):
            if f["action"] == code and not evaluate(f["unless"], facts):
                return f
        return None

    def evaluate(self, facts: dict, extra: list[tuple[str, str]] | None = None) -> PolicyDecision:
        """Fire all rules; ``extra`` are (code, reason) proposals from the agent/LLM which are also policy-checked."""
        dec = PolicyDecision()
        wanted: dict[str, list[str]] = {}
        deferred: set[str] = set()
        for r in self.p.get("rules", []):
            if evaluate(r["when"], facts):
                dec.fired_rules.append(r["id"])
                for code in r.get("recommend", []):
                    wanted.setdefault(code, [])
                    if r["id"] not in wanted[code]:
                        wanted[code].append(r["id"])
                deferred |= set(r.get("defer", []))
        for code, why in extra or []:
            if code not in self.catalogue:
                dec.forbidden.append({"code": code, "clause": "POL-2", "reason": "not in the policy action catalogue"})
                continue
            wanted.setdefault(code, []).append(f"agent:{why}"[:80])
        for s in self.p.get("sar", []):
            if evaluate(s["when"], facts):
                dec.sar_required = True
                dec.sar_clauses.append(s["id"])
        if dec.sar_required:
            wanted.setdefault("FILE_REPORT", []).extend(c for c in dec.sar_clauses if c not in wanted.get("FILE_REPORT", []))
        decision = facts.get("decision")
        # resolve class conflicts in favour of the decision
        keep_class = {"PROTECT": "protect", "RELEASE": "release"}.get(decision)
        drop_classes = set(self.p.get("conflicts", {}).get(keep_class, [])) if keep_class else set()
        if decision == "GATHER":
            drop_classes = {"release"}
        for code, clauses in wanted.items():
            a = self.catalogue[code]
            if a.get("class") in drop_classes:
                continue
            if code in deferred:
                dec.deferred.append({"code": code, "clauses": clauses})
                continue
            fb = self.is_forbidden(code, facts)
            if fb:
                dec.forbidden.append({"code": code, "clause": fb["id"], "reason": f"forbidden unless {fb['unless']}"})
                continue
            dec.actions.append({"code": code, "route": self.route(code, facts), "clauses": clauses, "class": a.get("class")})
        order = list(self.catalogue)
        dec.actions.sort(key=lambda a: order.index(a["code"]))
        return dec
