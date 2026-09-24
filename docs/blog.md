# Teaching a fraud agent when to stop: value of information, graph evidence and memory on TigerGraph

*Hacker House Goa 2026, TigerGraph Agentic Fraud Investigation challenge. Code: <repo link> · Demo: <video link>*

## The problem

A fraud analyst's hardest question isn't "is this fraud?". It's **"do I know enough to act?"** Block too early and you've
stranded a genuine customer abroad. Wait too long and the money's gone. The brief asked for an agent that handles
*uncertain* signals: one that gathers evidence, knows when to ask for more, recommends a defensible action and explains itself.

Most LLM agents answer that question by vibes. We wanted an agent whose uncertainty is **measured**, whose requests for
more evidence are **justified in dollars**, and whose actions are **constrained by the bank's policy by construction**.

## What we built

VERDICT, an investigation agent with five layers:

1. **Graph investigation (TigerGraph + MCP).** The agent reaches the graph only through the official `tigergraph-mcp`
   server, started with a read-only tool filter. Our 14 installed GSQL queries answer the questions an analyst asks:
   *Were there small authorisations on this card in the last hour? Is this device new for this customer, and who else
   uses it? Is the customer's normal activity continuing at home while their card is used 800 km away? Which other cards
   share a device or recipient email with this one?* Ring context comes from a card-to-card projection we build in GSQL,
   with TigerGraph's GDS WCC and Louvain run over it.
2. **A calibrated evidence ledger.** Each query result becomes named signals. Their weights are learned from the bank's
   closed cases with a regularised additive log-odds model, and 200 bootstrap refits give a credible interval. Every point
   of probability is a ledger row with a source query. The model learned things analysts know: a new region *alone* is
   evidence *against* fraud (people travel), but a new region *while home activity continues* is the strongest signal we have.
3. **Value of information.** With a loss model (the cost of blocking a genuine customer vs. the exposure of letting fraud
   continue) and response likelihoods learned from history (P(customer denies | fraud) = 0.74 vs 0.07 | legit), the agent
   computes the expected value of each evidence request. It asks only when that value is positive after cost **and** some
   answer would flip the decision. Before asking, it records the branch for every possible answer.
4. **Policy as code.** The bank's policy is compiled into rules with clause IDs, approval routes, prohibitions and SAR
   criteria. The engine is the final authority. It can defer a block until the customer answers (POL-3.5), refuse
   `BLOCK_ALL_CARDS` without evidence of wider compromise, and override the loss model when a customer confirms (POL-3.4).
   The LLM can only *propose*; anything off the AUTO route waits for a human.
5. **Memory.** Every case is written back to the graph as `FraudCase → Evidence / EvidenceRequest / CaseAction` with
   `SIMILAR_CASE` edges and vector embeddings. GraphRAG fuses TigerVector hits with graph-structural precedent. Resolved
   cases refit the model live, and a discovery job clusters fraud the documented typologies can't explain, which is how the
   agent found the undocumented *dormant card, night-time reactivation* pattern.

## Architecture

(diagram from the README)

## How TigerGraph is used

- A schema of 13 vertex types, covering both the transaction world and the investigation world (cases, evidence, actions,
  patterns, doc chunks, feature statistics).
- Installed GSQL queries with time windows, hub suppression and inverse-log-degree weighting, each taking 10-25 ms.
- GDS WCC and Louvain on a GSQL-built projection.
- TigerVector for policy clauses and case narratives, searched with `vectorSearch()` from installed queries.
- The TigerGraph MCP server as the agent's only read path, with the tool filter as a least-privilege control.

## Agentic capabilities

Tool use over MCP with a budget; a phase state machine (trigger → investigate → assess → decide → gather → reassess →
act → explain → remember); controlled evidence requests; human-in-the-loop approvals; grounded explanations; case memory
and a learning loop; pattern discovery.

## Results

<fill in from `docs/scoreboard` / the Scoreboard tab after running on the official data: backtest AUC vs risk score,
calibration, pattern accuracy, number of cases needing evidence>

## What we learned

- **The LLM is best at judgement, not arithmetic.** Moving probabilities and policy into deterministic code made the
  agent auditable and made the LLM's job (what to look at, how to explain) sharper.
- **"Ask for more evidence" needs a price.** Once requests had a cost and a value, the agent stopped over-asking on
  obvious cases and started asking on the genuinely ambiguous ones.
- **Graph features beat the score.** The bank's risk score alone was weak on investigated cases; graph context carried
  the signal.

## What we'd improve with more time

Graph embeddings (FastRP) as precedent features, per-segment loss models, streaming triggers, a feedback loop from
analysts to proposed policy changes, and richer analyst-facing counterfactuals ("what single fact would change this decision?").
