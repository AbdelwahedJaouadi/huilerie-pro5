# Bank Statement Preview — Phase 13

## Purpose
Provide an admin-only, non-persistent preview of a normalized bank CSV against already recorded treasury movements. This is a review aid, not a bank reconciliation or import ledger.

## CSV contract
UTF-8 (optional BOM), comma-delimited CSV, maximum 2 MiB and 100 data rows.

Required headers:
- `transaction_date` — booking/transaction date, ISO `YYYY-MM-DD`
- `amount` — positive TND amount, plain decimal notation, maximum three fractional digits
- `direction` — `IN` or `OUT`

Optional headers:
- `value_date` — ISO `YYYY-MM-DD`
- `reference` — bank reference, maximum 160 characters
- `description` — maximum 500 characters

The preview requires selection of an active TND bank account. It compares only movements in the active olive season, on that account, with the same direction and exact Decimal128 amount, within seven calendar days of the statement transaction date.

## Candidate statuses
- `REFERENCE_CANDIDATE`: exactly one candidate has the same external reference.
- `AMBIGUOUS_REFERENCE`: multiple candidates share that reference.
- `POSSIBLE_MATCH`: one amount/date/direction candidate exists but no bank reference was supplied.
- `AMBIGUOUS`: multiple candidates exist without a decisive reference.
- `REFERENCE_MISMATCH`: amount/date/direction candidates exist but their reference differs.
- `UNMATCHED`: no candidate exists.
- `DUPLICATE_IN_FILE`: duplicate statement line fingerprint within the uploaded file.

Every result has `automatic_match=false`. A candidate is never marked reconciled by this preview.

## Safety and data handling
- Admin-only endpoint; upload is held in request memory and is not persisted.
- File size and row count are bounded.
- Strict date, amount, direction, and CSV shape validation.
- Duplicate detection is within the current uploaded file only; this preview does not claim to detect files imported in the past.
- No bank statement collection, source movement, settlement status, balance, or GL record is created or changed.
- Bank statement values are suggestions and require human evidence review before any future reconciliation action.

## Deferred
- Bank-specific CSV/XLSX format adapters after the actual bank export format is confirmed.
- Persistent statement batches and cross-upload duplicate protection.
- Maker/checker review and explicit statement-line-to-movement reconciliation.
- Partial matching, fees, interest, direct debits, FX and bank-originated transactions.
- Statement opening/closing balance validation and period locking.
