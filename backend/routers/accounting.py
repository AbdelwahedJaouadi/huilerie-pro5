"""Read-only accounting overview scoped to the active olive season.

Financial totals are aggregated from authoritative source documents for the active
season only. Recent-document lists are bounded for display and never drive totals.
"""
from __future__ import annotations

import asyncio
import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation
from typing import Any, Literal
from uuid import uuid4

from bson.decimal128 import Decimal128
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from lib.auth import require_admin
from lib.db import db, run_transaction
from lib.season import active_season, season_prefix
from accounting_foundation.preview import build_reconciliation_preview
from accounting_foundation.treasury_preview import build_treasury_movement_preview
from accounting_foundation.treasury_posting import record_source_payment_movement
from accounting_foundation.treasury_register import build_movement_register_filter

router = APIRouter(prefix="/accounting", tags=["accounting"])
RECENT_LIMIT = 200


def _safe(value: Any) -> Any:
    if isinstance(value, Decimal128):
        return str(value.to_decimal())
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items() if key != "_id"}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


async def _recent(
    collection: str, sort_field: str = "created_at",
    limit: int | None = RECENT_LIMIT, match: dict | None = None,
):
    docs = await db[collection].find(match or {}, {"_id": 0}).sort(sort_field, -1).to_list(limit)
    return _safe(docs)


def _sum_pipeline(field: str, match: dict | None = None) -> list[dict]:
    """Build a Decimal128 aggregation; never route money through binary float."""
    pipeline = []
    if match:
        pipeline.append({"$match": match})
    pipeline.extend([
        {"$group": {"_id": None, "total": {"$sum": {
            "$convert": {"input": f"${field}", "to": "decimal", "onError": 0, "onNull": 0}
        }}}},
        {"$project": {"_id": 0, "total": {"$toString": "$total"}}},
    ])
    return pipeline


async def _sum(collection: str, field: str, match: dict | None = None) -> str:
    """Sum a numeric/Decimal128/string field server-side across matching records."""
    rows = await db[collection].aggregate(_sum_pipeline(field, match)).to_list(1)
    return rows[0]["total"] if rows else "0.000"


async def _supplier_outstanding_total(match: dict) -> str:
    """Include legacy approved purchases that predate the explicit outstanding snapshot."""
    amount = {"$convert": {"input": {"$ifNull": ["$total_amount_dt", 0]}, "to": "decimal", "onError": 0, "onNull": 0}}
    paid = {"$convert": {"input": {"$ifNull": ["$paid_amount_dt", 0]}, "to": "decimal", "onError": 0, "onNull": 0}}
    outstanding = {"$convert": {
        "input": {"$ifNull": ["$outstanding_amount_dt", {"$subtract": [amount, paid]}]},
        "to": "decimal", "onError": 0, "onNull": 0,
    }}
    rows = await db.commercial_olive_purchases.aggregate([
        {"$match": match},
        {"$group": {"_id": None, "total": {"$sum": {"$max": [outstanding, 0]}}}},
        {"$project": {"_id": 0, "total": {"$toString": "$total"}}},
    ]).to_list(1)
    return rows[0]["total"] if rows else "0.000"


def _filter_accounting_period(rows: list[dict], start_day: str | None, end_day: str | None, fields: tuple[str, ...]) -> list[dict]:
    if not start_day and not end_day:
        return rows
    filtered = []
    for row in rows:
        value = next((row.get(field) for field in fields if row.get(field)), None)
        day = _accounting_day(value)
        if day and (not start_day or day >= start_day) and (not end_day or day <= end_day):
            filtered.append(row)
    return filtered


def _sum_accounting_rows(rows: list[dict], field: str) -> str:
    total = sum((_accounting_decimal(row.get(field)) for row in rows), Decimal("0.000"))
    return format(total, "f")


def _outstanding_accounting_rows(rows: list[dict]) -> str:
    total = Decimal("0.000")
    for row in rows:
        amount = _accounting_decimal(row.get("outstanding_amount_dt"))
        if "outstanding_amount_dt" not in row or row.get("outstanding_amount_dt") is None:
            amount = _accounting_decimal(row.get("total_amount_dt")) - _accounting_decimal(row.get("paid_amount_dt"))
        total += max(amount, Decimal("0.000"))
    return format(total, "f")


@router.get("/overview")
async def accounting_overview(
    start_date: str | None = None,
    end_date: str | None = None,
    _: dict = Depends(require_admin),
):
    """Read-only accounting overview; optional inclusive business-date range."""
    start_day = end_day = None
    try:
        if start_date:
            start_day = date.fromisoformat(start_date).isoformat()
        if end_date:
            end_day = date.fromisoformat(end_date).isoformat()
    except ValueError:
        raise HTTPException(status_code=422, detail="Date invalide. Format attendu : AAAA-MM-JJ.")
    if start_day and end_day and start_day > end_day:
        raise HTTPException(status_code=422, detail="La date de début doit précéder ou égaler la date de fin.")
    period_selected = bool(start_day or end_day)

    season = await active_season()
    season_code = season_prefix(season)
    commercial_match = {"season_code": season_code}
    seasonal_load_ids = await db.loads.distinct("id", {"season_id": season})
    invoice_match = {"load_id": {"$in": seasonal_load_ids}}

    # A date-filtered report must not inherit the 200-row display cap.
    fetch_limit = None if period_selected else RECENT_LIMIT
    (
        invoices, olive_purchases, supplier_payments, internal_movements, oil_purchases,
        sales_invoices, sale_payments, oil_payments, credit_notes, suppliers, owners,
    ) = await asyncio.gather(
        _recent("invoices", "day", fetch_limit, invoice_match),
        _recent("commercial_olive_purchases", "created_at", fetch_limit, commercial_match),
        _recent("commercial_supplier_olive_purchase_payments", "payment_date", fetch_limit, commercial_match),
        _recent("commercial_internal_movements", "created_at", fetch_limit, commercial_match),
        _recent("commercial_oil_purchase_documents", "created_at", fetch_limit, commercial_match),
        _recent("commercial_sales_invoices", "created_at", fetch_limit, commercial_match),
        _recent("commercial_sale_payments", "created_at", fetch_limit, commercial_match),
        _recent("commercial_oil_purchase_payments", "created_at", fetch_limit, commercial_match),
        _recent("commercial_credit_notes", "created_at", fetch_limit, commercial_match),
        _recent("commercial_suppliers", "name", 1000),
        _recent("commercial_custody_owners", "client_name", 5000),
    )

    all_invoices_for_payments = invoices
    traditional_invoice_payments = []
    for invoice in all_invoices_for_payments:
        invoice_payments = invoice.get("payments") if isinstance(invoice.get("payments"), list) else []
        if invoice_payments:
            for payment in invoice_payments:
                payment_day = _accounting_day(payment.get("at") or payment.get("payment_date") or payment.get("paid_at"))
                if payment_day and (not period_selected or (not start_day or payment_day >= start_day) and (not end_day or payment_day <= end_day)):
                    traditional_invoice_payments.append({
                        "id": f"{invoice.get('id', '')}:{payment.get('at', '')}:{payment.get('amount', '')}",
                        "invoice_id": invoice.get("id"),
                        "invoice_number": invoice.get("number"),
                        "client_name": invoice.get("client_name"),
                        "payment_date": payment.get("at") or payment.get("payment_date") or payment.get("paid_at"),
                        "amount": _safe(payment.get("amount", "0")),
                        "paid_by": payment.get("by"),
                    })
        elif _accounting_decimal(invoice.get("paid_amount")) > 0:
            invoice_day = _accounting_day(invoice.get("day") or invoice.get("created_at"))
            if invoice_day and (not period_selected or (not start_day or invoice_day >= start_day) and (not end_day or invoice_day <= end_day)):
                traditional_invoice_payments.append({
                    "id": f"{invoice.get('id', '')}:legacy",
                    "invoice_id": invoice.get("id"),
                    "invoice_number": invoice.get("number"),
                    "client_name": invoice.get("client_name"),
                    "payment_date": invoice.get("day") or invoice.get("created_at"),
                    "amount": _safe(invoice.get("paid_amount")),
                    "paid_by": None,
                })

    if period_selected:
        invoices = _filter_accounting_period(invoices, start_day, end_day, ("day", "created_at"))
        olive_purchases = _filter_accounting_period(olive_purchases, start_day, end_day, ("purchase_date", "day", "created_at"))
        supplier_payments = _filter_accounting_period(supplier_payments, start_day, end_day, ("payment_date", "paid_at", "day", "created_at"))
        internal_movements = _filter_accounting_period(internal_movements, start_day, end_day, ("movement_date", "day", "created_at"))
        oil_purchases = _filter_accounting_period(oil_purchases, start_day, end_day, ("purchase_date", "day", "created_at"))
        sales_invoices = _filter_accounting_period(sales_invoices, start_day, end_day, ("sale_date", "day", "created_at"))
        sale_payments = _filter_accounting_period(sale_payments, start_day, end_day, ("payment_date", "paid_at", "day", "created_at"))
        oil_payments = _filter_accounting_period(oil_payments, start_day, end_day, ("payment_date", "paid_at", "day", "created_at"))
        credit_notes = _filter_accounting_period(credit_notes, start_day, end_day, ("issue_date", "credit_note_date", "day", "created_at"))

    supplier_names = {str(item.get("id")): item.get("name") for item in suppliers}
    owner_names = {str(item.get("id")): item.get("client_name") for item in owners}
    for purchase in olive_purchases:
        purchase["supplier_name"] = supplier_names.get(str(purchase.get("supplier_id")))
    for movement in internal_movements:
        source_owner = movement.get("source_owner") or {}
        movement["customer_name"] = owner_names.get(str(source_owner.get("customer_id")))

    approved_supplier_purchases = [row for row in olive_purchases if row.get("status") == "APPROVED"]
    customer_olive_purchases = [row for row in oil_purchases if row.get("product_kind") == "OLIVE"]
    customer_oil_purchases = [row for row in oil_purchases if row.get("product_kind", "OIL") == "OIL"]
    customer_olive_payments = [row for row in oil_payments if row.get("product_kind") == "OLIVE"]
    customer_oil_payments = [row for row in oil_payments if row.get("product_kind", "OIL") == "OIL"]

    if period_selected:
        summary = {
            "pressing_revenue_total": _sum_accounting_rows(invoices, "total"),
            "pressing_collected_total": _sum_accounting_rows(traditional_invoice_payments, "amount"),
            "gs_sales_revenue_total": _sum_accounting_rows(sales_invoices, "net_amount_dt"),
            "gs_sales_collected_total": _sum_accounting_rows(sales_invoices, "paid_amount_dt"),
            "supplier_olive_purchase_total": _sum_accounting_rows(approved_supplier_purchases, "total_amount_dt"),
            "supplier_olive_paid_total": _sum_accounting_rows(supplier_payments, "amount_tnd"),
            "supplier_olive_outstanding_total": _outstanding_accounting_rows(approved_supplier_purchases),
            "customer_olive_purchase_total": _sum_accounting_rows(customer_olive_purchases, "agreed_amount_tnd"),
            "customer_olive_paid_total": _sum_accounting_rows(customer_olive_payments, "amount_tnd"),
            "customer_oil_purchase_total": _sum_accounting_rows(customer_oil_purchases, "agreed_amount_tnd"),
            "customer_oil_paid_total": _sum_accounting_rows(customer_oil_payments, "amount_tnd"),
        }
    else:
        (
            pressing_revenue, pressing_collected, gs_sales_revenue, gs_collected,
            supplier_olive_total, supplier_olive_paid, supplier_olive_outstanding,
            customer_olive_total, customer_olive_paid, customer_oil_total, customer_oil_paid,
        ) = await asyncio.gather(
            _sum("invoices", "total", invoice_match),
            _sum("invoices", "paid_amount", invoice_match),
            _sum("commercial_sales_invoices", "net_amount_dt", commercial_match),
            _sum("commercial_sales_invoices", "paid_amount_dt", commercial_match),
            _sum("commercial_olive_purchases", "total_amount_dt", {**commercial_match, "status": "APPROVED"}),
            _sum("commercial_supplier_olive_purchase_payments", "amount_tnd", commercial_match),
            _supplier_outstanding_total({**commercial_match, "status": "APPROVED"}),
            _sum("commercial_oil_purchase_documents", "agreed_amount_tnd", {**commercial_match, "product_kind": "OLIVE"}),
            _sum("commercial_oil_purchase_payments", "amount_tnd", {**commercial_match, "product_kind": "OLIVE"}),
            _sum("commercial_oil_purchase_documents", "agreed_amount_tnd", {**commercial_match, "$or": [{"product_kind": "OIL"}, {"product_kind": {"$exists": False}}]}),
            _sum("commercial_oil_purchase_payments", "amount_tnd", {**commercial_match, "$or": [{"product_kind": "OIL"}, {"product_kind": {"$exists": False}}]}),
        )
        summary = {
            "pressing_revenue_total": pressing_revenue,
            "pressing_collected_total": pressing_collected,
            "gs_sales_revenue_total": gs_sales_revenue,
            "gs_sales_collected_total": gs_collected,
            "supplier_olive_purchase_total": supplier_olive_total,
            "supplier_olive_paid_total": supplier_olive_paid,
            "supplier_olive_outstanding_total": supplier_olive_outstanding,
            "customer_olive_purchase_total": customer_olive_total,
            "customer_olive_paid_total": customer_olive_paid,
            "customer_oil_purchase_total": customer_oil_total,
            "customer_oil_paid_total": customer_oil_paid,
        }

    return {
        "active_season": season,
        "season_code": season_code,
        "traditional_invoices": invoices,
        "traditional_invoice_payments": traditional_invoice_payments,
        "supplier_olive_purchases": olive_purchases,
        "supplier_olive_purchase_payments": supplier_payments,
        "customer_ownership_transfers": internal_movements,
        "customer_olive_purchases": customer_olive_purchases,
        "customer_oil_purchases": customer_oil_purchases,
        "commercial_sales_invoices": sales_invoices,
        "commercial_sale_payments": sale_payments,
        "customer_olive_purchase_payments": customer_olive_payments,
        "customer_oil_purchase_payments": customer_oil_payments,
        "commercial_credit_notes": credit_notes,
        "suppliers": suppliers,
        "summary": summary,
        "recent_limit": None if period_selected else RECENT_LIMIT,
        "date_range": {"start_date": start_day, "end_date": end_day} if period_selected else None,
        "accounting_basis": "ACTIVE_SEASON_SOURCE_DOCUMENTS_READ_ONLY",
    }


@router.get("/reconciliation-preview")
async def accounting_reconciliation_preview(limit: int = 100, _: dict = Depends(require_admin)):
    """Read-only source-event preview; never posts or mutates data."""
    if isinstance(limit, bool) or limit < 1 or limit > 200:
        raise HTTPException(status_code=422, detail="limit doit être compris entre 1 et 200.")
    season = await active_season()
    season_code = season_prefix(season)
    load_ids = await db.loads.distinct("id", {"season_id": season})
    invoices = await db.invoices.find({"load_id":{"$in":load_ids}},{"_id":0}).sort([("day",-1),("id",1)]).to_list(limit+1)
    purchases = await db.commercial_olive_purchases.find({"season_code":season_code},{"_id":0}).sort([("purchase_date",-1),("id",1)]).to_list(limit+1)
    gs_invoices = await db.commercial_sales_invoices.find({"season_code":season_code},{"_id":0}).sort([("sale_date",-1),("id",1)]).to_list(limit+1)
    gs_payments = await db.commercial_sale_payments.find({"season_code":season_code},{"_id":0}).sort([("payment_date",1),("id",1)]).to_list(limit+1)
    gs_reversals = await db.commercial_payment_reversals.find({"season_code":season_code},{"_id":0}).sort([("reversal_date",1),("id",1)]).to_list(limit+1)
    treasury_accounts = await db.accounting_treasury_accounts.find({}, {"_id":0,"id":1,"account_type":1,"currency":1,"active":1}).to_list(500)
    has_more={"traditional_invoices":len(invoices)>limit,"gs_purchases":len(purchases)>limit,
      "gs_sales_invoices":len(gs_invoices)>limit,"gs_sale_payments":len(gs_payments)>limit,"gs_sale_reversals":len(gs_reversals)>limit}
    invoices,purchases,gs_invoices,gs_payments,gs_reversals=[x[:limit] for x in (invoices,purchases,gs_invoices,gs_payments,gs_reversals)]
    purchase_ids=[str(x["id"]) for x in purchases if x.get("id")]
    supplier_payments=[]; lots=[]; movements=[]
    if purchase_ids:
        supplier_payments=await db.commercial_supplier_olive_purchase_payments.find({"purchase_id":{"$in":purchase_ids}},{"_id":0}).sort([("payment_date",1),("id",1)]).to_list(limit+1)
        lot_ids=list(dict.fromkeys(str(v) for p in purchases for v in (p.get("lot_ids") if isinstance(p.get("lot_ids"),list) else [])))
        movement_ids=list(dict.fromkeys(str(v) for p in purchases for v in (p.get("receipt_movement_ids") if isinstance(p.get("receipt_movement_ids"),list) else [])))
        if lot_ids: lots=await db.commercial_lots.find({"id":{"$in":lot_ids}},{"_id":0}).to_list(limit+1)
        if movement_ids: movements=await db.commercial_stock_movements.find({"id":{"$in":movement_ids}},{"_id":0}).to_list(limit+1)
    has_more["gs_supplier_payments"]=len(supplier_payments)>limit
    has_more["gs_purchase_lots"]=len(lots)>limit
    has_more["gs_purchase_movements"]=len(movements)>limit
    supplier_payments,lots,movements=[x[:limit] for x in (supplier_payments,lots,movements)]
    preview=build_reconciliation_preview(traditional_invoices=invoices,gs_purchases=purchases,supplier_payments=supplier_payments,
      lots=lots,stock_movements=movements,gs_sales_invoices=gs_invoices,gs_sale_payments=gs_payments,gs_sale_reversals=gs_reversals,
      treasury_accounts=treasury_accounts,
      check_gs_sale_payment_snapshots=not has_more["gs_sale_payments"] and not has_more["gs_sale_reversals"])
    return {**preview,"active_season":season,"season_code":season_code,"limit_per_source":limit,"has_more":has_more}


class TreasuryAccountInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=80)
    account_type: Literal["CASH", "BANK"]
    bank_name: str | None = Field(default=None, max_length=100)
    account_suffix: str | None = Field(default=None, pattern=r"^\d{4}$")
    location: str | None = Field(default=None, max_length=120)
    custodian_user_id: str | None = Field(default=None, max_length=80)
    notes: str = Field(default="", max_length=500)


class TreasuryAccountStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    active: bool


class TreasuryMovementCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_type: Literal["GS_SALE_PAYMENT", "GS_SUPPLIER_PAYMENT"]
    source_id: str = Field(min_length=1, max_length=100)
    confirm: Literal[True]


def _treasury_name_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _treasury_actor(user: dict) -> str:
    actor = user.get("id") or user.get("username") or user.get("_id")
    if not actor:
        raise HTTPException(status_code=403, detail="Identité administrateur manquante.")
    return str(actor)


@router.get("/treasury/accounts")
async def list_treasury_accounts(_: dict = Depends(require_admin)):
    """List treasury account metadata; balances remain unconfigured and are never inferred here."""
    rows = await db.accounting_treasury_accounts.find({}, {"_id": 0}).sort(
        [("active", -1), ("account_type", 1), ("name", 1)]
    ).to_list(500)
    return {"accounts": _safe(rows), "currency": "TND", "opening_balances_configured": False,
            "ledger_enabled": True, "movement_recording_enabled": True, "read_only_balances": True}


@router.post("/treasury/accounts")
async def create_treasury_account(payload: TreasuryAccountInput, user: dict = Depends(require_admin)):
    """Create a named cash/bank account shell; deliberately does not create a balance."""
    if payload.account_type == "BANK" and not (payload.bank_name or "").strip():
        raise HTTPException(status_code=422, detail="Le nom de la banque est obligatoire.")
    if payload.account_type == "CASH" and (payload.bank_name or payload.account_suffix):
        raise HTTPException(status_code=422, detail="Un tiroir-caisse ne peut pas contenir de coordonnées bancaires.")
    if len(payload.name.strip()) < 2:
        raise HTTPException(status_code=422, detail="Le nom du compte doit contenir au moins deux caractères.")
    actor_id = _treasury_actor(user)
    now, account_id = datetime.now(timezone.utc), str(uuid4())
    name_key = _treasury_name_key(payload.name)
    record = {
        "id": account_id, "name": re.sub(r"\s+", " ", payload.name.strip()),
        "name_key": name_key, "account_type": payload.account_type, "currency": "TND",
        "bank_name": payload.bank_name.strip() if payload.bank_name else None,
        "account_suffix": payload.account_suffix,
        "location": payload.location.strip() if payload.location else None,
        "custodian_user_id": payload.custodian_user_id.strip() if payload.custodian_user_id else None,
        "notes": payload.notes.strip(), "active": True, "version": 1,
        "opening_balance_status": "NOT_CONFIGURED",
        "created_by": actor_id, "created_at": now, "updated_at": now,
    }
    async def operation(session):
        duplicate = await db.accounting_treasury_accounts.find_one(
            {"account_type": payload.account_type, "name_key": name_key}, {"_id": 0, "id": 1}, session=session
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Un compte de même type et de même nom existe déjà.")
        await db.accounting_treasury_accounts.insert_one(record, session=session)
        await db.accounting_treasury_account_events.insert_one({
            "id": str(uuid4()), "account_id": account_id, "action": "ACCOUNT_CREATED",
            "actor_user_id": actor_id, "created_at": now,
            "details": {"account_type": payload.account_type, "name": record["name"], "currency": "TND"},
        }, session=session)
        return record
    try:
        return _safe(await run_transaction(operation))
    except Exception as exc:
        from pymongo.errors import DuplicateKeyError
        if isinstance(exc, DuplicateKeyError):
            raise HTTPException(status_code=409, detail="Un compte de même type et de même nom existe déjà.") from exc
        raise


@router.patch("/treasury/accounts/{account_id}/status")
async def update_treasury_account_status(account_id: str, payload: TreasuryAccountStatusInput,
                                         user: dict = Depends(require_admin)):
    """Deactivate/reactivate an account shell; never delete it or alter a balance."""
    actor_id, now = _treasury_actor(user), datetime.now(timezone.utc)
    async def operation(session):
        account = await db.accounting_treasury_accounts.find_one({"id": account_id}, {"_id": 0}, session=session)
        if not account:
            raise HTTPException(status_code=404, detail="Compte de trésorerie introuvable.")
        if account.get("version", 1) != payload.expected_version:
            raise HTTPException(status_code=409, detail="Le compte a été modifié. Actualisez la liste.")
        if account.get("active") == payload.active:
            return account
        update = await db.accounting_treasury_accounts.update_one(
            {"id": account_id, "version": payload.expected_version},
            {"$set": {"active": payload.active, "updated_at": now, "updated_by": actor_id},
             "$inc": {"version": 1}}, session=session,
        )
        if update.matched_count != 1:
            raise HTTPException(status_code=409, detail="Le compte a été modifié simultanément.")
        await db.accounting_treasury_account_events.insert_one({
            "id": str(uuid4()), "account_id": account_id,
            "action": "ACCOUNT_REACTIVATED" if payload.active else "ACCOUNT_DEACTIVATED",
            "actor_user_id": actor_id, "created_at": now,
            "details": {"previous_active": account.get("active"), "new_active": payload.active,
                        "previous_version": payload.expected_version, "new_version": payload.expected_version + 1},
        }, session=session)
        account["active"], account["version"], account["updated_at"] = payload.active, payload.expected_version + 1, now
        return account
    return _safe(await run_transaction(operation))


@router.post("/treasury/movements", status_code=201)
async def create_treasury_movement(payload: TreasuryMovementCreateInput, user: dict = Depends(require_admin)):
    """Explicitly record one operational movement from an existing immutable GS payment."""
    from pymongo.errors import DuplicateKeyError

    season = await active_season()
    season_code = season_prefix(season)
    actor_id = _treasury_actor(user)
    now = datetime.now(timezone.utc)

    async def operation(session):
        return await record_source_payment_movement(
            db, source_type=payload.source_type, source_id=payload.source_id,
            season_code=season_code, actor_user_id=actor_id,
            recorded_at=now, session=session,
        )

    try:
        return _safe(await run_transaction(operation))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DuplicateKeyError as exc:
        existing = await db.accounting_treasury_movements.find_one(
            {"season_code": season_code, "source_type": payload.source_type, "source_id": payload.source_id}, {"_id": 0}
        )
        if existing:
            return _safe(existing)
        raise HTTPException(status_code=409, detail="Une opération de trésorerie concurrente doit être vérifiée.") from exc


@router.get("/treasury/movements")
async def list_treasury_movements(
    account_id: str | None = None,
    direction: Literal["IN", "OUT"] | None = None,
    settlement_status: Literal[
        "CASH_RECORDED", "PENDING_BANK_CONFIRMATION", "PENDING_CHEQUE_CLEARANCE"
    ] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _: dict = Depends(require_admin),
):
    """Read-only, active-season movement register; no running or closing balances."""
    if isinstance(limit, bool) or limit < 1 or limit > 200:
        raise HTTPException(status_code=422, detail="limit doit être compris entre 1 et 200.")
    if isinstance(offset, bool) or offset < 0 or offset > 50000:
        raise HTTPException(status_code=422, detail="offset doit être compris entre 0 et 50000.")
    season = await active_season()
    season_code = season_prefix(season)
    try:
        match = build_movement_register_filter(
            season_code=season_code, account_id=account_id, direction=direction,
            settlement_status=settlement_status, start_date=start_date, end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    total_count = await db.accounting_treasury_movements.count_documents(match)
    rows = await db.accounting_treasury_movements.find(match, {"_id": 0}).sort(
        [("movement_date", -1), ("id", -1)]
    ).skip(offset).limit(limit).to_list(length=limit)
    return {
        "rows": _safe(rows),
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "active_season": season,
        "season_code": season_code,
        "read_only": True,
        "balances_calculated": False,
        "currency": "TND",
    }


@router.get("/treasury/movement-preview")
async def treasury_movement_preview(limit: int = 100, _: dict = Depends(require_admin)):
    """Read-only proposals from mapped GS payment documents; never posts money movements."""
    if isinstance(limit, bool) or limit < 1 or limit > 200:
        raise HTTPException(status_code=422, detail="limit doit être compris entre 1 et 200.")
    season = await active_season()
    season_code = season_prefix(season)
    sale_payments, supplier_payments, reversals, accounts = await asyncio.gather(
        db.commercial_sale_payments.find({"season_code": season_code}, {"_id": 0})
        .sort([("payment_date", -1), ("id", 1)]).to_list(limit + 1),
        db.commercial_supplier_olive_purchase_payments.find({"season_code": season_code}, {"_id": 0})
        .sort([("payment_date", -1), ("id", 1)]).to_list(limit + 1),
        db.commercial_payment_reversals.find({"season_code": season_code}, {"_id": 0})
        .sort([("reversal_date", -1), ("id", 1)]).to_list(limit + 1),
        db.accounting_treasury_accounts.find(
            {}, {"_id": 0, "id": 1, "name": 1, "account_type": 1, "currency": 1, "active": 1}
        ).to_list(500),
    )
    has_more = {
        "gs_sale_payments": len(sale_payments) > limit,
        "gs_supplier_payments": len(supplier_payments) > limit,
        "gs_sale_reversals": len(reversals) > limit,
    }
    sale_payment_rows, supplier_payment_rows = sale_payments[:limit], supplier_payments[:limit]
    sale_invoice_ids = list(dict.fromkeys(str(row.get("invoice_id")) for row in sale_payment_rows if row.get("invoice_id")))
    supplier_purchase_ids = list(dict.fromkeys(str(row.get("purchase_id")) for row in supplier_payment_rows if row.get("purchase_id")))
    sale_invoices, supplier_purchases = await asyncio.gather(
        db.commercial_sales_invoices.find(
            {"id": {"$in": sale_invoice_ids}, "season_code": season_code},
            {"_id": 0, "id": 1, "sale_id": 1, "buyer_id": 1},
        ).to_list(limit),
        db.commercial_olive_purchases.find(
            {"id": {"$in": supplier_purchase_ids}, "season_code": season_code},
            {"_id": 0, "id": 1, "status": 1, "supplier_id": 1},
        ).to_list(limit),
    )
    preview = build_treasury_movement_preview(
        sale_payments=sale_payment_rows,
        supplier_payments=supplier_payment_rows,
        sale_reversals=reversals[:limit],
        sale_invoices=sale_invoices,
        supplier_purchases=supplier_purchases,
        treasury_accounts=accounts,
    )
    source_ids = [row["source_id"] for row in preview["candidates"]]
    recorded_rows = await db.accounting_treasury_movements.find(
        {"season_code": season_code, "source_id": {"$in": source_ids}},
        {"_id": 0, "source_type": 1, "source_id": 1, "id": 1, "settlement_status": 1, "recorded_at": 1},
    ).to_list(limit * 2)
    recorded = {(row["source_type"], row["source_id"]): row for row in recorded_rows}
    for candidate in preview["candidates"]:
        movement = recorded.get((candidate["source_type"], candidate["source_id"]))
        candidate["recorded_movement_id"] = movement.get("id") if movement else None
        candidate["settlement_status"] = movement.get("settlement_status") if movement else None
        candidate["recorded_at"] = movement.get("recorded_at").isoformat() if movement and movement.get("recorded_at") else None
    return {
        **preview, "active_season": season, "season_code": season_code,
        "limit_per_source": limit, "has_more": has_more,
    }


class PassiveIncomeInput(BaseModel):
    income_type: Literal["RENT", "EQUIPMENT_RENTAL", "INTEREST", "INVESTMENT", "OTHER"]
    description: str = Field(min_length=2, max_length=180)
    income_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    amount_tnd: str = Field(pattern=r"^\d{1,12}(?:\.\d{1,3})?$")
    payment_method: Literal["CASH", "BANK_TRANSFER", "CHEQUE", "OTHER"] = "CASH"
    notes: str = Field(default="", max_length=500)


@router.get("/passive-incomes")
async def list_passive_incomes(
    start_date: str | None = None,
    end_date: str | None = None,
    _: dict = Depends(require_admin),
):
    season = await active_season()
    period_selected = bool(start_date or end_date)
    rows = await db.accounting_passive_incomes.find(
        {"season": season}, {"_id": 0}
    ).sort([("income_date", -1), ("created_at", -1)]).to_list(None if period_selected else 1000)
    if period_selected:
        try:
            start_day = date.fromisoformat(start_date).isoformat() if start_date else None
            end_day = date.fromisoformat(end_date).isoformat() if end_date else None
        except ValueError:
            raise HTTPException(status_code=422, detail="Date invalide. Format attendu : AAAA-MM-JJ.")
        if start_day and end_day and start_day > end_day:
            raise HTTPException(status_code=422, detail="La date de début doit précéder ou égaler la date de fin.")
        rows = _filter_accounting_period(rows, start_day, end_day, ("income_date", "created_at"))
    return _safe(rows)


@router.post("/passive-incomes")
async def create_passive_income(payload: PassiveIncomeInput, user: dict = Depends(require_admin)):
    season = await active_season()
    try:
        datetime.strptime(payload.income_date, "%Y-%m-%d")
        amount = Decimal(payload.amount_tnd)
    except (ValueError, InvalidOperation):
        raise HTTPException(status_code=422, detail="Date ou montant invalide.")
    if not amount.is_finite() or amount <= 0:
        raise HTTPException(status_code=422, detail="Le montant doit être supérieur à zéro.")
    record = {
        "id": str(uuid4()),
        "season": season,
        "income_type": payload.income_type,
        "description": payload.description.strip(),
        "income_date": payload.income_date,
        "amount_tnd": format(amount.quantize(Decimal("0.001")), "f"),
        "payment_method": payload.payment_method,
        "notes": payload.notes.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("id") or user.get("username") or "admin",
    }
    await db.accounting_passive_incomes.insert_one(record)
    record.pop("_id", None)
    return record


@router.delete("/passive-incomes/{income_id}")
async def delete_passive_income(income_id: str, _: dict = Depends(require_admin)):
    season = await active_season()
    result = await db.accounting_passive_incomes.delete_one({"id": income_id, "season": season})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Revenu passif introuvable pour la saison active.")
    return {"ok": True}

class ExpenseInput(BaseModel):
    expense_type: Literal["ELECTRICITY", "WAGES", "MAINTENANCE", "FUEL", "TRANSPORT", "SUPPLIES", "RENT", "INSURANCE", "TAXES", "OTHER"]
    description: str = Field(min_length=2, max_length=180)
    expense_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    amount_tnd: str = Field(pattern=r"^\d{1,12}(?:\.\d{1,3})?$")
    payment_method: Literal["CASH", "BANK_TRANSFER", "CHEQUE", "OTHER"] = "CASH"
    beneficiary: str = Field(default="", max_length=160)
    notes: str = Field(default="", max_length=500)


async def _create_accounting_outflow(collection: str, kind_field: str, kind: str, date_field: str, payload: Any, user: dict):
    season = await active_season()
    try:
        datetime.strptime(getattr(payload, date_field), "%Y-%m-%d")
        amount = Decimal(payload.amount_tnd)
    except (ValueError, InvalidOperation):
        raise HTTPException(status_code=422, detail="Date ou montant invalide.")
    if not amount.is_finite() or amount <= 0:
        raise HTTPException(status_code=422, detail="Le montant doit être supérieur à zéro.")
    record = {
        "id": str(uuid4()),
        "season": season,
        kind_field: kind,
        "description": payload.description.strip(),
        date_field: getattr(payload, date_field),
        "amount_tnd": format(amount.quantize(Decimal("0.001")), "f"),
        "payment_method": payload.payment_method,
        "notes": payload.notes.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.get("id") or user.get("username") or "admin",
    }
    if kind_field == "expense_type":
        record["beneficiary"] = payload.beneficiary.strip()
    else:
        record["supplier"] = payload.supplier.strip()
    await db[collection].insert_one(record)
    record.pop("_id", None)
    return record


async def _list_accounting_outflows(
    collection: str, date_field: str,
    start_date: str | None = None, end_date: str | None = None,
):
    season = await active_season()
    period_selected = bool(start_date or end_date)
    rows = await db[collection].find({"season": season}, {"_id": 0}).sort(
        [(date_field, -1), ("created_at", -1)]
    ).to_list(None if period_selected else 1000)
    if period_selected:
        try:
            start_day = date.fromisoformat(start_date).isoformat() if start_date else None
            end_day = date.fromisoformat(end_date).isoformat() if end_date else None
        except ValueError:
            raise HTTPException(status_code=422, detail="Date invalide. Format attendu : AAAA-MM-JJ.")
        if start_day and end_day and start_day > end_day:
            raise HTTPException(status_code=422, detail="La date de début doit précéder ou égaler la date de fin.")
        rows = _filter_accounting_period(rows, start_day, end_day, (date_field, "created_at"))
    return _safe(rows)


async def _delete_accounting_outflow(collection: str, record_id: str, kind_label: str):
    season = await active_season()
    result = await db[collection].delete_one({"id": record_id, "season": season})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"{kind_label} introuvable pour la saison active.")
    return {"ok": True}


@router.get("/expenses")
async def list_accounting_expenses(
    start_date: str | None = None,
    end_date: str | None = None,
    _: dict = Depends(require_admin),
):
    return await _list_accounting_outflows("accounting_expenses", "expense_date", start_date, end_date)


@router.post("/expenses")
async def create_accounting_expense(payload: ExpenseInput, user: dict = Depends(require_admin)):
    return await _create_accounting_outflow("accounting_expenses", "expense_type", payload.expense_type, "expense_date", payload, user)


@router.delete("/expenses/{record_id}")
async def delete_accounting_expense(record_id: str, _: dict = Depends(require_admin)):
    return await _delete_accounting_outflow("accounting_expenses", record_id, "Dépense")


def _accounting_day(value: Any) -> str | None:
    """Normalize timestamps to the mill's business date."""
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo("Africa/Tunis")).date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10]).isoformat()
        except ValueError:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(ZoneInfo("Africa/Tunis")).date().isoformat()
            except ValueError:
                return None
    return None


def _accounting_decimal(value: Any) -> Decimal:
    try:
        amount = value.to_decimal() if isinstance(value, Decimal128) else Decimal(str(value if value is not None else "0"))
        return amount if amount.is_finite() else Decimal("0.000")
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.000")


def _daily_event(events: list[dict], *, day: str | None, category: str,
                 label: str, reference: str, amount: Any, kind: str,
                 detail: str = "") -> None:
    value = _accounting_decimal(amount).quantize(Decimal("0.001"))
    if not day or value == 0:
        return
    events.append({
        "date": day, "category": category, "label": label,
        "reference": reference or "—", "amount": format(value, "f"),
        "kind": kind, "detail": detail,
    })


@router.get("/daily-situation")
async def accounting_daily_situation(
    report_date: str | None = None,
    comparison_start_date: str | None = None,
    comparison_end_date: str | None = None,
    report_start_date: str | None = None,
    report_end_date: str | None = None,
    _: dict = Depends(require_admin),
):
    """Period accrual/cash report from source records; does not mutate accounting data."""
    try:
        period_start = date.fromisoformat(report_start_date or comparison_start_date or report_date or date.today().isoformat())
        period_end = date.fromisoformat(report_end_date or comparison_end_date or report_date or date.today().isoformat())
        selected_day = period_end.isoformat()
    except ValueError:
        raise HTTPException(422, "invalid_report_period")
    if period_start > period_end:
        raise HTTPException(422, "period_start_after_end")
    if (period_end - period_start).days > 3650:
        raise HTTPException(422, "period_too_long")

    season = await active_season()
    season_code = season_prefix(season)
    load_ids = await db.loads.distinct("id", {"season_id": season})
    invoices, supplier_purchases, supplier_payments, customer_purchase_docs, sale_invoices, sale_payments, sale_reversals, customer_purchase_payments, passive_incomes, expenses = await asyncio.gather(
        db.invoices.find({"load_id": {"$in": load_ids}}, {"_id": 0}).to_list(None),
        db.commercial_olive_purchases.find({"season_code": season_code, "status": "APPROVED"}, {"_id": 0}).to_list(None),
        db.commercial_supplier_olive_purchase_payments.find({"season_code": season_code}, {"_id": 0}).to_list(None),
        db.commercial_oil_purchase_documents.find({"season_code": season_code}, {"_id": 0}).to_list(None),
        db.commercial_sales_invoices.find({"season_code": season_code}, {"_id": 0}).to_list(None),
        db.commercial_sale_payments.find({"season_code": season_code}, {"_id": 0}).to_list(None),
        db.commercial_payment_reversals.find({"season_code": season_code}, {"_id": 0}).to_list(None),
        db.commercial_oil_purchase_payments.find({"season_code": season_code}, {"_id": 0}).to_list(None),
        db.accounting_passive_incomes.find({"season": season}, {"_id": 0}).to_list(None),
        db.accounting_expenses.find({"season": season}, {"_id": 0}).to_list(None),
    )

    events: list[dict] = []
    unallocated_receipts = Decimal("0.000")
    current_receivables = Decimal("0.000")
    current_payables = Decimal("0.000")

    for invoice in invoices:
        invoice_day = _accounting_day(invoice.get("day") or invoice.get("created_at"))
        _daily_event(events, day=invoice_day, category="Prestation", label="Facture de trituration",
                     reference=invoice.get("number", ""), amount=invoice.get("total"), kind="revenue",
                     detail=invoice.get("client_name", ""))
        current_receivables += max(Decimal("0"), _accounting_decimal(invoice.get("balance")))
        known_paid = Decimal("0.000")
        for payment in invoice.get("payments") or []:
            amount = _accounting_decimal(payment.get("amount"))
            payment_day = _accounting_day(payment.get("at") or payment.get("date"))
            if amount > 0 and payment_day:
                _daily_event(events, day=payment_day, category="Prestation", label="Encaissement facture",
                             reference=invoice.get("number", ""), amount=amount, kind="receipt",
                             detail=invoice.get("client_name", ""))
                known_paid += amount
        for history in invoice.get("history") or []:
            if history.get("action") != "updated":
                continue
            before = _accounting_decimal((history.get("before") or {}).get("paid_amount"))
            after = _accounting_decimal((history.get("after") or {}).get("paid_amount"))
            delta = after - before
            history_day = _accounting_day(history.get("at"))
            if delta > 0 and history_day:
                _daily_event(events, day=history_day, category="Prestation", label="Encaissement facture",
                             reference=invoice.get("number", ""), amount=delta, kind="receipt",
                             detail=invoice.get("client_name", ""))
                known_paid += delta
        unallocated_receipts += max(Decimal("0"), _accounting_decimal(invoice.get("paid_amount")) - known_paid)

    for purchase in supplier_purchases:
        purchase_day = _accounting_day(purchase.get("purchase_date") or purchase.get("created_at"))
        amount = _accounting_decimal(purchase.get("total_amount_dt"))
        _daily_event(events, day=purchase_day, category="Achat fournisseur", label="Achat d’olives",
                     reference=purchase.get("document_number", ""), amount=amount, kind="expense",
                     detail=purchase.get("supplier_name", ""))
        current_payables += max(
            Decimal("0"),
            _accounting_decimal(purchase.get("outstanding_amount_dt"))
            if purchase.get("outstanding_amount_dt") is not None
            else amount - _accounting_decimal(purchase.get("paid_amount_dt")),
        )

    for payment in supplier_payments:
        payment_day = _accounting_day(payment.get("payment_date") or payment.get("created_at"))
        _daily_event(
            events, day=payment_day, category="Achat fournisseur",
            label="Règlement fournisseur",
            reference=payment.get("document_number") or payment.get("purchase_number", ""),
            amount=payment.get("amount_tnd"), kind="disbursement",
            detail=payment.get("supplier_name", ""),
        )

    for purchase in customer_purchase_docs:
        purchase_day = _accounting_day(purchase.get("purchase_date") or purchase.get("created_at"))
        amount = _accounting_decimal(purchase.get("agreed_amount_tnd"))
        product = "olives" if purchase.get("product_kind") == "OLIVE" else "huile"
        _daily_event(events, day=purchase_day, category="Achat client", label=f"Achat d’{product}",
                     reference=purchase.get("document_number", ""), amount=amount, kind="expense",
                     detail=purchase.get("customer_name", ""))
        current_payables += max(Decimal("0"), _accounting_decimal(purchase.get("outstanding_amount_tnd")))

    for invoice in sale_invoices:
        invoice_day = _accounting_day(invoice.get("sale_date") or invoice.get("created_at"))
        _daily_event(events, day=invoice_day, category="Vente GS", label="Facture de vente d’huile",
                     reference=invoice.get("document_number", ""),
                     amount=invoice.get("net_amount_dt", invoice.get("total_amount_dt")),
                     kind="revenue", detail=invoice.get("buyer_name", ""))
        current_receivables += max(Decimal("0"), _accounting_decimal(invoice.get("outstanding_amount_dt")))

    for reversal in sale_reversals:
        reversal_day = _accounting_day(reversal.get("reversal_date") or reversal.get("created_at"))
        _daily_event(events, day=reversal_day, category="Vente GS", label="Annulation d’encaissement",
                     reference=reversal.get("document_number", ""),
                     amount=-_accounting_decimal(reversal.get("amount_dt")),
                     kind="receipt_adjustment", detail=reversal.get("reason", ""))

    for payment in sale_payments:
        payment_day = _accounting_day(payment.get("payment_date") or payment.get("created_at"))
        _daily_event(events, day=payment_day, category="Vente GS", label="Encaissement facture GS",
                     reference=payment.get("document_number", ""), amount=payment.get("amount_dt"),
                     kind="receipt", detail=payment.get("buyer_name", ""))

    for payment in customer_purchase_payments:
        payment_day = _accounting_day(payment.get("payment_date") or payment.get("created_at"))
        _daily_event(events, day=payment_day, category="Achat client", label="Paiement d’achat",
                     reference=payment.get("document_number", ""), amount=payment.get("amount_tnd"),
                     kind="disbursement", detail=payment.get("customer_name", ""))

    for income in passive_incomes:
        income_day = _accounting_day(income.get("income_date"))
        label = income.get("description", "Revenu complémentaire")
        _daily_event(events, day=income_day, category="Revenu passif", label=label,
                     reference=income.get("id", ""), amount=income.get("amount_tnd"),
                     kind="revenue", detail=income.get("income_type", ""))
        _daily_event(events, day=income_day, category="Revenu passif", label=label,
                     reference=income.get("id", ""), amount=income.get("amount_tnd"),
                     kind="receipt", detail=income.get("payment_method", ""))

    for expense_doc in expenses:
        expense_day = _accounting_day(expense_doc.get("expense_date"))
        label = expense_doc.get("description", "Dépense")
        _daily_event(events, day=expense_day, category="Dépense", label=label,
                     reference=expense_doc.get("id", ""), amount=expense_doc.get("amount_tnd"),
                     kind="expense", detail=expense_doc.get("beneficiary", ""))
        _daily_event(events, day=expense_day, category="Dépense", label=label,
                     reference=expense_doc.get("id", ""), amount=expense_doc.get("amount_tnd"),
                     kind="disbursement", detail=expense_doc.get("payment_method", ""))

    events.sort(key=lambda item: (item["date"], item["category"], item["reference"]))
    day_events = [item for item in events if period_start.isoformat() <= item["date"] <= period_end.isoformat()]

    def total_for(items: list[dict], kind: str) -> Decimal:
        return sum((_accounting_decimal(item["amount"]) for item in items if item["kind"] == kind), Decimal("0.000"))

    revenue = total_for(day_events, "revenue")
    expense = total_for(day_events, "expense")
    receipts = total_for(day_events, "receipt") + total_for(day_events, "receipt_adjustment")
    disbursements = total_for(day_events, "disbursement")
    comparison_start = period_start
    comparison_end = period_end

    comparison = []
    current_day = comparison_start
    while current_day <= comparison_end:
        day = current_day.isoformat()
        rows = [item for item in events if item["date"] == day]
        day_revenue, day_expense = total_for(rows, "revenue"), total_for(rows, "expense")
        comparison.append({
            "date": day, "revenue": format(day_revenue, "f"),
            "expense": format(day_expense, "f"), "net": format(day_revenue - day_expense, "f"),
        })
        current_day += timedelta(days=1)

    return {
        "date": selected_day, "start_date": period_start.isoformat(), "end_date": period_end.isoformat(), "season": season,
        "summary": {
            "total_revenue": format(revenue, "f"),
            "total_expenses": format(expense, "f"),
            "net_result": format(revenue - expense, "f"),
            "encaissements": format(receipts, "f"),
            "decaissements": format(disbursements, "f"),
            "current_receivables": format(current_receivables, "f"),
            "current_payables": format(current_payables, "f"),
            "unallocated_legacy_receipts": format(unallocated_receipts, "f"),
        },
        "events": day_events, "comparison": comparison,
        "accounting_basis": "SOURCE_DOCUMENTS_ACCRUAL_AND_CASH",
        "supplier_payments_available": True,
    }
