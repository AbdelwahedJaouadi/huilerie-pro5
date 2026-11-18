# Tax Configuration and Invoice Compliance Audit

Project: huilerie-pro5  
Base: main at `e1bc0b838ca9d48e5f6eb375a731d5d5e843c37f`  
Method: static inspection of traditional invoice creation, GS sale invoice creation, accounting schemas and the Tunisia accounting baseline. No live tax records or invoices changed.

## 1. Executive finding

The company profile decisions are known: Tunisia, SUARL, régime réel. The owner reports a suspension de TVA, but the official authorization is not currently available for review. The runtime does not yet implement a versioned transaction-level tax engine.

The tax state must remain **unverified / not configured for automatic posting**. Do not infer a blanket VAT exemption, non-registration or zero-rate treatment from the reported suspension.

## 2. Traditional pressing invoice

The inspected `backend/routers/invoices.py` invoice creation path calculates:
- oil quantity;
- tariff per kg;
- total;
- paid amount and balance.

The invoice document has no explicit tax base, VAT rate, VAT amount, tax treatment code, suspension/exemption reason, stamp duty, withholding or tax-rule version fields. The traditional invoice API does not apply a tax calculation or record a legal authorization reference.

This means the current invoice total is a commercial amount calculation, not proof that the invoice meets all statutory tax-content requirements for every relevant transaction type.

## 3. GS wholesale invoice

The inspected `backend/commercial/services/sales.py` creates a commercial sales invoice with:
- quantity and unit price;
- `total_amount_dt`;
- paid, credited, net and outstanding amounts;
- `tax_treatment_status = NOT_CONFIGURED`.

No tax amount/base/rate or active authorization snapshot is calculated in this flow. The explicit status correctly signals that tax treatment is not configured; it must not be silently replaced with a presumed suspension.

## 4. Tax authorization requirements

Before automated VAT treatment is enabled, obtain and validate the official suspension certificate/authorization and record at least:
- authorization/reference number and issuing authority;
- exact beneficiary legal identity and tax identifiers;
- effective-from and expiry dates;
- transaction scope: eligible products/services, purchase/sale direction, counterparties or supplier/customer restrictions where stated;
- ceilings, quotas, conditions and required approvals, if any;
- required invoice wording and supporting document references;
- evidence file and date/actor of verification;
- revocation, renewal or amendment history.

The tax engine must evaluate each transaction against the valid authorization scope. An out-of-scope transaction or an expired authorization must use the otherwise applicable tax rules, not inherit suspension automatically.

## 5. Versioned tax-rule model

Create a controlled tax configuration with:
- taxpayer profile and effective dates;
- transaction tax category (pressing service, mill-owned olive purchase, customer-custody service, customer-to-mill purchase, bulk oil sale, by-product, asset purchase, payroll, etc.);
- tax code, base, rate, amount and currency;
- exemption vs suspension vs non-liability vs outside-scope distinctions;
- withholding/stamp duty/other applicable taxes as separate components;
- rule version and effective-from/effective-to dates;
- authorization reference and evidence where relevant;
- accountant approval identity/time;
- immutable snapshot of the exact applied rule on each posted document.

Tax changes must not silently recalculate historical posted invoices. Correct them with approved adjustment/credit/debit documents under the applicable law.

## 6. Open professional determinations

The following must be decided by the Tunisian accountant from the current law and the company's actual contracts/activity:
1. Exact VAT registration status and legal scope of the suspension authorization.
2. VAT treatment of olive purchases from farmers and suppliers, including any special agricultural regime or withholding/documentation.
3. VAT treatment of toll pressing for customer-owned olives and any related services.
4. VAT treatment of customer-to-mill ownership purchases of olives or oil.
5. VAT treatment of bulk oil sales and by-products.
6. Stamp duty, withholding taxes, invoice wording and mandatory identifiers.
7. Corporate income tax and other activity-specific taxes; régime réel alone does not establish a single applicable rate.
8. Tax treatment of payroll, benefits, social contributions, fixed assets and depreciation.

Do not hard-code rates or tax outcomes in the absence of signed accountant-approved rules.

## 7. Acceptance gates

1. Expired suspension authorization is not applied.
2. In-scope transaction uses the correct versioned authorization snapshot and mandatory wording.
3. Out-of-scope product/service/customer/supplier does not inherit the suspension.
4. Traditional pressing and GS wholesale invoices show tax treatment explicitly; no silent zero-tax assumption.
5. Credit/debit notes reference the original invoice and preserve the original tax-rule snapshot.
6. Historical posted documents retain their original tax snapshot after a new rule version becomes effective.
7. Tax bases, amounts, withholding, stamp duty and TND totals reconcile exactly using Decimal arithmetic.
8. Accountant approval, evidence file, effective dates and authorization scope are auditable.

## 8. Boundaries

This is an engineering source audit and control design, not a Tunisian tax opinion. No tax rate, tax mapping, tax authorization, invoice amount or live record was changed. Automatic tax calculation remains disabled until the official authorization and transaction-specific treatment are verified by the Tunisian accountant.
