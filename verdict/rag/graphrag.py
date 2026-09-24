"""GraphRAG: document + case-narrative embeddings in TigerVector, and a fused retriever.

Ingestion
  * policy / pattern / regulation documents are split into clause-level chunks (DocChunk, id = DOC-<clause>)
  * closed-case narratives are embedded onto the FraudCase vertices (FraudCase.emb)
  * pattern chunks are linked to Pattern vertices (CHUNK_PATTERN)

Retrieval (``ContextPack``)
  1. semantic search over DocChunk + FraudCase vectors (installed queries rag_search_docs / rag_search_cases)
  2. structural precedent from the graph (inv_similar_cases) and case memory (inv_prior_cases)
  3. reciprocal-rank fusion + boosts for same predicted pattern -> compact, provenance-tagged context for the LLM

Embeddings: offline LSA (TF-IDF + SVD, fitted on this corpus) by default - no model download, deterministic.
``VERDICT_EMBEDDER=fastembed`` switches to BAAI/bge-small-en-v1.5 (requires internet to fetch the model).
"""
from __future__ import annotations

import pickle
import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from verdict.config import settings
from verdict.tg.client import conn

EMB_PATH = settings.work_dir / "embedder.pkl"


# ---------------------------------------------------------------- chunking
def chunk_markdown(text: str, doc_type: str, fname: str) -> list[dict]:
    chunks, section = [], ""
    clause_re = re.compile(r"^\s*((?:POL|REG|PAT)-[\d.]+[a-z]?)\b\s*(.*)")
    buf: list[str] = []
    cur_id = None

    def flush():
        if buf and (cur_id or "".join(buf).strip()):
            body = " ".join(x.strip() for x in buf if x.strip())
            if body:
                cid = cur_id or f"{fname}-{len(chunks)}"
                chunks.append({"chunk_id": f"DOC-{cid}", "doc_type": doc_type, "section": section, "text": body[:2000], "ref_id": cid})

    for line in text.splitlines():
        h = re.match(r"^#+\s*(.*)", line)
        m = clause_re.match(line.lstrip("#").strip()) if (h or clause_re.match(line)) else None
        if m:
            flush()
            buf, cur_id = [line.lstrip("# ").strip()], m.group(1)
            if h:
                section = h.group(1)
            continue
        if h:
            flush()
            section, buf, cur_id = h.group(1), [], None
            continue
        if line.strip().startswith("|") and cur_id is None and doc_type == "POLICY":
            # table rows of the action catalogue become their own chunks
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells and re.match(r"^[A-Z_]{4,}$", cells[0]):
                flush()
                chunks.append({"chunk_id": f"DOC-ACTION-{cells[0]}", "doc_type": doc_type, "section": section,
                               "text": " | ".join(cells), "ref_id": cells[0]})
                buf = []
            continue
        buf.append(line)
    flush()
    return chunks


# --------------------------------------------------------------- embedder
class LsaEmbedder:
    def __init__(self, dim: int):
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.vec = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True, stop_words="english")
        self.svd = TruncatedSVD(n_components=dim, random_state=0)
        self.dim = dim

    def fit(self, texts: list[str]):
        X = self.vec.fit_transform(texts)
        k = min(self.dim, X.shape[1] - 1, X.shape[0] - 1)
        if k < self.dim:
            from sklearn.decomposition import TruncatedSVD

            self.svd = TruncatedSVD(n_components=k, random_state=0)
        self.svd.fit(X)
        return self

    def encode(self, texts: list[str]) -> np.ndarray:
        Z = self.svd.transform(self.vec.transform(texts))
        if Z.shape[1] < self.dim:
            Z = np.hstack([Z, np.zeros((Z.shape[0], self.dim - Z.shape[1]))])
        n = np.linalg.norm(Z, axis=1, keepdims=True)
        return Z / np.maximum(n, 1e-9)


class FastEmbedder:
    def __init__(self, dim: int):
        from fastembed import TextEmbedding

        self.m = TextEmbedding("BAAI/bge-small-en-v1.5")
        self.dim = dim

    def fit(self, texts):
        return self

    def encode(self, texts):
        Z = np.array(list(self.m.embed(texts)))[:, : self.dim]
        return Z / np.maximum(np.linalg.norm(Z, axis=1, keepdims=True), 1e-9)


def load_embedder():
    return pickle.loads(EMB_PATH.read_bytes())


# ---------------------------------------------------------------- ingest
def ingest(data_dir: Path | None = None) -> dict:
    data_dir = Path(data_dir or settings.data_dir)
    smap = yaml.safe_load(Path(settings.schema_map).read_text())
    chunks: list[dict] = []
    for d in smap["files"].get("docs", []):
        p = data_dir / d["file"]
        if p.exists():
            chunks += chunk_markdown(p.read_text(), d["doc_type"], p.stem)
    cases = pd.read_csv(settings.work_dir / "prepared" / "cases_history.csv", dtype=str).fillna("")
    narratives = cases["summary"].tolist()
    emb = (FastEmbedder if settings.embedder == "fastembed" else LsaEmbedder)(settings.emb_dim)
    emb.fit([c["text"] for c in chunks] + narratives)
    EMB_PATH.parent.mkdir(parents=True, exist_ok=True)
    EMB_PATH.write_bytes(pickle.dumps(emb))
    c = conn("ops")
    if chunks:
        V = emb.encode([f"{ch['section']} {ch['text']}" for ch in chunks])
        c.upsertVertices("DocChunk", [(ch["chunk_id"], {k: ch[k] for k in ("doc_type", "section", "text", "ref_id")} | {"emb": V[i].round(5).tolist()})
                                      for i, ch in enumerate(chunks)])
        for ch in chunks:
            m = re.match(r"PAT-\d+", ch["ref_id"])
            if m:
                name = re.search(r"PAT-\d+\s+([A-Z_]+)", ch["text"])
                if name:
                    c.upsertVertex("Pattern", name.group(1), {"name": name.group(1), "status": "DOCUMENTED", "description": ch["text"][:500]})
                    c.upsertEdge("DocChunk", ch["chunk_id"], "CHUNK_PATTERN", "Pattern", name.group(1))
    CV = emb.encode(narratives) if narratives else np.zeros((0, settings.emb_dim))
    batch = []
    for i, cid in enumerate(cases["case_id"]):
        batch.append((cid, {"emb": CV[i].round(5).tolist()}))
        if len(batch) >= 500:
            c.upsertVertices("FraudCase", batch)
            batch = []
    if batch:
        c.upsertVertices("FraudCase", batch)
    return {"doc_chunks": len(chunks), "case_embeddings": len(narratives), "embedder": type(emb).__name__}


# --------------------------------------------------------------- retrieval
class Retriever:
    def __init__(self, gateway):
        self.gw = gateway
        self.emb = load_embedder() if EMB_PATH.exists() else None

    def embed(self, text: str) -> list[float]:
        return self.emb.encode([text])[0].round(5).tolist()

    def search_docs(self, text: str, k: int = 5) -> list[dict]:
        if not self.emb:
            return []
        res = self.gw.run_query("rag_search_docs", {"qv": self.embed(text), "k": k})
        r = res[0] if res else {}
        dist = r.get("distances", {})
        return [{"chunk_id": h["v_id"], **{kk.split(".")[-1]: vv for kk, vv in h["attributes"].items()},
                 "distance": dist.get(h["v_id"])} for h in r.get("hits", [])]

    def search_cases(self, text: str, k: int = 5) -> list[dict]:
        if not self.emb:
            return []
        res = self.gw.run_query("rag_search_cases", {"qv": self.embed(text), "k": k})
        r = res[0] if res else {}
        dist = r.get("distances", {})
        out = []
        for h in r.get("hits", []):
            a = {kk.split(".")[-1]: vv for kk, vv in h["attributes"].items()}
            a["cards"] = a.pop("@cards", [])
            out.append({"case_id": h["v_id"], **a, "distance": dist.get(h["v_id"])})
        return out

    def context_pack(self, query: str, facts: dict, top_pattern: str | None, exclude_case: str | None = None) -> dict:
        docs = self.search_docs(query, k=6)
        sem = [c for c in self.search_cases(query, k=8) if c["case_id"] != exclude_case]
        struct = facts.get("similar_cases", [])
        # reciprocal rank fusion over semantic + structural precedent, boosted for same pattern
        score: dict[str, float] = {}
        info: dict[str, dict] = {}
        for rank, cse in enumerate(sem):
            score[cse["case_id"]] = score.get(cse["case_id"], 0) + 1 / (60 + rank)
            info.setdefault(cse["case_id"], {}).update(cse, via=info.get(cse["case_id"], {}).get("via", []) + ["vector"])
        for rank, cse in enumerate(struct):
            score[cse["case_id"]] = score.get(cse["case_id"], 0) + 1 / (60 + rank)
            d = info.setdefault(cse["case_id"], {})
            for k, v in cse.items():
                d.setdefault(k, v)
            d["via"] = d.get("via", []) + ["graph-structure"]
        for cid, d in info.items():
            if top_pattern and d.get("pattern") == top_pattern:
                score[cid] += 0.01
                d["via"] = d.get("via", []) + ["same-pattern"]
        prec = sorted(info.values(), key=lambda d: -score[d["case_id"]])[:6]
        for p in prec:
            p["fused_score"] = round(score[p["case_id"]], 4)
            p["summary"] = (p.get("summary") or "")[:300]
        return {"policy": docs, "precedents": prec}
