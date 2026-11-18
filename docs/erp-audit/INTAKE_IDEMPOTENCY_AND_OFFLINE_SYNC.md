# Intake Command Idempotency — Traditional Loads and GS Supplier Reception

Project: Oro Verde / huilerie-pro5  
Review date: 18 Nov 2026  
Status: source-level audit and implementation contract; no runtime changes

## 1. Executive summary

The two physical intake paths have different reliability maturity:

- Traditional `POST /loads` has no client request key, no canonical payload fingerprint and no duplicate-command lookup. A retry after an uncertain network response creates another load with a new ID and load code.
- GS `POST /commercial/v1/olive-receptions` has a request key and transaction, but its idempotency check is split across the purchase-draft fingerprint and approval fingerprint. The outer command is not fingerprinted as one complete normalized payload. In particular, changed phone/tax metadata for a new supplier can be silently ignored on a retry that reuses the same key and name.

The two problems must be solved before gross/tare capture and before the planned local/offline intake workflow. A unique sequential load code is not request idempotency.

## 2. Traditional load creation — confirmed duplicate-command path

### Current request

`LoadCreate` accepts:
- client name and phone;
- one positive `olive_kg: float`;
- optional bags, variety and notes;
- initial status.

It does not accept a request/idempotency key. `frontend/src/components/IntakePanel.tsx` posts the body directly to `POST /loads` without retaining a request identity across retries.

### Current write order

`backend/routers/loads.py::create_load`:
1. Normalizes phone and checks inactive-client state.
2. Reads active season and reserves the next sequential load code.
3. Generates a fresh UUID and timestamp.
4. Opens a MongoDB transaction.
5. Creates/guards the client registry record.
6. Inserts a new load document.
7. Inserts a `LOAD_CREATED` audit event.
8. Commits, then sends the arrival SMS outside the transaction.

There is no lookup by client operation ID and no fingerprint comparison. A retry repeats steps 2–7 with a new UUID and code. The unique `loads.code` index only prevents duplicate codes; it cannot recognize the same physical intake submitted twice.

The current transaction protects the client/load/audit write set, but not duplicate HTTP business intent. Because code reservation currently occurs before the transaction, a rejected/failed attempt may also consume a sequential code; gaps are acceptable, but avoid reserving a code before a replay check.

### Required behavior

Add a required request key for the upgraded intake client, with a controlled compatibility policy for older clients during rollout:
- Same scoped key + same canonical payload: return the original load response, with no second load, audit event, client mutation or notification enqueue.
- Same scoped key + different payload: return HTTP 409 with a stable conflict code such as `idempotency_key_payload_conflict`.
- New key: create exactly one load, one audit event and one notification-outbox event atomically.
- Concurrent requests with the same key: exactly one commits; the loser reads the committed winner and applies the same fingerprint comparison.
- A replay must not reserve a new load code or create a new client record.

Recommended persisted request identity on the load or a dedicated request collection:
- scope (single mill + authenticated actor/device namespace, with a documented offline identity policy);
- idempotency key;
- canonical payload fingerprint;
- resulting load ID;
- created/recorded timestamps;
- request schema version.

Use a unique index on the scoped key. Fingerprint normalized business fields, not presentation details: normalized phone, trimmed client name, exact normalized quantity, bags, variety, notes and initial status. During weighing rollout, include gross, tare, unit, weighing source, scale ticket/device identity and any source timestamp in the fingerprint. Do not include server-generated load code, current time or generated UUID.

The server must calculate/validate net weight and include the canonical validated gross/tare/net evidence in the fingerprint. A submitted client net is not authoritative.

## 3. Traditional SMS side effect

Arrival SMS is sent after the load transaction. This avoids rolling back a valid load because the SMS provider is unavailable, but a naive replay-safe handler must not send the SMS again every time the original request is retried.

Use a transactional outbox:
- insert one `LOAD_ARRIVAL_NOTIFICATION_REQUESTED` outbox item in the same transaction as the load;
- give it a stable notification event ID derived from the load/request identity;
- dispatch asynchronously with retry tracking;
- pass a provider idempotency token if the SMS provider supports it;
- record delivered/failed status and provider reference.

Without provider-side idempotency, exactly-once external SMS delivery cannot be guaranteed across a crash between provider acceptance and local acknowledgement. State the achievable guarantee honestly (durable at-least-once delivery plus duplicate mitigation), rather than claiming exactly once.

A replayed HTTP request returns the original load and never creates a second outbox event.

## 4. GS supplier reception — confirmed incomplete outer fingerprint

### Existing safeguards

`OliveReceptionPurchaseCommand` includes an idempotency key. The route creates supplier, purchase draft, approval, lots and stock receipt inside one MongoDB transaction.

The purchase draft service fingerprints its normalized `OlivePurchaseDraft` (supplier ID, purchase date, lines, notes and idempotency key). The approval service fingerprints `ApproveOlivePurchaseCommand` (expected version, receiving location and approval key). An already-approved purchase rejects a changed approval fingerprint, so a changed receiving location is not silently accepted.

### Gap

The route's outer command also contains:
- `new_supplier_name`;
- `new_supplier_phone`;
- `new_supplier_tax_identifier`;
- receiving location;
- original price-in-millimes representation and other normalized input fields.

For a new supplier, supplier ID is deterministically derived from the request key. If the same key is retried with the same normalized supplier name but a changed phone or tax identifier:
1. The normalized-name lookup finds the already-created supplier with the same deterministic supplier ID.
2. The route does not compare the existing supplier phone/tax identifier with the retry payload.
3. The purchase draft fingerprint remains unchanged because supplier ID/date/lines/notes/key are unchanged.
4. The approval fingerprint remains unchanged if the location is unchanged.
5. The retry can return the prior approved purchase while silently ignoring changed supplier contact/tax metadata.

This is a confirmed incomplete idempotency contract. It is not evidence of duplicate stock posting: the transaction and existing purchase/approval guards prevent the ordinary same-key replay from simply creating a second purchase.

The UI retains `supplierRequestKey` after an error and clears it after success, which is useful retry behavior. But if the operator edits supplier contact/tax values after an uncertain response and retries with the same key, the API currently does not reject the changed outer payload.

### Required behavior

Fingerprint the complete canonical reception command before creating the supplier:
- existing supplier ID OR normalized new supplier name;
- new supplier phone and tax identifier (including explicit nulls);
- purchase date;
- every line's variety ID, exact kg Decimal and unit price in millimes;
- receiving location;
- notes;
- request schema version.

Persist a unique scoped idempotency record for the complete command in the same transaction as supplier/purchase/approval/lot/stock/audit writes. On same key/same fingerprint return the prior result; on same key/different fingerprint return 409. Do not silently ignore changed contact/tax metadata.

A duplicate-key race must be handled by reading the winning idempotency record after transaction abort and comparing fingerprints. Do not convert every DuplicateKeyError into generic success; only identical request fingerprints are idempotent success.

The request scope must be explicit. If scoped by employee, an offline retry must preserve the original authenticated actor identity; do not let a new device/user accidentally reuse a key in a different scope and create a second purchase.

## 5. Offline/local-server synchronization

The planned local Windows server and worker phones require a durable outbox/inbox contract, not merely browser state:
- create a client-generated UUID operation ID before the first network attempt;
- persist the complete payload and operation ID in a durable local queue;
- retry the exact same payload and key until a terminal response is received;
- never generate a new key just because a request timed out;
- server stores the idempotency claim and source record atomically;
- same key/same payload returns original result; same key/changed payload conflicts;
- preserve original device/actor identity, local captured timestamps and device ticket IDs;
- store server-received/synchronized timestamps separately;
- keep local operation state (queued/sending/acknowledged/conflict) visible to the operator;
- prevent deletion of an unacknowledged local operation without an explicit audited cancellation workflow.

A local browser's component state alone is not a durable offline queue. Use a durable local database/outbox (for example, the local app's server-side persistence or an explicitly selected client storage design) and define conflict recovery before enabling offline mode.

## 6. Required regression tests

### Traditional `POST /loads`
1. First request creates one load, one client registry mutation and one audit event.
2. Same key/same payload returns the exact original load ID/code; counts of loads/audit/client mutations remain unchanged.
3. Same key with changed phone/name/quantity/bags/variety/notes/status returns 409 and creates nothing.
4. Two concurrent same-key/same-payload requests create one load and one code; both callers receive the same resulting load.
5. Same key in another authenticated scope follows the explicitly chosen scope policy.
6. Transaction abort leaves no idempotency claim, load, audit or notification-outbox event.
7. Replaying a committed request does not reserve another load code.
8. Replaying a committed request does not enqueue or send a second arrival SMS.
9. SMS provider timeout/retry is covered by outbox tests; no false exactly-once guarantee.
10. Legacy clients without a key follow the explicitly time-bounded compatibility policy and are observable; do not silently make all old clients fail before coordinated frontend rollout.

### GS `POST /commercial/v1/olive-receptions`
11. Same complete command/key returns the same purchase, supplier, lot and movement IDs.
12. Same key with changed new-supplier phone returns 409.
13. Same key with changed tax identifier returns 409.
14. Same key with changed supplier name returns 409.
15. Same key with changed date, line variety, quantity, unit price, location or notes returns 409.
16. Concurrent identical requests produce one supplier, purchase, lot set, stock receipt and audit event.
17. Concurrent same-key/different-payload requests allow one canonical payload and reject the other.
18. Transaction rollback removes the idempotency claim and all business writes together.
19. Retry after an uncertain client response returns the committed original receipt; it does not create a second batch code or stock movement.

### Weighing and offline integration
20. Gross/tare/net are part of the same canonical fingerprint; changed readings under the same operation key conflict.
21. Same physical scale ticket cannot be ingested twice under two different request keys.
22. Offline retry after reconnection preserves the same operation ID and produces one physical intake.
23. Legacy net-only records remain unchanged and are not assigned invented gross/tare readings.

## 7. Release boundary

Do not deploy the idempotency or weighing runtime changes until:
- GitHub Actions assigns a real runner and executes steps;
- unit tests for canonical normalization/fingerprinting pass;
- MongoDB transaction and concurrent duplicate-key tests pass against a replica-set-capable test database;
- frontend retry behavior is tested on both desktop and worker phones;
- outbox behavior is tested independently from load transaction success.

No runtime code, collection, index, live data, permission or Render service is changed by this audit document.


## 8. Verified SMS failure semantics (source-level clarification)

The arrival-SMS path has a narrower failure mode than a generic provider outage:

- `backend/lib/sms.py::_deliver` catches `httpx.HTTPError` and returns status `failed` with an error string. Non-200/201 Twilio responses also return `failed`; they do not raise an exception.
- `send_load_sms` then attempts to persist the SMS result in `sms_log` and returns the log record. Therefore an ordinary Twilio rejection/timeout is recorded as a failed notification while the already-created load request can still return successfully.
- Exceptions from reading SMS settings/credentials or writing the `sms_log` record are not swallowed by `send_load_sms`. Since `create_load` awaits it after the load transaction has committed, such a local database/settings exception can still produce an HTTP error after the load exists.
- The traditional intake form disables its submit button while the mutation is pending, but it does not send or retain a request key. That protects against ordinary double-clicks in one mounted form, not retries after timeout, reload, lost response or another device.

Consequently, the primary duplicate-load risk remains the missing server-side idempotency key, not an ordinary Twilio provider failure. The outbox is still the correct durable notification design, but its dispatcher must record provider failures without changing the committed intake result.
