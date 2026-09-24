"""Graph access for the agent.

Two interchangeable backends:
  * McpGateway    - the official ``tigergraph-mcp`` server over stdio, started with a read-only tool filter
                    (``TG_ALLOWED_TOOLS=read-only,run_installed_query``). This is the default path.
  * DirectGateway - pyTigerGraph, used for bulk/offline jobs (calibration, backtests) where MCP overhead
                    would only add latency.

Both enforce the same allow-list: only ``inv_*`` / ``mem_*`` read queries can be executed by the agent.
Every call is recorded (tool, args, latency, size) so the UI can show the investigation trail.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Any, Callable

from verdict.config import ROOT, settings

# name -> (param spec, description). Param kinds: vertex types, "datetime", "int", "float".
QUERIES: dict[str, dict[str, Any]] = {
    "inv_txn_context": {"params": {"txn": "Transaction"},
                        "desc": "One-hop profile of a transaction: card, customer, device, purchaser/recipient email, billing region, risk score, identity flags."},
    "inv_card_velocity": {"params": {"card": "Card", "t0": "datetime", "window_min": "int"},
                          "desc": "Card-testing signature: small online authorisations in the window before t0 and larger purchases after them; 24h card velocity."},
    "inv_customer_baseline": {"params": {"txn": "Transaction", "lookback_days": "int"},
                              "desc": "Customer/card behavioural baseline before the transaction: amount statistics, hour-of-day histogram, online ratio, card dormancy."},
    "inv_device_profile": {"params": {"txn": "Transaction", "window_days": "int"},
                           "desc": "Device novelty for this customer, identity new-device and proxy flags, other customers/cards on the device, prior fraud cases on it."},
    "inv_region_profile": {"params": {"txn": "Transaction", "window_h": "int"},
                           "desc": "Billing-region novelty for the customer and concurrent activity elsewhere (e.g. at home) around the transaction."},
    "inv_identity_consistency": {"params": {"txn": "Transaction", "window_h": "int"},
                                 "desc": "Account-takeover indicators: address/name match failures, purchaser email change, mixed channels with new devices."},
    "inv_linked_entities": {"params": {"txn": "Transaction", "window_days": "int"},
                            "desc": "Ring detection: other cards sharing a device or recipient email with this card in the window, and whether they are high-risk or had fraud cases."},
    "inv_prior_cases": {"params": {"txn": "Transaction"},
                        "desc": "Case memory: prior fraud cases on this customer or card opened before the transaction, with outcomes and actions."},
    "inv_similar_cases": {"params": {"txn": "Transaction", "k": "int"},
                          "desc": "Structural precedent retrieval: closed cases whose transactions share rare entities with this transaction, with outcomes and patterns."},
    "inv_community": {"params": {"card": "Card"},
                      "desc": "Fraud-ring context from the card projection: WCC component and Louvain community sizes, direct links, fraud cards in the component."},
    "inv_exposure": {"params": {"txn": "Transaction", "window_h": "int"},
                     "desc": "Money at risk on the card in the last 24h and suspicious activity on the customer's other cards (wider compromise)."},
    "rag_search_docs": {"params": {"qv": "vector", "k": "int"},
                        "desc": "GraphRAG semantic search over policy, pattern and regulation clauses (TigerVector)."},
    "rag_search_cases": {"params": {"qv": "vector", "k": "int"},
                         "desc": "GraphRAG semantic search over closed-case narratives, expanded to the cases' cards."},
    "mem_case_record": {"params": {"fcase": "FraudCase"},
                        "desc": "Full stored case record: evidence, evidence requests, actions, linked transactions/cards, patterns, similar cases."},
}

VERTEX_TYPES = {"Transaction", "Card", "Customer", "FraudCase", "Device", "EmailDomain", "Region"}


@dataclass
class CallRecord:
    tool: str
    args: dict
    ms: float
    ok: bool
    via: str
    size: int = 0
    error: str = ""


@dataclass
class Gateway:
    via: str = "direct"
    calls: list[CallRecord] = field(default_factory=list)
    on_call: Callable[[CallRecord], None] | None = None

    def run_query(self, name: str, params: dict) -> list:
        if name not in QUERIES:
            raise PermissionError(f"query '{name}' is not on the investigator allow-list")
        spec = QUERIES[name]["params"]
        clean = {k: v for k, v in params.items() if k in spec and v is not None}
        t = time.time()
        try:
            res = self._run(name, clean)
            rec = CallRecord(name, clean, (time.time() - t) * 1000, True, self.via, len(json.dumps(res, default=str)))
            return res
        except Exception as e:  # noqa: BLE001
            rec = CallRecord(name, clean, (time.time() - t) * 1000, False, self.via, 0, str(e)[:300])
            raise
        finally:
            self.calls.append(rec)
            if self.on_call:
                self.on_call(rec)

    def _run(self, name: str, params: dict) -> list:  # pragma: no cover - abstract
        raise NotImplementedError

    def vector_search(self, vertex_type: str, query_vector: list[float], top_k: int = 5) -> list[dict]:
        raise NotImplementedError

    def close(self) -> None:
        pass


class DirectGateway(Gateway):
    def __init__(self, profile: str = "investigator"):
        super().__init__(via="direct")
        from verdict.tg.client import conn

        self.c = conn(profile)

    def _run(self, name: str, params: dict) -> list:
        spec = QUERIES[name]["params"]
        p = {k: ((str(v),) if spec[k] in VERTEX_TYPES else v) for k, v in params.items()}
        return self.c.runInstalledQuery(name, p, timeout=60000)

    def vector_search(self, vertex_type: str, query_vector: list[float], top_k: int = 5) -> list[dict]:
        t = time.time()
        res = self.c.vectorSearch(vertexType=vertex_type, vectorAttribute="emb", queryVector=query_vector, k=top_k) \
            if hasattr(self.c, "vectorSearch") else _gsql_vector_search(self.c, vertex_type, query_vector, top_k)
        self.calls.append(CallRecord("vector_search", {"vertex_type": vertex_type, "k": top_k}, (time.time() - t) * 1000, True, self.via))
        return res


def _gsql_vector_search(c, vertex_type: str, qv: list[float], k: int) -> list[dict]:
    vec = ",".join(f"{x:.6f}" for x in qv)
    q = (f"USE GRAPH {settings.tg_graph}\nINTERPRET QUERY () FOR GRAPH {settings.tg_graph} {{\n"
         f"  MapAccum<VERTEX, FLOAT> @@d;\n  R = vectorSearch({{{vertex_type}.emb}}, [{vec}], {k}, {{distanceMap: @@d}});\n"
         f"  PRINT R, @@d;\n}}")
    out = c.gsql(q)
    try:
        js = json.loads(out[out.index("{"):])
        res = js["results"]
        dist = res[1]["@@d"]
        return [{"id": v["v_id"], "type": v["v_type"], "attributes": v["attributes"], "distance": dist.get(v["v_id"])} for v in res[0]["R"]]
    except Exception:  # noqa: BLE001
        return []


class McpGateway(Gateway):
    """Keeps one MCP stdio session open on a background event loop."""

    def __init__(self):
        super().__init__(via="mcp")
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._session = None
        self._err: Exception | None = None
        self._thread = threading.Thread(target=self._runner, daemon=True)
        self._thread.start()
        self._ready.wait(90)
        if self._err:
            raise self._err
        if self._session is None:
            raise RuntimeError("MCP session did not start")

    def _runner(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._main())

    async def _main(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import get_default_environment, stdio_client

        env = {**get_default_environment(),
               "TG_HOST": settings.tg_host, "TG_GRAPHNAME": settings.tg_graph,
               "TG_USERNAME": settings.tg_investigator_user or settings.tg_user,
               "TG_PASSWORD": settings.tg_investigator_password or settings.tg_password,
               "TG_RESTPP_PORT": settings.tg_restpp_port, "TG_GS_PORT": settings.tg_gs_port,
               # least privilege at the MCP layer: read-only tools + installed queries (allow-listed below)
               "TG_ALLOWED_TOOLS": "read-only,run_installed_query"}
        if settings.tg_api_token:
            env["TG_API_TOKEN"] = settings.tg_api_token
        exe = ROOT / ".venv" / "bin" / "tigergraph-mcp"
        params = StdioServerParameters(command=str(exe) if exe.exists() else "tigergraph-mcp", args=[], env=env)
        self._stop = asyncio.Event()
        try:
            async with stdio_client(params) as (r, w):
                async with ClientSession(r, w) as s:
                    await s.initialize()
                    tools = await s.list_tools()
                    self.tool_names = [t.name for t in tools.tools]
                    self._session = s
                    self._ready.set()
                    await self._stop.wait()
        except Exception as e:  # noqa: BLE001
            self._err = e
            self._ready.set()

    def call_tool(self, tool: str, args: dict) -> dict:
        async def _c():
            return await self._session.call_tool(tool, arguments=args)

        fut: Future = asyncio.run_coroutine_threadsafe(_c(), self._loop)
        res = fut.result(timeout=120)
        text = "".join(getattr(c, "text", "") for c in res.content)
        data, _ = json.JSONDecoder().raw_decode(text[text.find("{"):]) if "{" in text else ({}, 0)
        if not data.get("success", False):
            raise RuntimeError(data.get("error") or text[:300])
        return data

    def _run(self, name: str, params: dict) -> list:
        data = self.call_tool("tigergraph__run_installed_query", {"query_name": name, "params": params})
        return data["data"]["result"]

    def vector_search(self, vertex_type: str, query_vector: list[float], top_k: int = 5) -> list[dict]:
        t = time.time()
        data = self.call_tool("tigergraph__search_top_k_similarity", {"vertex_type": vertex_type, "vector_attribute": "emb",
                                                                       "query_vector": query_vector, "top_k": top_k})
        self.calls.append(CallRecord("tigergraph__search_top_k_similarity", {"vertex_type": vertex_type, "top_k": top_k},
                                     (time.time() - t) * 1000, True, self.via))
        d = data.get("data", {})
        rows = d.get("results") or d.get("result") or d.get("vertices") or []
        out = []
        for r in rows:
            out.append({"id": r.get("v_id") or r.get("id"), "type": r.get("v_type", vertex_type),
                        "attributes": r.get("attributes", {}), "distance": r.get("distance", r.get("score"))})
        return out

    def close(self) -> None:
        if self._session is not None:
            self._loop.call_soon_threadsafe(self._stop.set)
            self._thread.join(timeout=5)


def make_gateway(kind: str | None = None) -> Gateway:
    kind = kind or settings.graph_access
    if kind == "mcp":
        try:
            return McpGateway()
        except Exception as e:  # noqa: BLE001
            print(f"[verdict] MCP gateway unavailable ({e}); trying direct pyTigerGraph...")
    try:
        gw = DirectGateway()
        gw.c.getVer()
        return gw
    except Exception as e:  # noqa: BLE001
        print(f"[verdict] Live TigerGraph instance not reachable ({e}). Engaging High-Performance LocalGraphGateway.")
        from verdict.agent.local_graph import LocalGraphGateway
        return LocalGraphGateway()
