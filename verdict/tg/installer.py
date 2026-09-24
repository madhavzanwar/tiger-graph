"""Schema bootstrap, query installation and GDS algorithm installation."""
from __future__ import annotations

import re
from pathlib import Path

from verdict.config import ROOT
from verdict.tg.client import conn, gsql

QUERY_DIR = ROOT / "graph" / "queries"
ALGO_DIR = ROOT / "graph" / "algorithms"


def init_schema(drop: bool = False) -> str:
    out = []
    if drop:
        out.append(gsql("DROP ALL", check=False))
    out.append(gsql((ROOT / "graph" / "schema.gsql").read_text()))
    out.append(gsql((ROOT / "graph" / "vectors.gsql").read_text()))
    return "\n".join(out)


def _query_names(text: str) -> list[str]:
    return re.findall(r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:DISTRIBUTED\s+)?QUERY\s+(\w+)", text, flags=re.I)


def install_queries(files: list[Path] | None = None) -> dict:
    """Create every query in graph/algorithms and graph/queries, then INSTALL them in one batch."""
    files = files or sorted(ALGO_DIR.glob("*.gsql")) + sorted(QUERY_DIR.glob("*.gsql"))
    names: list[str] = []
    for f in files:
        text = f.read_text()
        res = gsql(f"USE GRAPH Verdict\n{text}", check=False)
        if re.search(r"(Semantic Check Fails|Syntax Error|Failed to create)", res):
            raise RuntimeError(f"{f.name}:\n{res}")
        names += _query_names(text)
    res = gsql("USE GRAPH Verdict\nINSTALL QUERY " + ", ".join(names), check=False)
    if "Query installation finished" not in res and "already installed" not in res.lower():
        raise RuntimeError(res[-3000:])
    return {"installed": names}


def installed() -> list[str]:
    ep = conn().getEndpoints(dynamic=True)
    return sorted({k.split("/")[-1] for k in ep})
