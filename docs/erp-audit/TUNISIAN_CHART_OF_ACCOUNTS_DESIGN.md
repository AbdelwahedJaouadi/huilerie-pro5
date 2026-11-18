# Tunisian Chart of Accounts and ERP Mapping Design

Project: Oro Verde / huilerie-pro5
Branch: audit/erp-foundation
Status: design baseline only; not an accountant-approved posting chart.
Framework: Tunisian Système Comptable des Entreprises, NC 01 and applicable technical standards.

## 1. Governing rule

Use the Tunisian NC 01 nomenclature as the statutory account-code foundation. Do not import the French PCG, a public-sector chart, or an IFRS-only chart. NC 01 permits each enterprise to adapt the proposed nomenclature to its legal status and activities by creating appropriate subdivisions, provided additions/groupings and their operating rules are documented.

The complete account list and final subaccounts must be checked against the current official NC 01 text and approved by the company's Tunisian chartered accountant before posting is enabled. This document intentionally does not invent detailed account codes or tax mappings.

References:
- Ministry of Finance / National Accounting Council: https://www.finances.gov.tn/fr/conseil-national-de-la-comptabilite-cnc
- OECT — Tunisian accounting system: https://oect.org.tn/systeme-comptable-tunisien/
- NC 01 PDF hosted by OECT: https://oect.org.tn/wp-content/uploads/2023/01/NC_01.pdf
- Law 96-112 in JORT: https://jort.tn/view/journal-officiel/fr/1996/105/loi-96-112/

## 2. NC 01 account-class architecture

| Class | NC 01 purpose | Oro Verde ERP coverage |
|---|---|---|
| 1 | Equity and non-current liabilities | SUARL capital, reserves, retained earnings, result, provisions, loans |
| 2 | Non-current assets | Land, buildings, industrial equipment, weighbridge, vehicles, IT and intangible assets; depreciation |
| 3 | Inventories | Company-owned olives/oil, packaging and consumables; valuation under NC 04 |
| 4 | Third parties | Customers, suppliers, employees, tax/social bodies, sole shareholder current account |
| 5 | Financial accounts | Cash, bank accounts and other financial accounts |
| 6 | Expenses | Purchases consumed, payroll, energy, maintenance, services, depreciation and finance costs |
| 7 | Revenues | Pressing/service revenue, oil/product sales, by-products and other approved income |

This is a class-level design map, not a final posting instruction. Exact account codes, subdivisions, normal balances and financial-statement line mappings must be validated against NC 01 and the company's actual activities.

## 3. Analytical dimensions — do not explode the chart of accounts

Use subsidiary ledgers and dimensions rather than a separate general-ledger account for every customer, supplier, lot, tank, employee or production batch.

Required dimensions where relevant:
- Activity: pressing service, olive purchase, oil purchase, custody, oil sale, by-products.
- Cost centre: reception/weighing, pressing, laboratory/quality, tanks/storage, packaging, sales, administration, maintenance.
- Product/variety/quality category.
- Ownership: company-owned versus customer-owned/custody stock.
- Traceability: immutable GS lot code and source load/purchase.
- Location: reception, production, tank, warehouse, dispatch.
- Production run/batch and olive season.
- Counterparty subsidiary ledger: customer, supplier, employee, state body, sole shareholder.
- Source event: invoice, receipt, supplier payment, sales invoice, credit note, stock movement, production, custody receipt/release, bank transaction.

Dimensions must not change the statutory meaning of NC 01 account codes. They support profitability, stock reconciliation and cost-per-unit analysis without creating hundreds of redundant accounts.

## 4. SUARL controls

- Keep company transactions separate from the sole shareholder's personal transactions.
- Distinguish capital, documented advances/loans, current-account movements, reimbursements and distributions.
- Never classify a shareholder withdrawal as an operating expense by default.
- Require supporting documents and approval for shareholder-related postings.
- Preserve the sole shareholder's decision register and link relevant approvals where legally required.

## 5. Inventory and customer custody

- Company-owned olives/oil may enter company inventory accounts when recognition and measurement criteria are met.
- Customer-owned olives/oil held for pressing or custody must be tracked by owner, lot, location and movement, but must not be recognized as company-owned inventory merely because it is physically on site.
- Pressing revenue, custody obligations, losses, claims and any ownership transfer require transaction-specific policies approved by the accountant.
- Inventory valuation must use a documented policy under NC 04. Retain cost layers and movement history.
- Reconcile stock by product, lot, location and owner. Ownership transfers are paired owner-level movements, not physical receipts or consumption.

## 6. Posting architecture

Proposed collection names only; do not create them until posting rules and migration are approved:
- `accounting_chart_accounts`: NC 01 code, label, parent, class, type, posting eligibility, active dates, approval metadata.
- `accounting_fiscal_periods`: explicitly configured fiscal year and periods.
- `accounting_journals`: sales, purchases, cash, bank, payroll, inventory/production and general journals as approved.
- `accounting_journal_entries`: immutable posted-entry header, journal, date, source event, status, actor and timestamps.
- `accounting_journal_lines`: account, debit, credit, currency, dimensions, counterparty and source.
- `accounting_posting_sources`: unique source type + source ID + event type for idempotency.
- `accounting_tax_codes` / `accounting_tax_rules`: versioned effective-dated rules; no hard-coded VAT rates or blanket suspension.

Invariants:
1. Every posted entry balances exactly: debits = credits.
2. Posted entries are immutable; corrections use linked reversal/adjustment entries.
3. A source event posts at most once; retries are idempotent.
4. Source-state transition and journal posting are atomic where possible.
5. Subsidiary ledgers reconcile to GL control accounts.
6. Use Decimal128 or integer minor units; never binary float for posted money.
7. Every line has account, period, currency, source and audit identity.
8. Backdated posting is blocked or approval-controlled after period close.
9. No statutory posting until chart, fiscal year, opening balances and source mappings are approved.

## 7. Source-to-ledger mapping — design only

| Operational event | Accounting treatment to design | Gate before automation |
|---|---|---|
| Pressing invoice | Service revenue and customer receivable; separate receipt event | Confirm revenue and tax treatment |
| Olive purchase | Inventory/expense and supplier payable/cash according to ownership and contract | Confirm title transfer, valuation and tax |
| Customer-owned custody | Owner subledger and any service revenue/obligation; not company inventory by default | Confirm contract, risk and loss policy |
| Production | Accumulate/transfer eligible conversion costs into output inventory where applicable | Confirm NC 04 cost formula and by-product treatment |
| Oil sale | Revenue, receivable/cash and inventory cost of sales | Confirm ownership, revenue recognition, tax and cost layers |
| Customer/supplier payment | Settle receivable/payable and update cash/bank | Payment method, account and evidence |
| Return/credit note | Adjust original revenue, receivable and inventory as applicable | Link to original posted document |
| Stock loss/adjustment | Approved inventory adjustment and corresponding expense/claim | Count, reason, authorization and audit |
| Fixed-asset acquisition | Asset or expense under capitalization policy | Asset register and NC 05/NC 06 review |
| Depreciation | Periodic depreciation entry | Useful life, method, residual value approval |

No account numbers or debit/credit templates are prescribed here. The Tunisian accountant must approve each mapping.

## 8. VAT suspension evidence gate

The owner reports a VAT suspension, but the official authorization is currently unavailable. Keep the tax profile as `suspension_reported_unverified`. Do not classify the company as non-assujettie and do not suppress VAT globally. A transaction may use suspension only after the authorization, beneficiary, scope, eligible transaction, effective dates, conditions and required wording are verified and approved. Store the applied tax-rule version on each posted document.

## 9. Fiscal year

The owner deferred selecting the fiscal-year closing date. Do not assume 1 January–31 December and do not derive the fiscal year from the olive season. Require explicitly approved start/end dates before annual statutory statements, closing entries or opening-balance carry-forward.

## 10. Approval checklist

- [ ] Current NC 01 nomenclature imported and checked against official source.
- [ ] Accountant-approved Oro Verde subaccounts and account operating rules.
- [ ] Financial-statement mapping approved.
- [ ] Company-owned versus customer-owned stock policy approved.
- [ ] Inventory valuation and production cost allocation under NC 04 approved.
- [ ] Revenue recognition under NC 03 approved for pressing, sales and by-products.
- [ ] Fixed-asset capitalization/depreciation under NC 05/NC 06 approved.
- [ ] Fiscal-year dates and opening balances approved.
- [ ] VAT suspension authorization and scope verified; tax rules approved.
- [ ] Journal templates tested against sample documents.
- [ ] Trial balance and subsidiary-ledger reconciliations signed off.

This is an engineering design specification, not an accountant-approved statutory chart or tax opinion.
