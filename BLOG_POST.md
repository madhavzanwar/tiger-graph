# Engineering the Ultimate Agentic Fraud Investigator on TigerGraph
### How We Built VERDICT: Fusing Graph Data Science, Bayesian Decision Theory, and FinCEN SAR Automation for Hacker House Goa 2026

*By the VERDICT Team · Built for TigerGraph Hacker House Goa 2026 (IEEE-CIS Edition)*

---

## 1. The Real Challenge in Financial Fraud

In modern card payments, fraud is rarely a glaring neon sign. A $77 charge in another city could be an unauthorized card clone—or it could be a busy cardholder boarding an evening flight. 

For a Tier-1 financial institution, the central problem facing automated fraud systems isn't just *"Is this transaction suspicious?"* It is:
> **"Do we know enough to take a high-impact punitive action right now, or should we gather more evidence first?"**

- **Act too aggressively on a weak signal**: You block a legitimate cardholder's card while they are stranded abroad at a restaurant. Customer friction explodes, interchange revenue drops, and regulatory safeguards against unwarranted blocks (Policy R1) are violated.
- **Hesitate too long**: A stolen credential ring executes high-velocity cash-outs, transferring tens of thousands of dollars before perimeter controls react.

Most AI agent hackathon submissions answer this trade-off with **LLM vibes**—prompting a language model to guess whether to block or allow based on loose text instructions.

In this project, we built **VERDICT** (*Value-of-Information Evidence Reasoning & Decision Intelligence for Card Transactions*). We replaced LLM guesswork with:
1. **Calibrated Bayesian Evidence Accounting**: Log-odds additive ledger with 80% credible intervals.
2. **Decision-Theoretic Value of Information (VOI)**: Calculating the Expected Value of Sample Information (EVSI) in dollars before contacting customers.
3. **Graph Data Science on TigerGraph**: Weakly Connected Components (WCC), Louvain community detection, and PageRank across 26,000+ real transactions.
4. **Zero-Hallucination FinCEN SAR Automation**: Programmatic claim checking against graph ground truth.
5. **100% Benchmark Compliance**: Achieving a flawless 20/20 on the official IEEE-CIS hackathon exam pack.

---

## 2. System Architecture: The Cyclic State Machine

VERDICT implements a cyclic finite state machine designed around operational banking compliance:

```
[TRIGGER INGESTION] (Risk Score / Customer Dispute / Analyst Request)
         │
         ▼
[GRAPH INVESTIGATION] (14 GSQL Queries via TigerGraph MCP)
         │
         ▼
[BAYESIAN EVIDENCE LEDGER] (Calibrated Log-Odds Decomposition + Bootstrap CI)
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

---

## 3. Four Core Architectural Innovations

### Innovation 1: The Calibrated Bayesian Evidence Ledger
Rather than allowing an LLM to hallucinate risk percentages, VERDICT computes a rigorous log-odds evidence ledger:
$$\text{logit} \, P(\text{fraud}) = \beta_0 + w_{\text{risk}} \cdot \text{logit}(\text{risk\_score}) + \sum_{i} w_i \cdot \text{signal}_i + \sum_{j} \text{LLR}(\text{evidence}_j)$$

- $\beta_0$: Calibrated prior base rate of fraud from historical closed cases.
- $w_{\text{risk}}$: Bank real-time model feature weight.
- $w_i \cdot \text{signal}_i$: GSQL query signals (e.g. `region_novel_card_present`, `ct_small_burst`, `ring_linked_high_risk`).
- $\text{LLR}(\text{evidence}_j)$: Empirical log-likelihood ratio of evidence responses (e.g. cardholder denial vs. confirmation).

To quantify uncertainty, we compute **200 bootstrap refits** of the parameter distribution, reporting a calibrated **80% Credible Interval (`ci80`)** and a **Decision Stability Metric**.

### Innovation 2: Value of Information (VOI) & Stopping Rules
Evidence gathering has operational costs: customer friction, SMS gateway fees, and analyst time. The agent computes the **Expected Value of Sample Information (EVSI)**:
$$\text{EVSI}(X) = \mathbb{E}_x \left[ \min_a \mathbb{E}_{y|x}[\mathcal{L}(a, y)] \right] - \min_a \mathbb{E}_y[\mathcal{L}(a, y)]$$

- If $\text{EVSI}(X) - \text{Cost}(X) > 0$ and the outcome could change the optimal policy action, the agent triggers `VERIFY_WITH_CUSTOMER` or `STEP_UP_AUTH`.
- If $\text{EVSI}(X) \le \text{Cost}(X)$, further investigation is financially unjustifiable: the agent halts immediately and executes the defensible decision.

### Innovation 3: Graph Data Science & Topology Algorithms
Payment fraud is organized in syndicated rings. We executed 14 installed GSQL queries on TigerGraph:
- **`inv_community`**: Weakly Connected Components and Louvain modularity identifying clusters of cards sharing emulated device fingerprints.
- **`inv_card_velocity`**: 24-hour sliding transaction windows detecting micro-testing authorizations.
- **`inv_geographic_spread`**: Implied velocity travel anomalies detecting simultaneous in-person transactions across impossible distances.
- **`inv_identity_consistency`**: Match flag discrepancies and email domain alterations indicating Account Takeover (ATO).

### Innovation 4: Anti-Hallucination Claim-Checked SAR Generation
When Policy R2 or R6 mandates filing a regulatory Suspicious Activity Report (`FILE_REPORT`), VERDICT drafts a 7-point narrative (Subject, Timeline, Geography, Channels, Graph Linkages, Exposure, Disposition).

Before the report is finalized, `verdict/outputs/claim_checker.py` extracts every entity identifier, monetary amount, date, and card token, validating them against the graph context. If any hallucinated assertion is detected, the report immediately falls back to a verified deterministic template.

---

## 4. Benchmark Results: 100% Evaluation Compliance

We evaluated VERDICT against the true official IEEE-CIS benchmark dataset (`case_pack.csv`):

```
==========================================================================================
OFFICIAL HACKATHON EVALUATION SUITE: VALIDATING 20 CASES IN cases/
==========================================================================================
Case      | Verdict      | Pattern                      | Prob  | Exposure   | SAR   | Status
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

## 5. What We Learned

Building an enterprise-ready AI investigator taught us three enduring lessons:
1. **Never let an LLM do mathematics**: Language models are exceptional at summarizing evidence, formulating hypotheses, and drafting regulatory narratives. They should never be responsible for computing probabilities, calculating loss functions, or routing policy approvals.
2. **Graph databases are essential for fraud**: Single-row relational tables miss 90% of fraud context. The difference between an ordinary customer and a card-testing syndicate is found in multi-hop entity sharing across device fingerprints and billing regions.
3. **Turnkey resilience is mandatory**: Hackathon judges and production operators need systems that run anywhere, anytime. Our Dual-Engine Graph Gateway guarantees seamless fallback between live TigerGraph Savanna and high-speed local graph traversal without dropping a beat.

---

## 6. Try It Out

```bash
# 1. Run the benchmark across all 20 cases
python -m verdict.cli benchmark

# 2. Run the official schema test suite
python validate_all_benchmark_cases.py

# 3. Launch the full-stack analyst cockpit
python -m verdict.cli serve
```

Visit the GitHub repository to inspect the code, explore the GSQL algorithms, and try the interactive analyst cockpit!
