"""Read-only GS sales invoice, receipt and reversal adapters."""
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable
from .normalization import build_candidate_envelope, canonical_decimal, source_fingerprint

def _d(v):
    if hasattr(v, "to_decimal"): v=v.to_decimal()
    if isinstance(v,(bool,float)) or not isinstance(v,(Decimal,str,int)): raise TypeError("Invalid financial decimal")
    d=v if isinstance(v,Decimal) else Decimal(v)
    if not d.is_finite(): raise ValueError("Non-finite decimal")
    return d

def _id(x):
    v=x.get("id",x.get("_id"))
    return str(v) if v is not None and str(v).strip() else None

def _day(v):
    if isinstance(v,datetime): return v.date().isoformat()
    if isinstance(v,date): return v.isoformat()
    if not isinstance(v,str): return None
    try: return date.fromisoformat(v[:10]).isoformat()
    except ValueError:
        try: return datetime.fromisoformat(v.replace("Z","+00:00")).date().isoformat()
        except ValueError: return None

def _at(v):
    if isinstance(v,datetime): return v.isoformat() if v.tzinfo else None
    if not isinstance(v,str) or "T" not in v: return None
    try:
        d=datetime.fromisoformat(v.replace("Z","+00:00"))
        return v if d.tzinfo else None
    except ValueError: return None

def adapt_gs_sales(invoices: Iterable[dict], payments: Iterable[dict]=(), reversals: Iterable[dict]=(), *, treasury_accounts: Iterable[dict]=(), check_payment_snapshots=True):
    """Invoice revenue is informational; receipts/reversals are review candidates only."""
    invs,pays,revs=list(invoices),list(payments),list(reversals)
    accounts={str(a.get("id")):a for a in treasury_accounts if isinstance(a,dict) and a.get("id")}
    byid={_id(x):x for x in invs if isinstance(x,dict) and _id(x)}
    pcounts=Counter(_id(x) for x in pays if isinstance(x,dict) and _id(x))
    rcounts=Counter(_id(x) for x in revs if isinstance(x,dict) and _id(x))
    pby=defaultdict(list); pamount={}; rtotal=defaultdict(lambda:Decimal("0"))
    events=[]; unresolved=[]
    for p in pays:
        if not isinstance(p,dict): unresolved.append({"source_type":"GS_SALE_PAYMENT","reason":"PAYMENT_DOCUMENT_INVALID"}); continue
        iid=str(p.get("invoice_id") or "")
        if iid: pby[iid].append(p)
        if iid not in byid: unresolved.append({"source_type":"GS_SALE_PAYMENT","source_id":_id(p),"reason":"PAYMENT_INVOICE_NOT_IN_PREVIEW_SCOPE"})
    for inv_id,inv in byid.items():
        gross=credit=net=None; day=_day(inv.get("sale_date"))
        try:
            gross=_d(inv.get("total_amount_dt")); credit=_d(inv.get("credited_amount_dt","0")); net=_d(inv.get("net_amount_dt",gross-credit))
            if min(gross,credit,net)<0 or gross-credit!=net: raise ValueError()
        except (TypeError,ValueError,InvalidOperation):
            unresolved.append({"source_type":"GS_SALE_INVOICE","source_id":inv_id,"reason":"SALES_INVOICE_AMOUNT_SNAPSHOT_INVALID"})
        warnings=["REVENUE_RECOGNITION_POLICY_NOT_APPROVED","TAX_TREATMENT_NOT_CONFIGURED"]
        if not day: warnings.append("SALES_INVOICE_DATE_MISSING_OR_INVALID")
        events.append(build_candidate_envelope(
            source_type="GS_SALE_INVOICE",source_id=inv_id,event_type="INVOICE_RECOGNIZED",
            source_facts={"id":inv_id,"document_number":inv.get("document_number"),"sale_id":inv.get("sale_id"),"buyer_id":inv.get("buyer_id"),"sale_date":inv.get("sale_date"),"gross":canonical_decimal(gross) if gross is not None else None,"credited":canonical_decimal(credit) if credit is not None else None,"net":canonical_decimal(net) if net is not None else None},
            eligibility="INFORMATIONAL_ONLY" if net is not None and day else "LEGACY_UNRESOLVED",
            source_document_number=str(inv.get("document_number")) if inv.get("document_number") else None,business_date=day,recorded_at=_at(inv.get("created_at")),
            actor_id=str(inv.get("created_by")) if inv.get("created_by") else None,
            party_ref={"type":"COMMERCIAL_BUYER","id":str(inv["buyer_id"])} if inv.get("buyer_id") else None,
            currency="TND" if net is not None else None,amount=net,
            dimensions={"season_code":str(inv["season_code"])} if inv.get("season_code") else {},
            source_links=[{"type":"GS_SALE","id":str(inv["sale_id"])}] if inv.get("sale_id") else [],warnings=warnings))
    for p in pays:
        if not isinstance(p,dict): continue
        pid=_id(p); iid=str(p.get("invoice_id") or "")
        if not pid: unresolved.append({"source_type":"GS_SALE_PAYMENT","source_id":iid or None,"reason":"PAYMENT_DOCUMENT_ID_MISSING"}); continue
        inv=byid.get(iid); amount=None; blockers=[]
        try:
            amount=_d(p.get("amount_dt"))
            if amount<=0: blockers.append("PAYMENT_AMOUNT_NOT_POSITIVE")
        except (TypeError,ValueError,InvalidOperation): blockers.append("PAYMENT_AMOUNT_INVALID")
        day=_day(p.get("payment_date"))
        if not day: blockers.append("PAYMENT_DATE_MISSING_OR_INVALID")
        if not inv: blockers.append("PAYMENT_INVOICE_NOT_FOUND")
        elif p.get("sale_id")!=inv.get("sale_id"): blockers.append("PAYMENT_SALE_LINK_MISMATCH")
        if pcounts[pid]>1: blockers.append("DUPLICATE_GS_SALE_PAYMENT_ID")
        if p.get("method") in {"BANK_TRANSFER","CHEQUE"} and not (p.get("reference") or "").strip(): blockers.append("BANK_OR_CHEQUE_PAYMENT_REFERENCE_MISSING")
        account_id=str(p.get("treasury_account_id") or "")
        account=accounts.get(account_id)
        if not account_id: blockers.append("TREASURY_ACCOUNT_NOT_ASSIGNED")
        elif not account: blockers.append("TREASURY_ACCOUNT_NOT_FOUND")
        else:
            expected_type="CASH" if p.get("method")=="CASH" else "BANK" if p.get("method") in {"BANK_TRANSFER","CHEQUE"} else None
            if not expected_type or account.get("account_type")!=expected_type: blockers.append("TREASURY_ACCOUNT_TYPE_MISMATCH")
            if account.get("currency")!="TND": blockers.append("TREASURY_ACCOUNT_CURRENCY_NOT_TND")
        events.append(build_candidate_envelope(
            source_type="GS_SALE_PAYMENT",source_id=pid,event_type="PAYMENT_RECEIVED",
            source_facts={"id":pid,"invoice_id":iid,"sale_id":p.get("sale_id"),"number":p.get("document_number"),"amount":str(p.get("amount_dt")),"date":p.get("payment_date"),"method":p.get("method"),"reference":p.get("reference"),"treasury_account_id":account_id or None},
            eligibility="BLOCKED" if blockers else "ELIGIBLE_FOR_REVIEW",blocking_reasons=blockers,
            source_document_number=str(p.get("document_number")) if p.get("document_number") else None,business_date=day,recorded_at=_at(p.get("created_at")),
            actor_id=str(p.get("created_by")) if p.get("created_by") else None,
            party_ref={"type":"COMMERCIAL_BUYER","id":str(inv["buyer_id"])} if inv and inv.get("buyer_id") else None,
            currency="TND" if amount is not None else None,amount=amount,
            dimensions={"season_code":str(p["season_code"])} if p.get("season_code") else {},
            source_links=[{"type":"GS_SALE_INVOICE","id":iid}] if iid else [],
            warnings=["TREASURY_ACCOUNT_MAPPED"] if account_id and account and not any(x.startswith("TREASURY_ACCOUNT_") for x in blockers) else ["TREASURY_ACCOUNT_NOT_MAPPED"]))
        if amount is not None: pamount[pid]=amount
    for r in revs:
        if not isinstance(r,dict): continue
        rid=_id(r); pid=str(r.get("payment_id") or ""); iid=str(r.get("invoice_id") or "")
        original=next((p for p in pays if isinstance(p,dict) and _id(p)==pid),None)
        if not rid: unresolved.append({"source_type":"GS_SALE_PAYMENT_REVERSAL","source_id":pid or None,"reason":"REVERSAL_DOCUMENT_ID_MISSING"}); continue
        amount=None; blockers=[]
        try:
            amount=_d(r.get("amount_dt"))
            if amount<=0: blockers.append("REVERSAL_AMOUNT_NOT_POSITIVE")
        except (TypeError,ValueError,InvalidOperation): blockers.append("REVERSAL_AMOUNT_INVALID")
        day=_day(r.get("reversal_date"))
        if not day: blockers.append("REVERSAL_DATE_MISSING_OR_INVALID")
        if rcounts[rid]>1: blockers.append("DUPLICATE_GS_PAYMENT_REVERSAL_ID")
        if not original: blockers.append("REVERSAL_ORIGINAL_PAYMENT_NOT_FOUND")
        elif original.get("invoice_id")!=iid: blockers.append("REVERSAL_INVOICE_LINK_MISMATCH")
        method=(original or {}).get("method") or r.get("payment_method")
        if method in {"BANK_TRANSFER","CHEQUE"} and not (r.get("evidence_reference") or "").strip(): blockers.append("BANK_OR_CHEQUE_REVERSAL_EVIDENCE_MISSING")
        original_account_id=str((original or {}).get("treasury_account_id") or "")
        reversal_account_id=str(r.get("treasury_account_id") or "")
        if not original_account_id or not reversal_account_id: blockers.append("REVERSAL_TREASURY_ACCOUNT_NOT_ASSIGNED")
        elif reversal_account_id!=original_account_id: blockers.append("REVERSAL_TREASURY_ACCOUNT_LINK_MISMATCH")
        elif reversal_account_id not in accounts: blockers.append("REVERSAL_TREASURY_ACCOUNT_NOT_FOUND")
        events.append(build_candidate_envelope(
            source_type="GS_SALE_PAYMENT_REVERSAL",source_id=rid,event_type="PAYMENT_REVERSED",
            source_facts={"id":rid,"number":r.get("document_number"),"payment_id":pid,"invoice_id":iid,"amount":str(r.get("amount_dt")),"date":r.get("reversal_date"),"status":r.get("status"),"evidence":r.get("evidence_reference"),"treasury_account_id":reversal_account_id or None},
            eligibility="BLOCKED" if blockers else "ELIGIBLE_FOR_REVIEW",blocking_reasons=blockers,
            source_document_number=str(r.get("document_number")) if r.get("document_number") else None,business_date=day,recorded_at=_at(r.get("created_at")),
            actor_id=str(r.get("created_by")) if r.get("created_by") else None,
            party_ref={"type":"COMMERCIAL_BUYER","id":str(r["buyer_id"])} if r.get("buyer_id") else None,
            currency="TND" if amount is not None else None,amount=amount,
            dimensions={"season_code":str(r["season_code"])} if r.get("season_code") else {},
            source_links=([{"type":"GS_SALE_PAYMENT","id":pid}] if pid else [])+([{"type":"GS_SALE_INVOICE","id":iid}] if iid else []),
            warnings=["TREASURY_ACCOUNT_MAPPED","REVERSAL_IS_NOT_A_NEW_SALE"] if reversal_account_id and reversal_account_id==original_account_id and reversal_account_id in accounts else ["TREASURY_ACCOUNT_NOT_MAPPED","REVERSAL_IS_NOT_A_NEW_SALE"]))
        if amount is not None and pid: rtotal[pid]+=amount
    for pid,total in rtotal.items():
        if pid not in pamount or total>pamount[pid]:
            for e in events:
                if e["source_type"]=="GS_SALE_PAYMENT_REVERSAL" and any(x.get("id")==pid for x in e["source_links"]):
                    e["eligibility"]="BLOCKED"; e["blocking_reasons"].append("REVERSALS_EXCEED_ORIGINAL_PAYMENT")
    if check_payment_snapshots:
        for iid,inv in byid.items():
            rows=pby.get(iid,[]); paid=sum((pamount.get(_id(p) or "",Decimal("0")) for p in rows),Decimal("0"))
            reversed=sum((rtotal.get(_id(p) or "",Decimal("0")) for p in rows),Decimal("0"))
            try: snapshot=_d(inv.get("paid_amount_dt","0"))
            except (TypeError,ValueError,InvalidOperation):
                unresolved.append({"source_type":"GS_SALE_INVOICE","source_id":iid,"reason":"INVOICE_PAID_SNAPSHOT_INVALID"}); continue
            if paid-reversed!=snapshot:
                unresolved.append({"source_type":"GS_SALE_INVOICE","source_id":iid,"reason":"SALE_PAYMENT_LEDGER_DOES_NOT_MATCH_INVOICE_PAID_SNAPSHOT",
                    "source_fingerprint":source_fingerprint({"payments":canonical_decimal(paid),"reversals":canonical_decimal(reversed),"snapshot":canonical_decimal(snapshot)})})
                for e in events:
                    if e["source_type"] in {"GS_SALE_PAYMENT","GS_SALE_PAYMENT_REVERSAL"} and any(x.get("id")==iid for x in e["source_links"]):
                        e["eligibility"]="BLOCKED"; e["blocking_reasons"].append("INVOICE_PAID_SNAPSHOT_MISMATCH")
    return {"candidate_events":events,"unresolved_items":unresolved,"read_only":True,"revenue_recognition_enabled":False,"payments_are_revenue":False}
