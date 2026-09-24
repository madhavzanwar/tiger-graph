"""TigerGraph connection helpers (pyTigerGraph)."""
from __future__ import annotations

import functools
import re

from pyTigerGraph import TigerGraphConnection

from verdict.config import settings


@functools.lru_cache(maxsize=4)
def conn(profile: str = "ops", graph: bool = True) -> TigerGraphConnection:
    user, pwd = settings.tg_user, settings.tg_password
    if profile == "investigator" and settings.tg_investigator_user:
        user, pwd = settings.tg_investigator_user, settings.tg_investigator_password
    kw = dict(host=settings.tg_host, username=user, password=pwd,
              restppPort=settings.tg_restpp_port, gsPort=settings.tg_gs_port)
    if graph:
        kw["graphname"] = settings.tg_graph
    if settings.tg_api_token:
        kw["apiToken"] = settings.tg_api_token
    return TigerGraphConnection(**kw)


_ERR = re.compile(r"(error|failed|exception|not exist|semantic check fails)", re.I)


def gsql(text: str, check: bool = True, profile: str = "ops") -> str:
    out = conn(profile, graph=False).gsql(text)
    if check and _ERR.search(out or "") and "Successfully" not in (out or ""):
        raise RuntimeError(out)
    return out


def run_query(name: str, params: dict | None = None, profile: str = "investigator", timeout: int = 60000):
    return conn(profile).runInstalledQuery(name, params or {}, timeout=timeout)
