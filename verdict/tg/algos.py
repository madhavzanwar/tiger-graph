"""Offline graph algorithms: card projection + TigerGraph GDS (WCC, Louvain)."""
from __future__ import annotations

import time

from verdict.tg.client import conn


def run_algorithms(max_entity_cards: int = 25) -> dict:
    c = conn("ops")
    out = {}
    t = time.time()
    c.runInstalledQuery("admin_clear_projection", {})
    time.sleep(1)
    out["projection"] = c.runInstalledQuery("admin_build_projection", {"max_entity_cards": max_entity_cards})[0]
    time.sleep(2)
    out["wcc"] = c.runInstalledQuery("tg_wcc", {"v_type_set": ["Card"], "e_type_set": ["SHARES_ENTITY"], "print_limit": 0,
                                                "print_results": False, "result_attribute": "community_id"})
    lv = c.runInstalledQuery("tg_louvain", {"v_type_set": ["Card"], "e_type_set": ["SHARES_ENTITY"], "weight_attribute": "weight",
                                            "result_attribute": "louvain_id", "print_stats": True})
    out["louvain"] = {k: v for d in lv for k, v in d.items() if k in ("FinalCommunityCount", "AllVertexCount")}
    out["secs"] = round(time.time() - t, 2)
    return out
