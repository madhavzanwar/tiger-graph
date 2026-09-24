"""Create loading jobs and push prepared CSVs to TigerGraph over REST (works for CE and Savanna)."""
from __future__ import annotations

import time
from pathlib import Path

from verdict.config import ROOT, settings
from verdict.tg.client import conn, gsql

JOBS = [  # (job, file) in dependency order
    ("load_customers", "customers.csv"),
    ("load_cards", "cards.csv"),
    ("load_devices", "devices.csv"),
    ("load_txns", "transactions.csv"),
    ("load_cases", "cases_history.csv"),
    ("load_case_txn", "case_txn.csv"),
    ("load_case_card", "case_card.csv"),
]
CHUNK_LINES = 150_000


def create_jobs(prepared: Path | None = None) -> None:
    """Jobs use a user-defined header taken from each prepared CSV so columns load by name."""
    prepared = Path(prepared or settings.work_dir / "prepared")
    names = [j for j, _ in JOBS]
    gsql("USE GRAPH Verdict\n" + "\n".join(f"DROP JOB {n}" for n in names), check=False)
    text = (ROOT / "graph" / "loading" / "jobs.gsql").read_text()
    for job, fname in JOBS:
        cols = (prepared / fname).open().readline().strip().split(",")
        hdr = ", ".join(f'"{c}"' for c in cols)
        head, _, rest = text.partition(f"CREATE LOADING JOB {job} ")
        body, _, tail = rest.partition("}")
        body = body.replace("DEFINE FILENAME f;", f"DEFINE FILENAME f;\n  DEFINE HEADER h = {hdr};")
        body = body.replace('USING header="true"', 'USING USER_DEFINED_HEADER="h", header="true"')
        text = head + f"CREATE LOADING JOB {job} " + body + "}" + tail
    out = gsql(text, check=False)
    missing = [j for j in names if f"Successfully created loading jobs: [{j}]" not in out]
    if missing:
        raise RuntimeError(f"loading jobs not created {missing}:\n{out}")


def _chunks(path: Path):
    with path.open() as fh:
        fh.readline()  # header is declared in the job (USER_DEFINED_HEADER), so it is not sent
        header = ""
        buf: list[str] = []
        for line in fh:
            buf.append(line)
            if len(buf) >= CHUNK_LINES:
                yield header + "".join(buf)
                buf = []
        if buf:
            yield header + "".join(buf)


def load_all(prepared: Path | None = None) -> dict:
    prepared = Path(prepared or settings.work_dir / "prepared")
    c = conn("ops")
    report = {}
    for job, fname in JOBS:
        t0 = time.time()
        n = 0
        for chunk in _chunks(prepared / fname):
            res = c.runLoadingJobWithData(chunk, "f", job, sep=",", eol="\n", timeout=600000, sizeLimit=512 * 1024 * 1024)
            n += 1
            if not res:
                raise RuntimeError(f"{job} returned nothing")
        report[job] = {"chunks": n, "secs": round(time.time() - t0, 1)}
    report["vertices"] = c.getVertexCount("*")
    return report


VERTEX_TYPES = ["Transaction", "Card", "Customer", "Device", "EmailDomain", "Region", "FraudCase", "Evidence",
                "EvidenceRequest", "CaseAction", "Pattern", "DocChunk", "FeatureStat"]


def clear_data() -> None:
    """Delete all vertices (and therefore edges) while keeping schema, jobs and installed queries."""
    c = conn("ops")
    for vt in VERTEX_TYPES:
        c.delVertices(vt)
