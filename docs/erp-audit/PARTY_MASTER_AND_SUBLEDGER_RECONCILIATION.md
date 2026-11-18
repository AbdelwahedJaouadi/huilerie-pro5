# Party Master and Customer/Supplier Subledger Reconciliation Audit

Project: huilerie-pro5  
Base: main at `1fd0291bef813cfff59c6d4ceaa69cb6633b5503`  
Method: static inspection of traditional client accounts, GS buyer/supplier schemas, custody-owner linking and commercial statements. No party records changed.

## 1. Executive finding

The application has working role-specific party records and separate operational statements, but no single canonical party master across the traditional mill, GS buyers, GS suppliers and custody owners.

This does not prove that duplicate people or companies already exist in live data. It means the current data model permits one real-world counterparty to be represented in more than one domain without a guaranteed shared identity key.

## 2. Current identity model

- Traditional pressing clients are primarily addressed by phone in `clients`, `loads`, invoices and `/client-accounts/{phone}`.
- GS suppliers are stored in `commercial_suppliers`, with name, normalized name, optional phone and tax identifier. The unique normalized-name key is not a universal legal-party identity.
- GS buyers are stored separately in `commercial_buyers`, also with name, normalized name, optional phone and tax identifier.
- Customer custody owners are stored in `commercial_custody_owners` and link to the legacy client record through `legacy_client_id` and `client_phone`. This is a useful bridge for the custody workflow, but it is not a shared master across buyer and supplier identities.
- Cross-domain search can find matching names/phones in multiple collections; search aggregation is not identity resolution and does not merge party records.

## 3. Existing statement boundaries

Separate read models exist for:
- Traditional client pressing invoices and receipts by phone.
- GS supplier payable statement: approved olive purchases less supplier payment documents.
- GS buyer account summary: wholesale sales invoices, credited amounts, cash paid, applied buyer credit and outstanding receivables.
- Customer-to-mill oil/olive purchase payable statement.
- Customer custody quantity/ownership statement.

These statements represent different legal and operational relationships. A person may be a pressing customer, supplier, wholesale buyer and/or custody owner. The current UI/API does not provide one canonical party timeline that references all roles.

Do not automatically net a receivable against a payable merely because two records share a phone number or name. Legal set-off requires a valid party match and an approved contractual/legal basis. Preserve gross receivable and payable subledgers separately.

## 4. Risks if left unresolved

1. Same counterparty can be created separately as a traditional client, GS supplier and GS buyer.
2. Name changes, spelling differences, shared family/business phone numbers and missing tax identifiers can produce false matches or missed matches.
3. Reports may show separate balances for one real-world legal entity without a consolidated party view.
4. Supplier/customer credit risk and exposure may be understated if balances are reviewed in isolated screens.
5. Deactivation or correction of one role record may not update other role records consistently.
6. A future GL control-account reconciliation needs stable party subledger references, not names or phone numbers.

## 5. Target model

Introduce a canonical `party_id` identity while preserving role-specific domain records and subledgers.

Minimum design:
- **Party master:** stable ID, legal/individual name, party type, normalized legal name, country, legal/tax identifiers, contact methods and lifecycle status.
- **Party identifiers:** typed identifiers with issuing jurisdiction, normalized value, validity dates and verification status; unique constraints only where legally safe.
- **Party roles:** client, olive supplier, oil supplier, wholesale buyer, custody owner, employee and other roles, each with effective dates and role-specific status.
- **Role links:** traditional client ID/phone, GS supplier ID, GS buyer ID and custody owner ID all reference the canonical party.
- **Identity merge/split workflow:** authorized, reviewed, reversible, with before/after mapping and full audit history. Never merge based on phone or similar name alone.
- **Subledger references:** invoices, receivables, payables, custody, payments, credit notes and statements retain their own role/document identities and additionally reference party_id.
- **Consolidated party view:** shows separate balances by role/domain and currency, with no automatic legal set-off.

## 6. Migration safeguards

- Preserve every existing collection ID and source document reference.
- Do not bulk-merge by phone/name.
- Create candidate matches with confidence and supporting identifiers; ambiguous matches require human verification.
- A shared phone may belong to a family, employee or office; it is not a legal identity key.
- Missing tax identifiers remain unknown; do not fabricate them.
- Historical documents retain the party snapshot/name/address as issued, while the canonical party link can be corrected through an audited mapping.
- Ensure party_id introduction does not alter the existing customer-custody owner ID or traceability code.
- Reconcile traditional client statements, GS supplier statements, buyer receivables and custody statements before/after migration.

## 7. Acceptance tests

1. One legal party can hold client, supplier and buyer roles without creating three canonical parties.
2. Separate role-specific receivable/payable statements remain distinct and accurate.
3. Consolidated view lists each role balance separately and does not automatically net receivables/payables.
4. Same phone on two different parties does not auto-merge.
5. Name variation with matching verified legal identifier proposes a match but requires approved resolution.
6. Party merge/split is audited and historical invoices remain unchanged.
7. Legacy records with no reliable match remain unlinked until reviewed.
8. Custody-owner links continue to resolve to the correct traditional client and preserve customer-owned stock balances.
9. Deactivation of one role does not erase other roles or historical transactions.
10. Every source document remains traceable to its original role-specific IDs and future GL subledger references.

## 8. Boundaries

This is a source-level data-model audit, not a live duplicate-party scan. It does not establish that any specific two records refer to the same person or company. No live party records were merged, renamed or modified.
