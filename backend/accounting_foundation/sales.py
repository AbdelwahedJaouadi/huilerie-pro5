"""Read-only GS sales invoice, receipt and reversal adapters."""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable
from .normalization import build_candidate_envelope, canonical_decimal, source_fingerprint

def _d(value: Any) -> Decimal:
    if hasattr(value, "to_decimal"): value = value.to_decimal()
    if isinstance(value, (bool, float)) or not isinstance(value, (Decimal, str, int)):
        raise TypeError("Invalid financial decimal")
    result = value if isinstance(value, Decimal) else Decimal(value)
    if not result.is_finite(): raise ValueError("Non-finite decimal")
    return result

def _id(row: dict[str, Any]) -> str | None:
    value = row.get("id", row.get("_id"))
    return str(value) if value is not None and str(value).strip() else None

def _day(value: Any) -> str | None:
    if isinstance(value, (date, datetime)): return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    if not isinstance(value, str) or not value.strip(): return None
    try: return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        try: return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
        except ValueError: return None

def _at(value: Any) -> str | None:
    if isinstance(value, datetime): return value.isoformat() if value.tzinfo else None
    if not isinstance(value, str) or "T" not in value: return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value if parsed.tzinfo else None
    except ValueError: return None

def adapt_gs_sales(invoices: Iterable[dict[str, Any]], payments: Iterable[dict[str, Any]] = (),
                   reversals: Iterable[dict[str, Any]] = (), *, check_payment_snapshots: bool = True) -> dict[str, Any]:
    """Compose sale candidates; invoices are informational until revenue/tax policy is approved."""
    invs, pays, revs = list(invoices), list(payments), list(reversals)
    by_invoice = {_id(x): x for x in invs if isinstance(x, dict) and _id(x)}
    payment_counts = Counter(_id(x) for x in pays if isinstance(x, dict) and _id(x))
    reversal_counts = Counter(_id(x) for x in revs if isinstance(x, dict) and _id(x))
    pays_by_invoice, reversals_by_payment = defaultdict(list), defaultdict(list)
    events, unresolved, payment_amounts, reversal_totals = [], [], {}, defaultdict(lambda: Decimal("0"))

    for p in pays:
        if not isinstance(p, dict):
            unresolved.append({"source_type":"GS_SALE_PAYMENT","reason":"PAYMENT_DOCUMENT_INVALID"}); continue
        iid = str(p.get("invoice_id") or "")
        if iid: pays_by_invoice[iid].append(p)
        else: unresolved.append({"source_type":"GS_SALE_PAYMENT","reason":"PAYMENT_INVOICE_LINK_MISSING"})
        if iid not in by_invoice:
            unresolved.append({"source_type":"GS_SALE_PAYMENT","source_id":_id(p),"reason":"PAYMENT_INVOICE_NOT_IN_PREVIEW_SCOPE"})
    for r in revs:
        if not isinstance(r, dict):
            unresolved.append({"source_type":"GS_SALE_PAYMENT_REVERSAL","reason":"REVERSAL_DOCUMENT_INVALID"}); continue
        pid = str(r.get("payment_id") or "")
        if pid: reversals_by_payment[pid].append(r)
        else: unresolved.append({"source_type":"GS_SALE_PAYMENT_REVERSAL","reason":"REVERSAL_PAYMENT_LINK_MISSING"})

    for iid, inv in by_invoice.items():
        day = _day(inv.get("sale_date")); gross = credited = net = None
        try:
            gross = _d(inv.get("total_amount_dt")); credited = _d(inv.get("credited_amount_dt", "0"))
            net = _d(inv.get("net_amount_dt", gross - credited))
            if min(gross, credited, net) < 0 or gross - credited != net: raise ValueError("snapshot mismatch")
        except (TypeError, ValueError, InvalidOperation):
            unresolved.append({"source_type":"GS_SALE_INVOICE","source_id":iid,"reason":"SALES_INVOICE_AMOUNT_SNAPSHOT_INVALID"})
        warnings = ["REVENUE_RECOGNITION_POLICY_NOT_APPROVED","TAX_TREATMENT_NOT_CONFIGURED"]
        if not day: warnings.append("SALES_INVOICE_DATE_MISSING_OR_INVALID")
        events.append(build_candidate_envelope(
            source_type="GS_SALE_INVOICE", source_id=iid, event_type="INVOICE_RECOGNIZED",
            source_facts={"id":iid,"document_number":inv.get("document_number"),"sale_id":inv.get("sale_id"),
              "buyer_id":inv.get("buyer_id"),"sale_date":inv.get("sale_date"),
              "total_amount_dt":canonical_decimal(gross) if gross is not None else None,
              "credited_amount_dt":canonical_decimal(credited) if credited is not None else None,
              "net_amount_dt":canonical_decimal(net) if net is not None else None,
              "tax_treatment_status":inv.get("tax_treatment_status")},
            eligibility="INFORMATIONAL_ONLY" if net is not None and day else "LEGACY_UNRESOLVED",
            source_document_number=str(inv.get("document_number")) if inv.get("document_number") else None,
            business_date=day, recorded_at=_at(inv.get("created_at")),
            actor_id=str(inv.get("created_by")) if inv.get("created_by") else None,
            party_ref={"type":"COMMERCIAL_BUYER","id":str(inv["buyer_id"])} if inv.get("buyer_id") else None,
            currency="TND" if net is not None else None, amount=net,
            dimensions={"season_code":str(inv["season_code"])} if inv.get("season_code") else {},
            source_links=[{"type":"GS_SALE","id":str(inv["sale_id"])}] if inv.get("sale_id") else [],
            warnings=warnings))

    for p in pays:
        if not isinstance(p, dict): continue
        pid, iid = _id(p), str(p.get("invoice_id") or "")
        if not pid:
            unresolved.append({"source_type":"GS_SALE_PAYMENT","source_id":iid or None,"reason":"PAYMENT_DOCUMENT_ID_MISSING"}); continue
        inv = by_invoice.get(iid); blockers=[]; amount=None
        try:
            amount=_d(p.get("amount_dt"))
            if amount <= 0: blockers.append("PAYMENT_AMOUNT_NOT_POSITIVE")
        except (TypeError, ValueError, InvalidOperation): blockers.append("PAYMENT_AMOUNT_INVALID")
        day=_day(p.get("payment_date"))
        if not day: blockers.append("PAYMENT_DATE_MISSING_OR_INVALID")
        if not inv: blockers.append("PAYMENT_INVOICE_NOT_FOUND")
        elif p.get("sale_id") != inv.get("sale_id"): blockers.append("PAYMENT_SALE_LINK_MISMATCH")
        if payment_counts[pid] > 1: blockers.append("DUPLICATE_GS_SALE_PAYMENT_ID")
        if p.get("method") in {"BANK_TRANSFER","CHEQUE"} and not (p.get("reference") or "").strip():
            blockers.append("BANK_OR_CHEQUE_PAYMENT_REFERENCE_MISSING")
        events.append(build_candidate_envelope(
            source_type="GS_SALE_PAYMENT", source_id=pid, event_type="PAYMENT_RECEIVED",
            source_facts={"id":pid,"invoice_id":iid,"sale_id":p.get("sale_id"),
              "document_number":p.get("document_number"),"amount_dt":str(p.get("amount_dt")),
              "payment_date":p.get("payment_date"),"method":p.get("method"),"reference":p.get("reference")},
            eligibility="BLOCKED" if blockers else "ELIGIBLE_FOR_REVIEW", blocking_reasons=blockers,
            source_document_number=str(p.get("document_number")) if p.get("document_number") else None,
            business_date=day, recorded_at=_at(p.get("created_at")),
            actor_id=str(p.get("created_by")) if p.get("created_by") else None,
            party_ref={"type":"COMMERCIAL_BUYER","id":str(inv["buyer_id"])} if inv and inv.get("buyer_id") else None,
            currency="TND" if amount is not None else None, amount=amount,
            dimensions={"season_code":str(p["season_code"])} if p.get("season_code") else {},
            source_links=[{"type":"GS_SALE_INVOICE","id":iid}] if iid else [],
            warnings=["TREASURY_ACCOUNT_NOT_MAPPED","PAYMENT_METHOD_IS_NOT_A_FINANCIAL_ACCOUNT"]))
        if amount is not None: payment_amounts[pid]=amount

    for r in revs:
        if not isinstance(r, dict): continue
        rid, pid, iid = _id(r), str(r.get("payment_id") or ""), str(r.get("invoice_id") or "")
        original=next((p for p in pays if isinstance(p,dict) and _id(p)==pid),None)
        if not rid:
            unresolved.append({"source_type":"GS_SALE_PAYMENT_REVERSAL","source_id":pid or None,"reason":"REVERSAL_DOCUMENT_ID_MISSING"}); continue
        blockers=[]; amount=None
        try:
            amount=_d(r.get("amount_dt"))
            if amount <= 0: blockers.append("REVERSAL_AMOUNT_NOT_POSITIVE")
        except (TypeError, ValueError, InvalidOperation): blockers.append("REVERSAL_AMOUNT_INVALID")
        day=_day(r.get("reversal_date"))
        if not day: blockers.append("REVERSAL_DATE_MISSING_OR_INVALID")
        if reversal_counts[rid] > 1: blockers.append("DUPLICATE_GS_PAYMENT_REVERSAL_ID")
        if not original: blockers.append("REVERSAL_ORIGINAL_PAYMENT_NOT_FOUND")
        elif original.get("invoice_id") != iid: blockers.append("REVERSAL_INVOICE_LINK_MISMATCH")
        method=(original or {}).get("method") or r.get("payment_method")
        if method in {"BANK_TRANSFER","CHEQUE"} and not (r.get("evidence_reference") or "").strip():
            blockers.append("BANK_OR_CHEQUE_REVERSAL_EVIDENCE_MISSING")
        events.append(build_candidate_envelope(
            source_type="GS_SALE_PAYMENT_REVERSAL",source_id=rid,event_type="PAYMENT_REVERSED",
            source_facts={"id":rid,"document_number":r.get("document_number"),"payment_id":pid,
              "invoice_id":iid,"amount_dt":str(r.get("amount_dt")),"reversal_date":r.get("reversal_date"),
              "status":r.get("status"),"evidence_reference":r.get("evidence_reference"),"reason":r.get("reason")},
            eligibility="BLOCKED" if blockers else "ELIGIBLE_FOR_REVIEW",blocking_reasons=blockers,
            source_document_number=str(r.get("document_number")) if r.get("document_number") else None,
            business_date=day,recorded_at=_at(r.get("created_at")),
            actor_id=str(r.get("created_by")) if r.get("created_by") else None,
            party_ref={"type":"COMMERCIAL_BUYER","id":str(r["buyer_id"])} if r.get("buyer_id") else None,
            currency="TND" if amount is not None else None,amount=amount,
            dimensions={"season_code":str(r["season_code"])} if r.get("season_code") else {},
            source_links=([{"type":"GS_SALE_PAYMENT","id":pid}] if pid else [])+([{"type":"GS_SALE_INVOICE","id":iid}] if iid else []),
            warnings=["TREASURY_ACCOUNT_NOT_MAPPED","REVERSAL_IS_NOT_A_NEW_SALE"]))
        if amount is not None and pid: reversal_totals[pid]+=amount

    for pid, total in reversal_totals.items():
        if pid not in payment_amounts or total > payment_amounts[pid]:
            for event in events:
                if event["source_type"]=="GS_SALE_PAYMENT_REVERSAL" and any(x.get("id")==pid for x in event["source_links"]):
                    event["eligibility"]="BLOCKED"; event["blocking_reasons"].append("REVERSALS_EXCEED_ORIGINAL_PAYMENT")

    if check_payment_snapshots:
        for iid, inv in by_invoice.items():
            rows=pays_by_invoice.get(iid,[])
            paid=sum((payment_amounts.get(_id(p) or "",Decimal("0")) for p in rows),Decimal("0"))
            reversed_amount=sum((reversal_totals.get(_id(p) or "",Decimal("0")) for p in rows),Decimal("0"))
            try:
                snapshot=_d(inv.get("paid_amount_dt","0"))
                if paid-reversed_amount != snapshot:
                    unresolved.append({"source_type":"GS_SALE_INVOICE","source_id":iid,
                      "reason":"SALE_PAYMENT_LEDGER_DOES_NOT_MATCH_INVOICE_PAID_SNAPSHOT",
                      "source_fingerprint":source_fingerprint({"payment_total":canonical_decimal(paid),
                        "reversal_total":canonical_decimal(reversed_amount),"invoice_paid_snapshot":canonical_decimal(snapshot)})})
                    for event in events:
                        if event["source_type"] in {"GS_SALE_PAYMENT","GS_SALE_PAYMENT_REVERSAL"} and any(x.get("id")==iid for x in event["source_links"]):
                            event["eligibility"]="BLOCKED"; event["blocking_reasons"].append("INVOICE_PAID_SNAPSHOT_MISMATCH")
            except (TypeError,ValueError,InvalidOperation):
                unresolved.append({"source_type":"GS_SALE_INVOICE","source_id":iid,"reason":"INVOICE_PAID_SNAPSHOT_INVALID"})
    return {"candidate_events":events,"unresolved_items":unresolved,"read_only":True,
            "revenue_recognition_enabled":False,"payments_are_revenue":False}
