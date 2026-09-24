# Known Fraud Patterns (synthetic stand-in)

## PAT-1 CARD_TESTING
Several small online authorisations on one card within an hour, often from a new device, followed by a larger purchase once the card is confirmed working.

## PAT-2 CNP_NEW_DEVICE
Same-day card-not-present fraud from a device the identity record marks as new for the account, sometimes behind an anonymous proxy.

## PAT-3 OUT_OF_REGION
Card-present purchases in a billing region where the cardholder has no history, while their normal activity continues at home (counterfeit / skimmed card).

## PAT-4 ACCOUNT_TAKEOVER
Mixed-channel activity inconsistent with the cardholder, with device changes, email-domain changes and address/name match-flag failures, pointing to stolen credentials rather than a stolen number.

## PAT-5 SHARED_ENTITY_RING
Several cards belonging to different customers transacting through the same device profile, billing region or recipient email within a short window; organised fraud.
