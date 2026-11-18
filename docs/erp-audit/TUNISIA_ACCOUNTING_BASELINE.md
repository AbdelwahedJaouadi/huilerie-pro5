# Tunisia Accounting and Tax Design Baseline

Project: Oro Verde / huilerie-pro5  
Decision supplied by the owner: the company is registered in Tunisia.  
Status: jurisdiction selected; entity-specific tax configuration remains unapproved.

## 1. Governing accounting framework

The ERP accounting design must target the Tunisian Enterprise Accounting System (`Système Comptable des Entreprises`), not the Tunisian public-sector chart of accounts and not a generic IFRS-only implementation.

Primary framework:
- Law No. 96-112 of 30 December 1996 on the Enterprise Accounting System.
- Decree No. 96-2459 of 30 December 1996 approving the conceptual framework.
- General Accounting Standard NC 01, including financial-statement presentation, accounting organization, chart-of-accounts nomenclature and account operation rules.
- Relevant technical standards, notably NC 03 (revenues), NC 04 (inventories), NC 05 (tangible fixed assets), NC 06 (intangible fixed assets), NC 08 (net income and extraordinary items), NC 11 (accounting changes), and other standards when the transaction requires them.

The Ministry of Finance's National Accounting Council page describes the Enterprise Accounting System as an integrated conceptual framework plus general, technical and sector standards. NC 01 governs the enterprise chart of accounts and financial-statement presentation. The Ministry's accounting obligations page says legal entities and individuals taxed under the real BIC regime must maintain accounting compliant with enterprise accounting legislation.

## 2. ERP architecture consequences

The target accounting engine must be a genuine accrual, double-entry ledger:
- Configurable chart of accounts based on NC 01; no use of the public-sector state chart of accounts.
- Journal entries with balanced debit/credit lines, source-document links, posting timestamps and actor identity.
- Separate draft and posted states. Posted entries are immutable; corrections use linked reversal/adjustment entries.
- General journal, general ledger, subsidiary ledgers, trial balance, and financial statements.
- Period controls, fiscal-year close, opening balances, audit trail and controlled reopening.
- Receivables/payables, cash and bank subledgers, VAT and withholding-tax accounts, inventory valuation, fixed assets and depreciation.
- Cost accounting for olive intake, customer-owned custody, purchases, production batches, tanks, losses, sales and returns.
- All amounts use decimal-safe storage; never binary floating-point for posted financial values.

The accounting period is not the olive season. The default calendar-year assumption may be used for a draft design only; the company's approved accounting year must be confirmed before closing logic is implemented.

## 3. Tax design must be configurable, not hard-coded

The Ministry of Finance lists VAT, corporate income tax, personal income tax, consumption duty, registration/stamp duties and local taxes within the Tunisian tax system. Its published obligations include sequentially numbered invoices/fee notes and compliant accounting. Monthly filing deadlines and exact tax treatment depend on taxpayer type and current law.

Therefore:
- Build a versioned tax-rules configuration with effective dates.
- Keep VAT rates, exemptions, suspension, withholding, stamp duty and tax treatment by product/service/document configurable.
- Store the applied tax-rule version on each posted document.
- Preserve tax base, rate, amount, exemption/suspension reason and supporting legal reference separately.
- Do not infer the mill's VAT status, corporate tax rate, withholding profile, or agricultural/industrial tax treatment from its business description.
- Do not treat a generic olive-oil purchase, pressing service, customer-custody operation or sale as having a tax result until the accountant confirms the exact transaction classification.

## 4. Mandatory business decisions before tax posting goes live

The jurisdiction is settled (Tunisia), but the following remain unknown and must be confirmed by the owner/accountant:
1. Legal form: SUARL, SARL, SA, individual enterprise, cooperative, or another form.
2. Tax regime: real regime or another applicable regime.
3. Tax registration: VAT-liable, VAT suspension/exemption, or not liable; relevant activity registrations.
4. Applicable activity codes and the company's precise tax treatment for olive purchase, toll pressing, customer-owned oil custody, bulk oil sales and by-products.
5. Approved accounting year (calendar year assumed only provisionally).
6. Whether statutory auditor/commissaire aux comptes requirements apply.
7. Opening balances date and approved opening trial balance.
8. Accountant-approved chart of accounts, tax mappings, invoice legal fields and numbering series.

No rate, tax liability, account mapping or statutory filing should be activated solely from this document.

## 5. Practical ERP delivery sequence

1. Build immutable journal and posting infrastructure with a configurable NC 01 chart.
2. Design source-document adapters for traditional invoices, GS olive purchases, supplier payments, customer custody, production, stock, sales, returns and cash/bank receipts.
3. Implement inventory valuation and production cost accounting aligned with NC 04 and relevant standards.
4. Implement receivable/payable and cash/bank subledgers.
5. Add tax calculation only after taxpayer profile and accountant-approved rules are supplied.
6. Generate trial balance and draft financial statements; have the Tunisian accountant validate mappings and outputs before operational posting.
7. Enable period close and statutory exports only after reconciliation and sign-off.

## 6. Official references reviewed

- Ministry of Finance — National Accounting Council / Enterprise Accounting System: https://www.finances.gov.tn/fr/conseil-national-de-la-comptabilite
- Ministry of Finance — Accounting obligations for persons under the real regime: https://www.finances.gov.tn/fr/node/951
- Ministry of Finance — Overview of Tunisian taxation: https://www.finances.gov.tn/fr/apercu-general-sur-la-fiscalite
- Ministry of Finance — Tax regulatory framework: https://www.finances.gov.tn/fr/cadre-reglementaire-6
- Order of Experts Accountants of Tunisia — Tunisian accounting system: https://oect.org.tn/systeme-comptable-tunisien/

This is an engineering design baseline, not a tax or legal opinion. Confirm current legislation and company-specific treatment with a Tunisian chartered accountant before posting statutory accounts.
