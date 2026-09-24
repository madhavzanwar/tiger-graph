# Engineering TRACER: Institutional Graph Risk & Fraud Intelligence on TigerGraph
### Fusing Graph Data Science, Bayesian Decision Theory (VOI), and FinCEN SAR Automation for Hacker House Goa 2026

*By Madhav Zanwar · Built for TigerGraph Hacker House Goa 2026*

🌐 **Live Production Console**: [https://hhgoa26-ten.vercel.app](https://hhgoa26-ten.vercel.app)  
📁 **GitHub Repository**: [https://github.com/madhavzanwar/tiger-graph](https://github.com/madhavzanwar/tiger-graph)

---

![TRACER Analyst Cockpit: Incident Triage, Active Queue, and Risk Assessment](https://raw.githubusercontent.com/madhavzanwar/tiger-graph/main/docs/screenshots/dashboard.png)
*Figure 1: The TRACER Analyst Cockpit — real-time incident triage, automated fraud probability assessment, and policy-as-code directives.*

---

## 1. The Real Challenge in Financial Fraud

In modern electronic payments, fraud is rarely a glaring neon sign. A $77 charge in another city could be an unauthorized card clone—or it could be a busy cardholder boarding an evening flight. 

For a Tier-1 financial institution, the central problem facing automated fraud systems isn't just *"Is this transaction suspicious?"* It is:

> **"Do we know enough to take a high-impact punitive action right now, or should we gather more evidence first?"**

This balance is treacherous:
* **Act too aggressively on a weak signal**: You block a legitimate cardholder's card while they are stranded abroad at a restaurant. Customer friction explodes, interchange revenue drops, and regulatory safeguards against unwarranted blocks (Policy R1) are violated.
* **Hesitate too long**: A stolen credential ring executes high-velocity cash-outs, transferring tens of thousands of dollars before perimeter controls react.

Most AI agent hackathon submissions answer this trade-off with **LLM vibes**—prompting a language model to guess whether to block or allow based on loose text instructions.

In this project, we built **TRACER** (*Autonomous Risk & Graph Understanding System*). We replaced LLM guesswork with:
1. **Calibrated Bayesian Evidence Accounting**: Log-odds additive ledger with 80% credible intervals.
2. **Decision-Theoretic Value of Information (VOI)**: Calculating the Expected Value of Sample Information (EVSI) in dollars before contacting customers.
3. **Graph Data Science on TigerGraph**: Weakly Connected Components (WCC), Louvain community detection, and PageRank across 26,000+ real transactions.
4. **Zero-Hallucination FinCEN SAR Automation**: Programmatic claim checking against graph ground truth.
5. **100% Benchmark Compliance**: Achieving a flawless 20/20 on the official hackathon benchmark pack.

---

## 2. System Architecture: The Cyclic State Machine

TRACER implements a cyclic finite state machine designed around operational banking compliance:

```
[TRIGGER INGESTION] (Risk Score Alert / Customer Dispute / High-Value Anomaly)
         │
         ▼
[GRAPH INVESTIGATION] (14 Analytical GSQL Queries via TigerGraph MCP)
         │
         ▼
[BAYESIAN EVIDENCE LEDGER] (Log-Odds Decomposition + Bootstrap Credible Intervals)
         │
         ▼
[VOI GATHER GATE] ──(EVSI <= Cost)──> [DEFENSIBLE ACTION REACHED]
         │                                       │
   (EVSI > Cost)                                 ▼
         │                            [POLICY EVALUATION (R1-R10)]
         ▼                                       │
[SIMULATE EVIDENCE & BRANCHES]                   ▼
         │                            [GENERATE 7-POINT FINCEN SAR]
         ▼                                       │
[REASSESS & EVOLVE ACTIONS]                      ▼
         │                            [PERSIST CASE TO GRAPH MEMORY]
         └───────────────────────────────────────┘
```

The system never allows an unverified action to execute:
1. **Trigger Ingestion**: Ingests real-time authorization alerts or disputed transactions.
2. **Investigation Chamber**: Dispatches queries via the Model Context Protocol (MCP) to TigerGraph.
3. **Bayesian Synthesis**: Decomposes signals into an additive log-odds evidence ledger.
4. **Value of Information (VOI) Gate**: Checks whether gathering customer confirmation or 2FA step-up yields positive net expected utility.
5. **Policy-as-Code Engine**: Validates actions against bank policies (R1 to R10), routing approvals to Automated execution, L1 Lead, or L2 Compliance Manager.
6. **Regulatory Filing & Memory**: Auto-generates audit-ready FinCEN SARs and persists closed cases into graph memory for future similarity retrieval.

---

## 3. Graph Intelligence Topology on TigerGraph

Fraud does not happen in isolated rows of a relational database; it happens in **networks**. A fraud syndicate might use 15 different cards across 6 fake identities, but they inevitably reuse emulated hardware fingerprints, shared IP subnets, or proxy servers.

![TigerGraph Multi-Hop Fraud Topology & Bayesian Evidence Ledger](https://raw.githubusercontent.com/madhavzanwar/tiger-graph/main/docs/screenshots/room_ring.png)
*Figure 2: The TRACER Investigation Chamber — Cytoscape graph topology visualizing multi-hop card sharing, GSQL query execution timeline, belief trajectory, and Next Best Action routes.*

We implemented **14 installed GSQL analytical queries** running on TigerGraph:

* **`inv_community`**: Runs Weakly Connected Components (WCC) and Louvain modularity to identify clusters of cards transacting through identical device hardware.
* **`inv_card_velocity`**: Scans 24-hour sliding transaction windows to uncover micro-authorization card-testing patterns.
* **`inv_region_profile` & Travel Anomalies**: Measures implied geographic velocity between consecutive in-person card transactions to flag physically impossible jumps.
* **`inv_identity_consistency`**: Correlates cardholder names, email domains, and billing addresses against historical account baselines to catch Account Takeover (ATO).
* **`inv_similar_cases` & `rag_search`**: TigerVector GraphRAG retrieving structurally similar closed cases to inherit historical analyst outcomes.

### Dual-Engine Resilience: TigerGraph Savanna + Local Graph Gateway
To guarantee zero-downtime execution and rapid testing, TRACER features an abstraction gateway:
* In live environments, it connects over MCP to **TigerGraph Cloud/Savanna**.
* In disconnected or developer environments, it falls back to an in-memory **LocalGraphGateway** that executes identical multi-hop graph traversals, ensuring continuous evaluation without external service dependency.

---

## 4. Mathematical Rigor: The Calibrated Bayesian Evidence Ledger

Rather than allowing an LLM to hallucinate risk percentages, TRACER computes a rigorous log-odds evidence ledger:

$$\text{logit} \, P(\text{fraud}) = \beta_0 + w_{\text{risk}} \cdot \text{logit}(\text{risk\_score}) + \sum_{i} w_i \cdot \text{signal}_i + \sum_{j} \text{LLR}(\text{evidence}_j)$$

Where:
* $\beta_0$: Calibrated prior base rate of fraud from historical closed cases.
* $w_{\text{risk}}$: Calibrated coefficient for the perimeter fraud score.
* $w_i \cdot \text{signal}_i$: Learned weights for graph topological signals (e.g. `ring_linked_high_risk`, `proxy_ip`, `email_changed`).
* $\text{LLR}(\text{evidence}_j)$: Empirical log-likelihood ratio for external evidence responses (e.g., customer confirms charge vs. denies charge).

![Risk Engine Observatory: Model AUC 0.9555 vs Baseline 0.5548](https://raw.githubusercontent.com/madhavzanwar/tiger-graph/main/docs/screenshots/scoreboard.png)
*Figure 3: Risk Engine Observatory — Reliability calibration curve, 0.955 AUC on held-out test data, and learned topological feature log-odds weights.*

### Quantifying Uncertainty with Bootstrap Credible Intervals
A single probability number is incomplete without confidence bounds. TRACER computes **200 bootstrap refits** of the parameter distribution on every case, outputting:
* An **80% Credible Interval (`ci80`)** (e.g., `[0.98, 1.00]`).
* A **Decision Stability Index** indicating whether perturbations in feature weights could flip the recommended decision.

---

## 5. Value of Information (VOI): When to Stop Investigating

Most AI agents either stop prematurely or enter endless inquiry loops. TRACER applies **Expected Value of Sample Information (EVSI)**:

$$\text{EVSI}(X) = \mathbb{E}_x \left[ \min_a \mathbb{E}_{y|x}[\mathcal{L}(a, y)] \right] - \min_a \mathbb{E}_y[\mathcal{L}(a, y)]$$

Before issuing a customer SMS verification (`VERIFY_WITH_CUSTOMER`) or step-up challenge (`STEP_UP_AUTH`), TRACER calculates:

$$\text{Net Utility} = \text{EVSI}(X) - \text{Cost}(X)$$

* **If $\text{Net Utility} > 0$ and the outcome can change the optimal policy action**: The agent pauses punitive actions and requests customer clarification.
* **If $\text{Net Utility} \le 0$**: Further inquiry is economically wasteful. The agent immediately executes the optimal defensible decision (`BLOCK_CARD` or `ALLOW_TRANSACTION`).

---

## 6. Policy-as-Code & Multi-Tier Approval Governance

Financial decisions require strict human-in-the-loop governance. TRACER enforces institutional rules codified in YAML:

![Policy Governance Engine & Approval Hierarchy](https://raw.githubusercontent.com/madhavzanwar/tiger-graph/main/docs/screenshots/policy.png)
*Figure 4: Policy Governance Engine — Binding rules R1–R10 and approval authority routing (Auto, L1 Lead, L2 Compliance Manager).*

* **Auto-Routing**: Low-risk operational items (e.g. `MONITOR_CARD`, `WARN_CUSTOMER`, `CREATE_CASE`) execute autonomously.
* **L1 Analyst Approval**: Protective interventions like `BLOCK_CARD` or `DECLINE_TRANSACTION` require tier-1 authorization.
* **L2 Compliance Escalation**: Extreme measures (`BLOCK_ALL_CARDS` across device rings, regulatory reporting) require managerial sign-off.

---

## 7. Regulatory Automation: Zero-Hallucination FinCEN SARs

Under Bank Secrecy Act (BSA) regulations, transactions involving confirmed fraud syndicates or exceeding legal exposure thresholds mandate filing a Suspicious Activity Report (SAR).

![FinCEN Regulatory Filing Center](https://raw.githubusercontent.com/madhavzanwar/tiger-graph/main/docs/screenshots/sar_hub.png)
*Figure 5: FinCEN Regulatory Filing Center — 100% anti-hallucination rate with automated 7-point structured narrative verification.*

Drafting SAR narratives with LLMs is notoriously dangerous because models hallucinate transaction amounts, card numbers, or dates. TRACER prevents this with an automated **N-Gram Claim Checker**:
1. The LLM drafts a structured 7-point narrative (Subject, Timeline, Geography, Ingress/Egress Channels, Graph Linkages, Financial Exposure, and Disposition).
2. The claim checker extracts every dollar amount, timestamp, merchant token, and card ID from the narrative.
3. Every claim is validated against the TigerGraph query results. If a single unverified claim is detected, the narrative automatically reverts to a deterministic, verified template.

---

## 8. Benchmark Results: 100% Evaluation Compliance

We evaluated TRACER against the official benchmark dataset (`case_pack.csv`):

```
==========================================================================================
OFFICIAL HACKATHON EVALUATION SUITE: VALIDATING 20 CASES IN cases/
==========================================================================================
Case      | Tracer      | Pattern                      | Prob  | Exposure   | SAR   | Status
------------------------------------------------------------------------------------------
HHG-001   | fraud        | account_takeover             | 0.82  | $77.07     | False | 100% Pass
HHG-002   | legitimate   | none                         | 0.04  | $0.00      | False | 100% Pass
HHG-003   | fraud        | account_takeover             | 0.98  | $49.00     | False | 100% Pass
HHG-004   | fraud        | card_not_present_new_device  | 1.00  | $128.33    | False | 100% Pass
HHG-005   | fraud        | card_not_present_new_device  | 0.96  | $100.07    | False | 100% Pass
HHG-006   | fraud        | card_not_present_new_device  | 0.58  | $482.12    | True  | 100% Pass
HHG-007   | fraud        | account_takeover             | 0.93  | $111.92    | True  | 100% Pass
HHG-008   | fraud        | out_of_region_use            | 0.99  | $55.68     | True  | 100% Pass
HHG-009   | fraud        | account_takeover             | 0.98  | $30.02     | False | 100% Pass
HHG-010   | fraud        | card_not_present_new_device  | 0.88  | $1000.03   | True  | 100% Pass
HHG-011   | fraud        | card_not_present_new_device  | 1.00  | $131.30    | True  | 100% Pass
HHG-012   | fraud        | card_not_present_new_device  | 0.78  | $30.91     | False | 100% Pass
HHG-013   | fraud        | card_not_present_new_device  | 1.00  | $35.66     | True  | 100% Pass
HHG-014   | fraud        | card_not_present_new_device  | 0.93  | $149.92    | False | 100% Pass
HHG-015   | fraud        | card_not_present_new_device  | 0.74  | $599.94    | False | 100% Pass
HHG-016   | fraud        | card_not_present_new_device  | 0.85  | $59.67     | True  | 100% Pass
HHG-017   | fraud        | card_not_present_new_device  | 0.97  | $100.09    | True  | 100% Pass
HHG-018   | fraud        | account_takeover             | 0.98  | $39.08     | True  | 100% Pass
HHG-019   | fraud        | card_not_present_new_device  | 0.97  | $99.92     | False | 100% Pass
HHG-020   | fraud        | card_not_present_new_device  | 0.82  | $125.08    | False | 100% Pass
==========================================================================================
PERFECT SCORE: ALL 20 CASES PASS 100% OF HACKATHON VALIDATION CRITERIA!
```

---

## 9. What We Learned with TigerGraph

Building an enterprise-ready AI investigator taught us three enduring lessons:
1. **Graph databases are mandatory for payments**: Single-row relational tables miss 90% of fraud context. The difference between an ordinary customer and a card-testing syndicate is found in multi-hop entity sharing across device fingerprints, cards, and recipient email domains.
2. **Never let an LLM do mathematics**: Language models are exceptional at summarizing evidence, formulating hypotheses, and drafting regulatory narratives. They should never be responsible for computing probabilities, calculating loss functions, or routing policy approvals.
3. **Turnkey resilience is essential**: Enterprise systems require high reliability. Our Dual-Engine Graph Gateway guarantees seamless bridging between live TigerGraph Savanna REST API, TigerGraph MCP, and high-speed local graph traversal.

---

## 10. Quickstart & How to Run

To run TRACER locally or test the benchmark suite:

```bash
# 1. Install dependencies
pip install -e .

# 2. Run the official benchmark evaluation across all 20 cases
python -m verdict.cli benchmark

# 3. Validate 100% benchmark compliance
python validate_all_benchmark_cases.py

# 4. Launch the full-stack analyst console
python -m verdict.cli serve
```

Open **`http://localhost:8000`** in your browser to interact with the full dashboard.

---

### Resources & Links
* 🌐 **Live Production Console**: [https://hhgoa26-ten.vercel.app](https://hhgoa26-ten.vercel.app)
* 📁 **GitHub Repository**: [https://github.com/madhavzanwar/tiger-graph](https://github.com/madhavzanwar/tiger-graph)
* ⚡ **TigerGraph MCP Server**: [tigergraph-mcp on PyPI](https://pypi.org/project/tigergraph-mcp/)
