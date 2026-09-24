# VERDICT: 3-Minute Video Demo Presentation Script
### TigerGraph Agentic Fraud Investigation Hackathon (Hacker House Goa 2026)

**Presenter:** Lead Investigator / Systems Architect  
**Duration:** 3 Minutes (180 seconds)  
**Target Video Screen:** Split screen showing the **VERDICT Analyst Cockpit UI (`http://localhost:8000`)** and **Terminal**.

---

## [0:00 - 0:30] Hook & The Core Problem

**[Visual: Terminal running `python -m verdict.cli serve`, browser opening to `http://localhost:8000` showing the live Case Queue.]**

**Speaker:**
> "In financial fraud investigation, the hardest question isn't *'Is this transaction suspicious?'*  
> It's: **'Do we know enough to act right now, or should we gather more evidence first?'**
> 
> Block a card too aggressively on a single weak signal, and you breach bank policy by stranding a legitimate customer abroad. Wait too long, and a syndicated card-testing ring cashes out tens of thousands of dollars.
> 
> Most AI agents answer this trade-off with pure guesswork. Today, we're presenting **VERDICT**—an autonomous, graph-native fraud investigation system on TigerGraph that replaces LLM guesswork with **Bayesian Decision Theory**, **Graph Data Science**, and **strict regulatory compliance**."

---

## [0:30 - 1:15] Deep-Dive: Live Case Investigation (HHG-001 & HHG-005)

**[Visual: In the UI, click on case `HHG-001` (flagged transaction 3514030, $77.07, score 0.61).]**

**Speaker:**
> "Let's investigate case **HHG-001**. A real-time risk score fired at 0.61. A single model score is an alert—never a verdict.
> 
> Watch the agent work:
> 1. It calls TigerGraph through the **Model Context Protocol (MCP)**, executing 14 installed GSQL queries across sliding 24-hour windows, device sharing, and geographic velocity.
> 2. Look at this **Evidence Ledger**: every query result is decomposed into an additive log-odds contribution. It uncovers that the purchaser email domain has never been seen on this account (+1.62 log-odds) and Weakly Connected Components (WCC) reveals that a linked card in its component has confirmed fraud (+0.81 log-odds).
> 3. Instead of guessing, VERDICT computes the posterior probability: **0.82**, bounded by an 80% credible interval [0.80 - 0.84] across 200 bootstrap refits."

**[Visual: Click on the "Next-Best-Actions" tab in the Cockpit.]**

**Speaker:**
> "Notice the **Decision-Theoretic Stopping Rule**: because the expected financial loss of releasing ($507.97) vastly exceeds the cost of protecting ($21.90), and no further evidence inquiry has positive Expected Value of Sample Information (EVSI), the agent stops immediately.
> 
> It recommends an initial action of `CREATE_CASE` (auto) and `BLOCK_CARD` (L1 human approval), satisfying Bank Policy R2 without unnecessary customer friction."

---

## [1:15 - 1:50] The FinCEN SAR & Cross-Card Ring Detection (HHG-006 & HHG-010)

**[Visual: Navigate in the UI to case `HHG-010` ($1,000.03 online transaction from new device) and open the FinCEN SAR Modal.]**

**Speaker:**
> "Now let's examine high-exposure and syndicated cases like **HHG-010**.
> 
> Because exposure exceeds the $1,000 regulatory threshold and connects to an anomalous hardware device profile, bank policy mandates filing a regulatory Suspicious Activity Report (`FILE_REPORT`).
> 
> Look at the **FinCEN SAR Dossier**:
> - It drafts a complete 7-point narrative covering subject identity, timeline, channels, and graph linkages.
> - Crucially, our **Zero-Hallucination Claim Checker** validates every single dollar amount, timestamp, customer ID, and card number against graph ground truth before filing.
> - Actions are automatically routed: `BLOCK_CARD` waits for Team Lead L1 approval, and `FILE_REPORT` routes to Level-2 Fraud Management approval."

---

## [1:50 - 2:30] Official Benchmark Compliance & Validation (20/20 Passed)

**[Visual: Switch to Terminal and run `python validate_all_benchmark_cases.py`.]**

**Speaker:**
> "We didn't just test on synthetic data. VERDICT is evaluated against the **official 26,000-transaction IEEE-CIS Hackathon benchmark dataset**.
> 
> Let's run our automated test suite across all 20 exam cases in `cases/`."

**[Visual: Output streams across the terminal, displaying all 20 cases with `OK (Passed 100%)` and the banner `PERFECT SCORE: ALL 20 CASES PASS 100% OF HACKATHON VALIDATION CRITERIA!`.]**

**Speaker:**
> "Every single case passed with zero validation errors:
> - 100% schema compliance with top-level fields, initial and final next-best actions, and what-changed deltas.
> - Perfect SAR synchronization matching `FILE_REPORT`.
> - Defensible Policy R1–R10 enforcement.
> - And sub-second response times powered by our resilient Dual-Engine Graph Gateway."

---

## [2:30 - 3:00] Conclusion & Why It Wins

**[Visual: Return to the Analyst Cockpit, panning over the interactive Cytoscape graph canvas.]**

**Speaker:**
> "VERDICT proves that enterprise AI agents don't have to be opaque, hallucinating black boxes.
> 
> By fusing:
> - **TigerGraph's high-speed GSQL analytics**,
> - **Bayesian log-odds evidence ledgers**,
> - **Value of Information decision theory**, and
> - **Zero-hallucination compliance checking**,
> 
> VERDICT delivers a turnkey, 100% compliant solution that turns uncertain signals into defensible, audit-ready banking decisions.
> 
> Thank you, and explore our repository on GitHub!"
