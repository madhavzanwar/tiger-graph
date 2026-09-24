"""VERDICT command line.

  verdict synth                      generate the synthetic HHGOA-shaped dataset (data/synthetic)
  verdict bootstrap [--drop]         prepare -> schema -> load -> install queries -> algorithms -> calibrate -> GraphRAG -> discovery
  verdict benchmark [CASE ...]       investigate the case pack and write answer files
  verdict investigate CASE           investigate one case and print the result
  verdict serve                      start the API + analyst UI
  verdict ops-mcp                    run the VERDICT ops MCP server (stdio)
  verdict export-demo                snapshot stored investigations into ui/public/demo for static hosting (Vercel)
  individual steps: prepare | init | load | install | algos | calibrate | ingest | discover | status
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from verdict.config import settings


def _p(obj) -> None:
    print(json.dumps(obj, indent=1, default=str))


def step(name: str, fn, *a, **kw):
    t = time.time()
    print(f"==> {name} ...", flush=True)
    r = fn(*a, **kw)
    print(f"    done in {time.time() - t:.1f}s", flush=True)
    return r


def cmd_bootstrap(args) -> None:
    from verdict.calibrate.calibration import calibrate
    from verdict.data.prepare import prepare
    from verdict.memory.discover import discover
    from verdict.memory.learning import publish_feature_stats
    from verdict.rag.graphrag import ingest
    from verdict.tg import algos, installer, loader

    _p(step("prepare", prepare))
    if args.drop or args.init:
        step("schema", installer.init_schema, drop=args.drop)
    else:
        print("==> schema: skipped (use --init for a fresh database or --drop to recreate)")
    if not args.skip_install:
        _p(step("install queries (takes a few minutes)", installer.install_queries))
    step("clear data", loader.clear_data)
    step("create loading jobs", loader.create_jobs)
    _p(step("load", loader.load_all))
    time.sleep(10)
    _p(step("graph algorithms", algos.run_algorithms))
    _p(step("calibrate evidence model on closed cases", calibrate))
    step("publish feature stats", publish_feature_stats)
    _p(step("GraphRAG ingest", ingest))
    d = step("undocumented-pattern discovery", discover)
    _p([{k: h[k] for k in ("name", "n_cases", "signals")} for h in d.get("hypotheses", [])])


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="verdict", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("synth")
    s.add_argument("--out", default="data/synthetic")
    s.add_argument("--customers", type=int, default=1200)
    b = sub.add_parser("bootstrap")
    b.add_argument("--drop", action="store_true", help="DROP ALL and recreate the schema")
    b.add_argument("--init", action="store_true", help="create the schema (fresh database)")
    b.add_argument("--skip-install", action="store_true")
    bm = sub.add_parser("benchmark")
    bm.add_argument("cases", nargs="*")
    iv = sub.add_parser("investigate")
    iv.add_argument("case")
    sv = sub.add_parser("serve")
    sv.add_argument("--port", type=int, default=8000)
    sv.add_argument("--host", default="0.0.0.0")
    for n in ("prepare", "init", "load", "install", "algos", "calibrate", "ingest", "discover", "status", "ops-mcp", "export-demo"):
        sub.add_parser(n)
    a = ap.parse_args(argv)

    if a.cmd == "synth":
        from verdict.data.synth import Synth

        Synth(n_customers=a.customers).generate(Path(a.out))
    elif a.cmd == "bootstrap":
        cmd_bootstrap(a)
    elif a.cmd == "prepare":
        from verdict.data.prepare import prepare

        _p(prepare())
    elif a.cmd == "init":
        from verdict.tg.installer import init_schema

        print(init_schema()[-2000:])
    elif a.cmd == "load":
        from verdict.tg import loader

        loader.create_jobs()
        _p(loader.load_all())
    elif a.cmd == "install":
        from verdict.tg.installer import install_queries

        _p(install_queries())
    elif a.cmd == "algos":
        from verdict.tg.algos import run_algorithms

        _p(run_algorithms())
    elif a.cmd == "calibrate":
        from verdict.calibrate.calibration import calibrate

        _p(calibrate())
    elif a.cmd == "ingest":
        from verdict.rag.graphrag import ingest

        _p(ingest())
    elif a.cmd == "discover":
        from verdict.agent.llm import LLM
        from verdict.memory.discover import discover

        _p(discover(llm=LLM()))
    elif a.cmd == "status":
        from verdict.tg.client import conn
        from verdict.tg.installer import installed

        c = conn()
        _p({"vertices": c.getVertexCount("*"), "queries": installed(), "llm": settings.use_llm, "model": settings.model,
            "graph_access": settings.graph_access, "data_dir": str(settings.data_dir)})
    elif a.cmd == "benchmark":
        from verdict.outputs.benchmark import run

        run(a.cases or None)
        print(f"answers written to {settings.answers_dir}")
    elif a.cmd == "investigate":
        import pandas as pd

        from verdict.agent.orchestrator import Shared, run_case
        from verdict.outputs.benchmark import load_oracle

        pack = pd.read_csv(settings.work_dir / "prepared" / "case_pack.csv", dtype=str).fillna("")
        row = pack[pack["case_id"] == a.case]
        if row.empty:
            sys.exit(f"case {a.case} not in case pack")
        st = run_case(row.iloc[0].to_dict(), Shared.create(), oracle=load_oracle().get(a.case))
        _p({k: st[k] for k in ("case_id", "status", "nba_before_evidence", "evidence_requests", "nba_after_evidence", "explanation")})
    elif a.cmd == "serve":
        import uvicorn

        uvicorn.run("verdict.api.app:app", host=a.host, port=a.port, log_level="info")
    elif a.cmd == "export-demo":
        from verdict.outputs.export_demo import export

        _p(export())
    elif a.cmd == "ops-mcp":
        from verdict.ops_mcp.server import main as ops_main

        ops_main()


if __name__ == "__main__":
    main()
