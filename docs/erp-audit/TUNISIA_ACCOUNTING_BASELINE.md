# Tunisia Accounting and Tax Design Baseline

Project: Oro Verde / huilerie-pro5  
Decisions supplied by the owner: the company is registered in Tunisia, its legal form is SUARL (Société Unipersonnelle à Responsabilité Limitée), and it operates under the régime réel.  
Status: jurisdiction, legal form and declared tax regime are owner-confirmed. VAT suspension is owner-reported but documentary evidence is currently unavailable; legal scope, validity dates and transaction-specific treatment are unverified. No automated suspension treatment may be activated until evidence is reviewed.

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
- Keep VAT rates, exemptions, suspension, withholding, stamp duty and tax treatment by product/service/document configurable. A VAT suspension must be represented separately from ordinary exemption and non-registration, with supporting authorization, scope, validity interval, conditions and documentary references.
- Store the applied tax-rule version on each posted document.
- Preserve tax base, rate, amount, exemption/suspension reason and supporting legal reference separately.
- The owner selected the régime réel. Do not infer the mill's VAT status, applicable corporate income-tax rate, withholding profile, minimum tax, or agricultural/industrial tax treatment from this selection or from its business description.
- Do not treat a generic olive-oil purchase, pressing service, customer-custody operation or sale as having a tax result until the accountant confirms the exact transaction classification.

## 4. Mandatory business decisions before tax posting goes live

The jurisdiction is settled (Tunisia), but the following remain unknown and must be confirmed by the owner/accountant:
1. ~~Legal form~~ **Resolved: SUARL (Société Unipersonnelle à Responsabilité Limitée)**. The sole shareholder may be a natural or legal person under Article 149 of the Tunisian Commercial Companies Code. The SUARL is governed by the SARL regime subject to the specific SUARL provisions (Article 148).
2. ~~Tax regime~~ **Owner-confirmed: régime réel.** As a SUARL, the company is a legal person and must maintain accounting compliant with Tunisian enterprise-accounting legislation. The exact corporate-tax treatment and any special activity-specific provisions still require accountant confirmation.
3. ~~VAT status~~ **Owner-confirmed: the company has a VAT suspension (`suspension de TVA`).** Record the suspension as a distinct, evidence-backed tax status; do not treat it as permanent non-liability or a blanket exemption. Verify the official suspension certificate/authorization, beneficiary identity, covered purchases or transactions, suppliers/customers where relevant, effective and expiry dates, ceilings/conditions, and required invoice wording before enabling automated treatment.
4. Applicable activity codes and the company's precise tax treatment for olive purchase, toll pressing, customer-owned oil custody, bulk oil sales and by-products.
5. Approved accounting year (calendar year assumed only provisionally).
6. Whether statutory auditor/commissaire aux comptes requirements apply.
7. Opening balances date and approved opening trial balance.
8. Accountant-approved chart of accounts, tax mappings, invoice legal fields and numbering series.

### SUARL-specific accounting and governance requirements

- Maintain a clear separation between the company's assets/liabilities and the sole shareholder's personal transactions. Record shareholder contributions, shareholder current-account movements, reimbursements, loans and distributions as distinct, documented transaction types; never treat a shareholder withdrawal as an ordinary operating expense by default.
- Support the sole shareholder's signed decisions and a dedicated register of decisions, rather than assuming multi-member shareholder meeting workflows.
- Under Article 153, the sole shareholder establishes the management report, inventory and annual accounts (with the statutory auditor's report where applicable) and approves them within three months of the accounts' closing date.
- Under Article 154, resolutions are signed by the sole shareholder or the authorized proxy and recorded in the special register prescribed by law.
- Determine statutory auditor requirements from the company's actual size, activity and current law; do not assume that SUARL status automatically exempts or requires an auditor.
- These are system requirements, not a substitute for confirmation by the company's Tunisian accountant or legal adviser.

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


## 7. Owner-confirmed tax regime (17 Nov 2026)

The owner confirmed **régime réel** for the SUARL. The Ministry of Finance states that legal entities and individuals taxed under the real BIC regime must keep accounting compliant with enterprise-accounting legislation. The company is therefore designed for full compliant enterprise accounting, not a simplified cash register. The selected regime does not by itself establish VAT registration/status, a specific corporate tax rate, withholding profile, or the tax classification of each mill activity. Those remain versioned configuration items pending accountant confirmation.

Official reference: Ministry of Finance — https://www.finances.gov.tn/fr/node/951


## 8. Owner-confirmed VAT suspension (17 Nov 2026)

The owner reports that the SUARL has a **suspension de TVA**. This is not to be modelled as `non assujettie` and must not be treated as an unlimited or permanent exemption. Until the current authorization/certificate is checked, the ERP must not automatically suppress VAT on every purchase or sale. The tax engine should support a suspension authorization record with at least: authorization/reference number, beneficiary legal identity, scope (eligible transactions/products/services and counterparties as specified), effective-from and expiry dates, any ceilings or conditions, supporting document, and the invoice/document wording required by the authorization and current law. Each transaction must be evaluated against the active authorization and its scope; out-of-scope or expired transactions follow the otherwise applicable tax treatment. Final configuration and invoice wording require the Tunisian accountant's validation.


## 9. VAT suspension evidence status (17 Nov 2026)

The owner confirms that the SUARL has a VAT suspension but states that the official certificate/authorization is not currently available.

Implementation status:
- Tax profile: `suspension_reported_unverified`.
- Evidence status: `missing`.
- Do not mark the company as `non_assujettie`.
- Do not suppress VAT globally, infer that all purchases/sales are covered, or print suspension wording on invoices without the applicable authorization and accountant approval.
- Keep tax calculation configurable and transaction-specific. Until evidence is supplied, the ERP must flag the tax treatment for accountant review rather than silently applying a suspension.
- When evidence becomes available, capture the issuing authority, authorization number, beneficiary identity, scope, eligible transaction types/counterparties, effective date, expiry date, ceilings/conditions, required document wording, file reference and reviewer/verification date.
- Expired, out-of-scope or unverified transactions must not inherit a suspension automatically.

This is a control state for software design, not a legal conclusion that the suspension is valid or invalid.
