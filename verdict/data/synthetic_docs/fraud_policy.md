# Bank Fraud Policy (synthetic stand-in)

## POL-1 Scope and authority
POL-1.1 The fraud agent may investigate, create and update cases, and **recommend** any action.
POL-1.2 The agent may **execute** only actions whose approval route is `AUTO`.
POL-1.3 Actions with route `L1_ANALYST`, `L2_FRAUD_MANAGER` or `COMPLIANCE` require recorded human approval before execution.
POL-1.4 Every recommendation must record the evidence relied on and the approval route, before and after any additional evidence is requested.

## POL-2 Action catalogue and approval routes
| Action | Meaning | Approval route |
|---|---|---|
| ALLOW_TRANSACTION | Let the transaction proceed | AUTO |
| MONITOR_CARD | Enhanced monitoring on the card for 30 days | AUTO |
| MONITOR_ACCOUNT | Enhanced monitoring on all of the customer's cards | AUTO |
| WARN_CUSTOMER | Send a fraud-awareness warning | AUTO |
| STEP_UP_AUTH | Challenge the next authorisation with strong authentication | AUTO |
| CONTACT_CUSTOMER | Ask the account owner to validate the transaction | AUTO |
| REQUEST_ANALYST_INFO | Ask an analyst / approved party for additional information | AUTO |
| CREATE_CASE | Open a fraud case | AUTO |
| DECLINE_TRANSACTION | Decline the pending transaction | L1_ANALYST |
| BLOCK_CARD | Block the card | L1_ANALYST (amount at risk <= $2,500), otherwise L2_FRAUD_MANAGER |
| BLOCK_ALL_CARDS | Block every card of the customer | L2_FRAUD_MANAGER |
| ESCALATE_TO_ANALYST | Hand the case to a human analyst | AUTO |
| FILE_REPORT | File a suspicious activity report (SAR) | COMPLIANCE |
| CLOSE_NO_FRAUD | Close the case as not fraud | L1_ANALYST |

## POL-3 Rules
POL-3.1 Card testing: three or more small (< $10) online authorisations on one card within one hour followed by a larger purchase -> STEP_UP_AUTH. If a purchase over $100 has already cleared -> BLOCK_CARD.
POL-3.2 New-device card-not-present activity with an anonymous proxy -> CONTACT_CUSTOMER before any block, unless the fraud probability is already high.
POL-3.3 If the customer does not reply within 24 hours -> DECLINE_TRANSACTION and MONITOR_CARD.
POL-3.4 If the customer denies the transaction -> BLOCK_CARD. If the customer confirms -> ALLOW_TRANSACTION and MONITOR_CARD.
POL-3.5 Out-of-region card-present use while home activity continues -> CONTACT_CUSTOMER; BLOCK_CARD once denied or on no reply.
POL-3.6 Account takeover indicators (new device + changed email + match-flag failures) -> STEP_UP_AUTH and ESCALATE_TO_ANALYST. BLOCK_ALL_CARDS only with evidence of a wider compromise (activity on more than one of the customer's cards or credential change).
POL-3.7 When several cards show fraud from the same device profile, billing region or recipient email -> CREATE_CASE and FILE_REPORT.
POL-3.8 BLOCK_ALL_CARDS is forbidden without evidence of a wider compromise.
POL-3.9 A pattern not covered by the documented typologies must be escalated to an analyst (ESCALATE_TO_ANALYST); it may not be auto-cleared.
POL-3.10 Cases with low fraud probability after evidence may be closed with CLOSE_NO_FRAUD (L1 approval) and MONITOR_CARD.

## POL-4 Suspicious activity reporting
POL-4.1 FILE_REPORT is required when confirmed or highly probable fraud involves $1,000 or more, an organised ring (POL-3.7), or account takeover.
POL-4.2 A SAR must state who, what, when, where, why and how, reference the evidence, and list actions taken.
