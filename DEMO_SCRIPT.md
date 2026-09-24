# TRACER: 3–5 Minute Video Demo Presentation Script
### TigerGraph Agentic Fraud Investigation Hackathon (Hacker House Goa 2026)

**Presenter:** Lead Systems Architect / Fraud Investigator  
**Duration:** 3–5 Minutes (180–300 seconds)  
**Target Video Screen:** Full-screen walkthrough of the live **TRACER Risk Platform UI (`http://localhost:8000` or `https://hhgoa26-ten.vercel.app`)** with terminal validation.
---

## [0:00 - 0:45] Hook & The Core Dilemma

**[Visual: Open browser to `https://hhgoa26-ten.vercel.app` showing the clean TRACER Triage Operations interface with Executive Risk Barometer.]**
**Speaker:**
> "In financial fraud investigation, the hardest question isn't *'Is this transaction suspicious?'*  
> It's: **'Do we know enough to take a high-impact punitive action right now, or should we gather more evidence first?'**
> 
> If you freeze a customer's card too aggressively on a single weak perimeter alert, you strand a legitimate cardholder abroad, triggering massive customer friction and violating regulatory safeguards under Policy R1. But if you hesitate too long, an organized card-testing syndicate executes rapid cash-outs across dozens of accounts.
> 
> Most AI agents answer this trade-off with pure LLM guesswork and hallucinations. 
> 
> Today, I'm presenting **TRACER**—an autonomous, institutional graph risk intelligence platform on TigerGraph that unites **Graph Data Science (GDS)**, **Bayesian Decision Theory (VOI / EVSI)**, and **FinCEN SAR Regulatory Automation**."
---

## [0:45 - 1:45] Live Triage & Entity Network Dossier (HHG-001)

**[Visual: In the Triage View, show the Split Triage Mode. Click on incident `HHG-001` (flagged transaction 3514030, $77.07), showing live probability 82%, then click "Open Full Dossier →".]**

**Speaker:**
> "Let's inspect incident **HHG-001**. A perimeter model scored this $77.07 transaction at 0.61. An alert is just a trigger—never a verdict.
> 
> In the **Entity Network Dossier**:
> 1. TRACER connects to TigerGraph via the **Model Context Protocol (MCP)**, executing 14 analytical GSQL queries across sliding 24-hour windows, device sharing, and geographic velocity.
> 2. On our interactive **Cytoscape Topology Canvas**, you can see the multi-hop entity graph: transactions, cards, device fingerprints, and past fraud clusters. We can toggle layout algorithms dynamically—from Force-Directed CoSE physics to Concentric rings or Hierarchical tree views—and inspect vertex degrees with one click.
> 3. Now look at the **Probabilistic Risk Decomposition** tab: every graph finding is decomposed into an additive log-odds evidence ledger. It uncovers that the purchaser email domain has never been seen on this account (+1.62 log-odds), and Weakly Connected Components (WCC) reveals that a linked card in its community has confirmed fraud (+0.81 log-odds).
> 4. TRACER reports a calibrated posterior probability of **0.82**, bounded by an 80% credible interval [0.80 – 0.84] across 200 bootstrap refits. No ungrounded LLM guesses."
---

## [1:45 - 2:45] Decision Theory (VOI/EVSI) & FinCEN SAR Automation (HHG-010)

**[Visual: Switch to the Adjudication Console on the right, then navigate to `HHG-010` ($1,000.03 transaction) and open the "FinCEN SAR Filing" tab.]**

**Speaker:**
> "Notice how TRACER decides whether to ask for more information:
> Using **Expected Value of Sample Information (EVSI)**, it prices customer SMS checks against financial loss in dollars. In this case, expected loss from releasing ($507.97) vastly exceeds protection costs ($21.90), and no further evidence inquiry has positive financial utility. TRACER stops immediately, recommending `CREATE_CASE` (Auto) and `BLOCK_CARD` (L1 Lead approval).
> 
> Now let's look at high-exposure syndicate cases like **HHG-010** ($1,000.03).
> Because exposure exceeds the $1,000 threshold and connects to an anomalous hardware device profile, Enterprise Policy R2/R6 mandates filing a regulatory Suspicious Activity Report (`FILE_REPORT`).
> 
> Look at the **FinCEN SAR Filing tab**:
> - TRACER automatically drafts a complete BSA Form 111 7-point narrative covering subject identity, timeline, channels, and graph linkages.
> - Crucially, our **Zero-Hallucination Claim Checker** validates every single dollar amount, timestamp, customer ID, and card token against TigerGraph ground truth before filing.
> - Actions are routed with human-in-the-loop governance: `BLOCK_CARD` awaits L1 Lead approval, and `FILE_REPORT` routes to Level-2 Fraud Management approval."

---

## [2:45 - 3:30] Model Calibration Observatory & 100% Benchmark Score

**[Visual: Click on the "Risk Engine Observatory" top navigation tab, then switch to terminal to run `python validate_all_benchmark_cases.py`.]**

**Speaker:**
> "In the **Risk Engine Observatory**, you can inspect our calibration curves evaluated against 5,565 historical closed cases:
> - TRACER achieves a **Brier score of 0.0778** and a **ROC-AUC of 0.9555**—compared to just 0.5548 for the bank's perimeter risk score alone!
> - It also features bi-directional graph write-back: resolving a case commits persistent `FraudCase` vertices back into TigerGraph for continuous GraphRAG precedent learning.
> 
> Finally, let's run the official validation suite across all 20 benchmark exam cases (`HHG-001` through `HHG-020`):
> `python validate_all_benchmark_cases.py`> 
> **Result: 100% Passed. 20 out of 20 cases meet all hackathon schema, policy, and mathematical criteria with zero errors.**
> 
> You can test the live system today at **https://hhgoa26-ten.vercel.app** or explore the complete codebase on GitHub. Thank you!"