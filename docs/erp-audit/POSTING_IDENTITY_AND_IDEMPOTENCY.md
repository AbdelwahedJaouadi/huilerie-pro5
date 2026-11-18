# General-Ledger Posting Identity and Idempotency Contract

Project: Oro Verde / huilerie-pro5
Branch: audit/erp-foundation
Status: proposed technical contract; not implemented.
Date: 17 Nov 2026

## 1. Objective

Prevent duplicate, missing, out-of-order and untraceable journal postings when operational requests are retried, two employees act concurrently, a document is corrected, or a payment is reversed.

A journal entry must be generated from one immutable business event. A document may emit multiple distinct events over its lifecycle (for example invoice issued, payment received, credit note issued, payment reversed). The document itself is not the event identity.

## 2. Canonical source-event key

Proposed unique identity:

`source_type + ":" + source_id + ":" + event_type + ":" + event_version`

Where:
- `source_type` is a stable, enumerated domain name, not a collection name that may later be renamed.
- `source_id` is the immutable business ID of the source document or child event.
- `event_type` identifies the economic event, e.g. `INVOICE_RECOGNIZED`, `PAYMENT_RECEIVED`, `PAYMENT_REVERSED`, `PURCHASE_APPROVED`, `STOCK_COST_ISSUED`.
- `event_version` is normally 1. It may increase only for a formally defined new event version, never to bypass a duplicate conflict.

Do not use a request idempotency key as the accounting event identity. Request idempotency prevents duplicate operational commands; posting-source identity prevents the same economic event from being posted twice across retries and separate code paths.

## 3. Proposed posting-source record

```json
{
  "id": "stable UUID",
  "source_type": "TRADITIONAL_INVOICE",
  "source_id": "immutable source document ID",
  "event_type": "INVOICE_RECOGNIZED",
  "event_version": 1,
  "source_event_key": "TRADITIONAL_INVOICE:<source-id>:INVOICE_RECOGNIZED:1",
  "source_document_number": "display number",
  "event_business_date": "YYYY-MM-DD",
  "event_recorded_at": "UTC timestamp",
  "currency": "TND",
  "amount_basis": "NET_OF_APPROVED_TAX",
  "payload_fingerprint": "canonical hash",
  "journal_entry_id": "linked immutable journal entry",
  "posting_status": "POSTED",
  "created_by": "user ID",
  "created_at": "UTC timestamp"
}
```

The JSON is illustrative, not a live schema. Do not store secrets or duplicate full customer personal data in posting records.

## 4. Database uniqueness and transaction rules

Required unique index:
- `(source_type, source_id, event_type, event_version)` unique.
- Optionally store a unique canonical `source_event_key` as a convenience, but do not rely on concatenation alone if source IDs can contain delimiters.

Posting algorithm:
1. Load and validate the authoritative source document and exact event state.
2. Build a canonical, normalized event payload using Decimal values and explicit currency/unit.
3. Start a database transaction.
4. Insert or claim the unique posting-source identity.
5. If it already exists with the same fingerprint and linked posted journal entry, return the existing result (idempotent success).
6. If it exists with a different fingerprint, reject and raise a reconciliation incident; never overwrite a posted event.
7. Create journal header and balanced lines.
8. Validate debit = credit exactly, valid account/period, actor permission and source-state eligibility.
9. Link posting-source to the journal entry and mark POSTED.
10. Commit atomically.

A duplicate-key race must be handled by re-reading the winning posting-source record and comparing its fingerprint. Do not return success for a conflicting payload.

## 5. Corrections and lifecycle

- Draft source changes do not create GL events.
- A posted source event is immutable.
- Reversal creates a new source event with a link to the original event and journal entry.
- A correction after posting creates a reversal and a replacement/adjustment event; it never changes the original event's fingerprint or journal lines.
- Payment reversal is a distinct settlement reversal. It does not reverse invoice revenue unless an approved credit note or return event separately requires that.
- A credit application is its own non-cash settlement event, linked to its credit source and target invoice.
- Stock correction is a separate inventory adjustment event with reason and approval.

## 6. Business date, recording time and period

Every event stores:
- `event_business_date`: date the economic event belongs to, based on the approved accounting policy.
- `event_recorded_at`: immutable UTC timestamp when the system accepted the event.
- `posted_at`: timestamp when the journal entry was posted.
- `fiscal_period_id`: explicit period resolved from configured fiscal-year dates.

Do not substitute `created_at` for the accounting date without policy. A payment date, invoice date, delivery/acceptance date, and record creation timestamp can differ. If the relevant business date is missing or outside an open period, require a controlled exception rather than silently using today's date.

Fiscal-year boundaries remain unset until owner/accountant approval. Olive-season code is not a fiscal-period key.

## 7. Money and quantity normalization

- Money is stored as Decimal128 or integer minor units; use TND as explicit currency.
- Quantities use Decimal and explicit units (kg, L, units); never aggregate kg and L as if interchangeable.
- Store tax base, tax amount and applied tax-rule version separately where applicable.
- Do not post from floating-point values or formatted display strings.
- A posted journal line stores the exact amount and currency used at posting time; later source display formatting cannot change it.

## 8. Current-source compatibility work required

- Traditional invoice payment objects are embedded and have no stable payment IDs. Introduce immutable payment child IDs/document records before posting receipts.
- Legacy `paid_amount` replacement semantics must be retired or restricted to an approved reconciliation workflow.
- Traditional invoice repricing/deletion must be replaced by adjustment/reversal lifecycle.
- GS payment, reversal and credit-application records already have their own IDs and request idempotency; posting still requires its own unique source-event key.
- Purchase and sale drafts must not post. Post only at their approved/recognized transition.
- Customer custody receipt/release events are not purchases or sales without a separate title-transfer/fee event.
- Manual passive-income/expense entries need evidence, recognition date, settlement event, cash/bank account and void/reversal lifecycle.
- All source adapters must define a deterministic fingerprint and event eligibility rule.

## 9. Required tests before enabling posting

- Same request retried twice produces one operational event and one journal entry.
- Two concurrent attempts to post one source event produce exactly one posted entry.
- Same source-event key with changed amount/fingerprint is rejected.
- Invoice issue and payment receipt create separate balanced entries.
- Multiple payments create separate receipt entries without duplicating invoice revenue.
- Payment reversal reverses only the settlement entry.
- Credit application is non-cash and does not create revenue.
- Accepted return/credit note creates the approved revenue/inventory adjustments; rejected return does not.
- Company-owned and customer-owned stock never cross-post.
- Backdated events into a closed period are blocked or explicitly approved.
- A transaction failure rolls back posting-source claim and journal lines together.
- Reversal links preserve the original posted event and journal unchanged.

No GL posting endpoint or collection is implemented by this contract.
