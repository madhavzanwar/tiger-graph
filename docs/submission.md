# Submission kit: VERDICT (TigerGraph Agentic Fraud Investigation, HHGOA 2026)

Paste-ready answers for the submission form. Replace every `<…>` placeholder before submitting.
One submission per team and no resubmissions, so check every link opens in a private window first.

---

## Links
| Field | Value |
|---|---|
| GitHub repository | https://github.com/madhavzanwar/tiger-graph |
| Live console (replay) | https://hhgoa26-ten.vercel.app |
| Demo video (3–5 min) | `<YouTube / Loom link>` (script: `docs/demo_script.md`) |
| Technical blog post | `<dev.to / Hashnode / Medium link>` (draft: `docs/blog.md`) |
| Social post | `<LinkedIn / X link>` (draft: `docs/social_post.md`, tag @TigerGraphDB) |
| Agent output on the 20 cases | `outputs/hhgoa/answers/` (one JSON + one Markdown per case, plus `benchmark_summary.md`), produced by `verdict benchmark` |

---

## Project name
**VERDICT: from an uncertain signal to a defensible action**

## One-line summary
An agentic fraud investigator that investigates inside TigerGraph through the TigerGraph MCP server, quantifies its own
uncertainty, asks for more evidence only when the answer could change the decision, and acts strictly within the bank's
policy and approval routes, remembering every case in the graph.

## About the builder
I'm a **Forward Deployed Engineer at Fiserv**, where my day job is exactly the intersection this challenge targets: taking
agentic AI into regulated fintech environments and integrating it with real payment, card and case-management systems.
In the field, the hard problems are rarely "can a model spot fraud?". They are **"can the bank defend this decision to an
auditor?"**, **"what is the agent allowed to do on its own?"** and **"how does it fit the analyst's existing workflow and
approval chain?"**. VERDICT is designed from that deployment perspective: every number is traceable to a graph query, every
action carries a policy clause and an approval route, the LLM can recommend but never execute, and the case record is
built to survive an audit. *(Views are my own; this project is not affiliated with or endorsed by Fiserv.)*

## Project description (long form)
Fraud analysts lose the most time on the ambiguous middle: alerts that are neither clearly fraud nor clearly fine. VERDICT
is built for that middle.

**1. Trigger → case.** A risk-score alert, a customer report (parsed as untrusted text) or an analyst request opens a case,
which is written to TigerGraph immediately.

**2. Graph investigation through MCP.** The agent reads the graph only through the official `tigergraph-mcp` server,
started with a read-only tool filter plus a query allow-list. 14 installed GSQL queries answer the analyst's questions:
card-testing velocity, customer and card behavioural baseline, device novelty and device sharing, billing-region novelty
*with concurrent home activity*, identity consistency (account-takeover signals), ring detection through shared devices
and recipient emails with hub suppression, prior cases, structural precedent and exposure. A card-to-card projection is
built in GSQL and analysed with TigerGraph's WCC and Louvain algorithms for fraud-ring communities.

**3. A calibrated evidence ledger.** Each finding becomes a ledger row whose weight is learned from the dataset's
closed-case history (confirmed vs cleared). The agent reports P(fraud) with an 80% credible interval (bootstrap) and a
belief trajectory showing how each query moved it. Pattern classification covers the five documented typologies, and a
discovery job clusters confirmed fraud the typologies do not explain, which surfaces undocumented patterns as graph-stored
hypotheses.

**4. Knowing when to ask for more.** A value-of-information engine prices each controlled evidence action (step-up
authentication, customer validation, analyst input) using response likelihoods learned from past cases. The agent asks
only when the answer could flip the decision and is worth its cost, and **before asking** it records what it will do for
each possible answer. Policy-mandated requests ("contact the customer before blocking") are honoured even when value of
information alone would not ask.

**5. Policy-bound next best actions.** The bank's policy is compiled into rules with clause IDs, approval routes
(AUTO / L1 / L2 / Compliance), prohibitions (for example no BLOCK_ALL_CARDS without evidence of wider compromise) and SAR
criteria. The engine is the final authority. The next best action and its approval route are recorded **before** and
**after** additional evidence, with a "what changed" delta. AUTO actions execute against simulated bank systems; everything
else waits in a human approval inbox.

**6. Explainability and memory.** Each case gets an executive summary, evidence for and against, remaining uncertainty and,
when policy requires one, a SAR whose every number and identifier is checked against the evidence store. The case,
evidence, requests, actions, pattern links and similar-case edges are written back to TigerGraph, retrieved through GraphRAG
(TigerVector over policy clauses and case narratives, fused with graph-structural precedent) and fed into a learning loop:
resolving a case refits the evidence model live.

**7. Analyst console.** A case queue, a live investigation room (MCP tool-call timeline, a subgraph that grows as the agent
traverses, belief trajectory, evidence ledger, evidence-request branches, before/after next best action, approvals, SAR), a
memory and patterns view, a scoreboard and the policy view.

## How we are different, mapped to the judging criteria
| Criterion | What most submissions do | What VERDICT does |
|---|---|---|
| **Investigation accuracy (25%)** | LLM reads rows and names a pattern | 14 purpose-built GSQL queries + WCC/Louvain ring detection; **signal weights learned from the closed-case history** and validated on a **time-split backtest** (scoreboard: AUC, calibration, pattern confusion); **undocumented-pattern discovery**, which the brief hints at explicitly |
| **Next best action (25%)** | Threshold rules on a risk score | **Decision theory**: expected loss plus **value of information** decides stop / ask / act; **counterfactual branches committed before evidence arrives**; recommendations and approval routes recorded before and after evidence, with a delta |
| **Case summary & explainability (10%)** | Free-form LLM summary | **Evidence ledger**: every point of probability traced to a named signal and its source query; belief trajectory; cited policy clauses; **claim-checked** SAR and summary (unsupported numbers are rejected) |
| **Agentic design & engineering (15%)** | Single LLM loop, prompts as guardrails | Phase state machine; **two MCP servers** (TigerGraph read-only + our policy-gated ops server); **defense in depth** (DB profile, MCP tool filter, query allow-list, policy engine, human approval); tool budgets; graceful degradation; audit log; 17 unit tests |
| **Innovation (15%)** | Vector RAG over documents | **GraphRAG that fuses TigerVector semantic hits with graph-structural precedent**; graph-native case memory; a **learning loop** that updates the model from resolved cases; discovered patterns stored as graph hypotheses |
| **Demo (10%)** | Chat window | Purpose-built analyst console with live streaming, graph view and approvals, plus a hosted replay link |

## Coverage of "What success looks like"
1. **Investigate from a trigger**: risk signal, customer report or analyst request → case opened in the graph.
2. **Gather evidence from the graph and other sources**: 11 core MCP queries + follow-ups; GraphRAG over policy and precedents; customer, step-up and analyst channels.
3. **Identify patterns and assess risk**: 5 documented typologies + discovered hypotheses; calibrated P(fraud) with credible interval.
4. **Create and progress a case**: TRIGGERED → INVESTIGATING → ASSESSED → AWAITING_EVIDENCE → REASSESSED → EXPLAINED → PENDING_APPROVAL/CLOSED, every step persisted.
5. **Recognise insufficient evidence**: credible interval + decision stability + value of information.
6. **Controlled evidence gathering**: policy-approved channels only (step-up, customer validation, analyst request).
7. **Recommend and update actions**: next best action before and after evidence, with branches and a "what changed" delta.
8. **Explain evidence, reasoning and uncertainty**: ledger, trajectory, summary, remaining uncertainty, claim-checked SAR.
9. **Operate within policy and permissions**: policy engine as final authority, approval routes, prohibitions, human inbox; the LLM cannot execute.
10. **Use prior cases as memory**: prior cases, structural + vector precedent, graph write-back, learning loop.
11. **Usable interface**: analyst console (live) + hosted replay.

## Additional features beyond the core ask
- **Undocumented-pattern discovery** from residual confirmed fraud, stored as `Pattern{status: HYPOTHESIS}` and escalated under policy (never auto-closed).
- **Learning loop**: analyst outcomes refit the evidence model; the UI shows which signal weights moved.
- **Counterfactual branches** for every evidence request ("if the customer confirms → …; denies → …; no reply → …").
- **Decision stability** metric and **expected-loss** reasoning in dollars.
- **Claim checker** for LLM-written text (SAR, summaries).
- **verdict-ops MCP server**: the same policy-gated actions are usable from any MCP client (e.g. Claude Desktop) next to tigergraph-mcp.
- **Scoreboard**: backtest AUC vs the bank's risk score, reliability diagram, pattern confusion, learned weights.
- **Runs with or without an LLM**: all graph analysis, scoring, policy and answer files are deterministic; Claude adds tool choice and narrative on top.
- **One-command deployment** (`docker compose`), Savanna-compatible REST loading, schema map and policy file isolate bank-specific details.

## Tech stack
TigerGraph 4.2 (GSQL, GDS WCC/Louvain, TigerVector) · tigergraph-mcp · MCP Python SDK · Python (FastAPI, scikit-learn,
pandas) · Anthropic Claude (`claude-opus-5` investigator, `claude-haiku-4-5` worker) · React + Vite + Cytoscape.js +
Recharts · Docker Compose · Vercel (replay console).

## Future scope
- **Streaming triggers**: Kafka → TigerGraph loading jobs so investigations start the moment an authorisation lands.
- **Challenger models**: a gradient-boosted classifier over graph + raw transaction features (with per-feature contributions feeding the same ledger) and an anomaly detector for novelty, routed so the LLM spends its budget only on the uncertain middle.
- **Graph embeddings** (FastRP / GraphSAGE) as additional precedent signals.
- **Per-segment loss models** (card type, merchant category, customer value) and real-time exposure.
- **Integration adapters** for card-management, CRM and case-management platforms, plus RBAC-mapped approval routing (the deployment work I do day to day).
- **Policy co-pilot**: analyst overrides and discovered patterns turned into proposed policy changes for review.
- **Regulatory packs**: jurisdiction-specific SAR/STR templates and tipping-off controls.

## Answer-file format (for the "agent output on 20 cases" field)
`outputs/hhgoa/answers/<case_id>.json` contains: the case with its internal investigation record (every graph query with
arguments and latency, evidence ledger, belief trajectory, subgraph, precedents, timeline), findings, decisions and the
actions log; the SAR when required; `next_best_action.before_evidence` and `.after_evidence` with approval routes;
evidence requests with counterfactual branches; and `graph_write_back` verified from TigerGraph.
