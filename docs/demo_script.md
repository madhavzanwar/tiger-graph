# Demo video script (target 4:00, max 5:00)

**Setup before recording:** `verdict bootstrap` done, `verdict serve` running, browser at http://localhost:8000, zoom 90%.
Pick the three cases from `outputs/<dataset>/benchmark_summary.md`: (A) an ambiguous case with an evidence request,
(B) a ring / SAR case, (C) a false positive that gets released. On the synthetic set: A = HHG-006, B = HHG-008, C = HHG-020.

| Time | Screen | Say |
|---|---|---|
| 0:00-0:20 | Title / case queue | "Fraud teams act after the money's gone. VERDICT goes from an uncertain signal to a defensible action, and it knows when it doesn't know enough yet." |
| 0:20-0:50 | README architecture diagram | "The agent investigates only through the TigerGraph MCP server, read-only. A calibrated evidence model learned from 5,500 closed cases turns graph findings into a probability. A value-of-information rule decides whether to ask for more evidence. The bank's policy, compiled to code, decides what's allowed, and a human approves anything high-impact." |
| 0:50-1:50 | Case A: click Investigate | Point at the timeline (MCP calls, ~15 ms each), the graph growing, the belief trajectory. "The model risk score said 51%. After the graph evidence it's 65%, but look at the credible interval and the decision stability. The agent computes that a customer confirmation would flip the decision, and the request is worth more than it costs, so it asks. Here are the branches it committed to *before* the answer." Click *Receive benchmark response*. "Confirmed: probability drops to 11%, release, and closing the case goes to an L1 analyst." |
| 1:50-2:40 | Case B | "A risk alert on a card that shares a device and recipient email with four other cards in a week. Graph ring detection plus the Louvain community. Policy POL-3.7 requires a report, so the SAR is drafted. Every number in it was checked against the evidence store." Show the SAR and the COMPLIANCE route. Approve BLOCK_CARD in the approval inbox. |
| 2:40-3:10 | Case C | "A high risk score, a new region, but no activity at home at the same time. The model learned from this bank's history that a new region *alone* points to a traveller. It asks the customer, gets a confirmation and releases. That's a false positive avoided." |
| 3:10-3:40 | Memory & patterns tab | "Not every pattern is documented. VERDICT clustered the fraud cases no typology explains and found dormant cards suddenly used at night. It's stored in the graph as a hypothesis and new cases are matched to it and escalated, never auto-closed." Then resolve a case and show the weight deltas: "Resolved outcomes update the model." |
| 3:40-4:10 | Scoreboard | "We measure ourselves: on a time-split holdout the evidence model reaches an AUC of X, against Y for the bank's risk score alone, and it's calibrated." |
| 4:10-4:30 | answer file + graph write-back line | "Twenty answer files with next best actions and approval routes before and after evidence, SARs where required, and every case written back to TigerGraph as memory." |
