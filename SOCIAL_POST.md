# Social Media Announcement Copy: VERDICT on TigerGraph

---

## 💼 LinkedIn Post

🚀 Excited to unveil **VERDICT**: our submission for the **TigerGraph Agentic Fraud Investigation Hackathon (Hacker House Goa 2026 - IEEE-CIS Edition)**! 🕵️‍♂️💳

In financial fraud investigation, the hardest question isn't *"Is this transaction suspicious?"*  
It's: **"Do we know enough to take a punitive action right now, or should we gather more evidence first?"**

Traditional AI agents rely on ungrounded LLM guesswork, causing severe false positives or catastrophic lag. With **VERDICT**, we fused **Graph Data Science**, **Bayesian Decision Theory**, and **FinCEN Regulatory Automation** into a production-ready AI investigator:

🔍 **TigerGraph MCP & GSQL Analytics**: 14 analytical queries traversing 26,000+ real transactions across 24h sliding velocity windows, device-sharing rings, and geographic impossibilities.  
📊 **Bayesian Log-Odds Evidence Ledger**: Every risk point is decomposed into an additive ledger with calibrated 80% credible intervals (`ci80`) from 200 bootstrap refits—no hallucinations.  
⚖️ **Value of Information (VOI/EVSI)**: Computes the net financial utility of evidence requests in dollars. The agent asks the customer or triggers step-up authentication *only* when the answer could flip the decision and is worth the operational cost.  
🛡️ **Policy-as-Code & FinCEN SARs**: Strict Policy R1–R10 enforcement with automated approval routing (auto, L1 Lead, L2 Manager) and programmatic n-gram claim checking on all filed SAR narratives.  
🏆 **100% Benchmark Score**: Passed all 20 official IEEE-CIS exam cases (`HHG-001` to `HHG-020`) with zero schema warnings!

Huge thanks to @TigerGraph and the Hacker House Goa organizers for this incredible challenge!

🔗 **GitHub Repository & Live Demo:** <your-github-repo-link>  
📄 **Read the Technical Blog Post:** <blog-post-link>  
🎬 **Watch the 3-Minute Video Demo:** <demo-video-link>  

#TigerGraph #AgenticAI #GraphRAG #FraudDetection #GSQL #FinTech #MachineLearning #DecisionTheory #GraphDataScience #HackerHouseGoa

---

## 🐦 X / Twitter Thread (280 Characters)

### Tweet 1 (Main Announcement)
Excited to launch **VERDICT** for the @TigerGraphDB #HackerHouseGoa Agentic Fraud Challenge! 🕵️‍♂️

An AI investigator that knows *when* it knows enough to act:
⚡ 14 GSQL Queries via MCP
📊 Bayesian Log-Odds Ledger
⚖️ Value of Information (EVSI)
🛡️ Grounded FinCEN SARs
🏆 20/20 Benchmark Passed

🧵👇

### Tweet 2 (Architecture & Math)
Why VERDICT wins:
Instead of relying on LLM vibes, VERDICT calculates the Expected Value of Sample Information in dollars. It gathers evidence only if $\text{EVSI} > \text{Cost}$, preventing unwarranted card freezes under Bank Policy R1.

### Tweet 3 (Graph & Compliance)
Built on real IEEE-CIS data with Louvain community detection, WCC, and PageRank. Generates both official `cases/<id>.json` files and deep mathematical audit dossiers, served on a modern React + Cytoscape cockpit.

Check out the code & demo: <your-repo-link>

---

## 💬 Hacker News / Reddit / Discord Pitch

**Title:** Show HN: VERDICT – Value-of-Information Agentic Fraud Investigation on TigerGraph

**Body:**
Hey everyone! We just open-sourced **VERDICT**, an agentic fraud investigation system built for the TigerGraph Hacker House Goa 2026 challenge.

Most AI agents for fraud either block cards on a single weak heuristic or hallucinate claims in regulatory reports. VERDICT solves this with:
1. **Additive Log-Odds Accounting**: Every GSQL signal maps to an exact log-odds contribution with bootstrap credible intervals.
2. **Decision-Theoretic Stopping Gate**: Calculates Expected Value of Sample Information (EVSI) net of customer friction before requesting verification.
3. **Zero-Hallucination SARs**: An n-gram claim checker validates that all amounts, timestamps, and card IDs exist in TigerGraph before filing FinCEN reports.
4. **Resilient Dual-Engine**: Runs live against TigerGraph Savanna via MCP, with an in-memory `LocalGraphGateway` fallback for local zero-dependency testing.

Evaluates 100% compliant across all 20 official benchmark cases (`HHG-001` to `HHG-020`).

We'd love your feedback on the architecture, GSQL algorithms, and Bayesian ledger approach!
GitHub: <your-repo-link>
