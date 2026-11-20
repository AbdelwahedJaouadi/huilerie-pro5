import hashlib
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from bson.decimal128 import Decimal128
from pymongo.errors import DuplicateKeyError
from fastapi import APIRouter, Depends, HTTPException, Query

from lib.auth import current_user, require_admin
from lib.dates import today_iso
from lib.db import db, run_transaction
from lib.season import active_season, next_load_code, season_filter, season_of
from lib.money import money_db, money_float, to_decimal
from lib.weighing import derive_net_weight_kg, weight_measurement_audit_snapshot
from lib.sms import send_load_sms
from routers.invoices import create_invoice as create_load_invoice, _create_invoice_in_session
from models.schemas import CancelBody, DailyPoint, LabAnalysis, Load, LoadCreate, OilUpdate, Stats, StatusUpdate

router = APIRouter(tags=["loads"])
log = logging.getLogger(__name__)


async def _audit_load_event(load: dict, user: dict, action: str, details: dict | None = None, session=None):
    event = {
        "id": str(uuid.uuid4()), "entity_type": "traditional_load",
        "entity_id": str(load.get("id") or ""), "action": action,
        "actor_user_id": user.get("id"), "created_at": datetime.now(timezone.utc),
        "details": {"code": load.get("code"), "client_name": load.get("client_name"),
                    **(details or {})},
    }
    options = {"session": session} if session is not None else {}
    await db.commercial_audit_events.insert_one(event, **options)


def _tz() -> ZoneInfo:
    return ZoneInfo(os.environ.get("APP_TZ", "UTC"))


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _price() -> float:
    s = await db.settings.find_one({"key": "app"})
    return money_float(s["price_per_kg"]) if s else 0.0


def _weight_measurement_value(measurement: dict, key: str) -> Optional[float]:
    value = measurement.get(key)
    if value is None:
        return None
    if isinstance(value, Decimal128):
        value = value.to_decimal()
    return float(value)


def to_load(doc: dict, user: dict, lab: Optional[dict] = None) -> Load:
    is_admin = user["role"] == "admin"
    raw_oil = doc.get("oil_kg")
    oil = money_float(to_decimal(raw_oil)) if raw_oil is not None else None
    olive_kg = money_float(to_decimal(doc["olive_kg"]))
    available_olive_kg = money_float(
        to_decimal(doc.get("customer_available_olive_kg", doc["olive_kg"]) or 0)
    )
    weight_measurement = doc.get("weight_measurement") or {}
    return Load(
        id=doc["id"], code=doc["code"], client_name=doc["client_name"], phone=doc["phone"],
        olive_kg=olive_kg, available_olive_kg=available_olive_kg,
        gross_weight_kg=_weight_measurement_value(weight_measurement, "gross_kg"),
        tare_weight_kg=_weight_measurement_value(weight_measurement, "tare_kg"),
        weight_source=weight_measurement.get("source"),
        weighed_at=_aware(weight_measurement["measured_at"]) if weight_measurement.get("measured_at") else None,
        weighed_by=weight_measurement.get("operator_username"),
        ownership_transferred=bool(doc.get("ownership_transferred", False)), ownership_transferred_at=_aware(doc["ownership_transferred_at"]) if doc.get("ownership_transferred_at") else None, oil_kg=oil,
        yield_pct=round(oil / olive_kg * 100, 2) if oil is not None and olive_kg else None,
        status="cancelled" if doc.get("cancelled") else (
            "delivered" if doc.get("delivered") else (
                "done" if oil is not None else ("pressing" if doc.get("pressing") else "pending"))),
        day=doc["day"], season=doc.get("season_id") or season_of(doc["day"]),
        created_at=_aware(doc["created_at"]), created_by=doc["created_by"],
        created_by_name=doc.get("created_by_name"), bags=doc.get("bags"),
        variety=doc.get("variety"), notes=doc.get("notes"),
        oil_ready_at=_aware(doc["oil_ready_at"]) if doc.get("oil_ready_at") else None,
        delivered_at=_aware(doc["delivered_at"]) if doc.get("delivered_at") else None,
        delivered_by=doc.get("delivered_by"),
        reminder_sent_at=_aware(doc["reminder_sent_at"]) if doc.get("reminder_sent_at") else None,
        cancel_reason=doc.get("cancel_reason"), cancelled_by=doc.get("cancelled_by"),
        cancelled_at=_aware(doc["cancelled_at"]) if doc.get("cancelled_at") else None,
        price_per_kg=money_float(doc.get("price_per_kg")) if is_admin else None,
        amount=money_float(to_decimal(doc["olive_kg"]) * to_decimal(doc.get("price_per_kg", 0))) if is_admin else None,
        lab=LabAnalysis(**{**lab, "created_at": _aware(lab["created_at"])}) if lab else None,
    )


async def _labs_for(ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    async for lab in db.lab.find({"load_id": {"$in": ids}}, {"_id": 0}).sort("created_at", 1):
        out[lab["load_id"]] = lab  # latest wins
    return out


@router.post("/loads", response_model=Load)
async def create_load(body: LoadCreate, user: dict = Depends(current_user)):
    phone = re.sub(r"\s+", "", body.phone)
    client_name = body.client_name.strip()
    variety = (body.variety or "").strip() or None
    notes = (body.notes or "").strip() or None
    net_kg = derive_net_weight_kg(body.gross_weight_kg, body.tare_weight_kg) if body.gross_weight_kg is not None else Decimal(str(body.olive_kg))
    request_scope = str(user.get("id") or user["username"])
    request_key = body.idempotency_key
    canonical_payload = {
        "client_name": client_name, "phone": phone, "net_kg": format(net_kg, "f"),
        "gross_weight_kg": format(body.gross_weight_kg, "f") if body.gross_weight_kg is not None else None,
        "tare_weight_kg": format(body.tare_weight_kg, "f") if body.tare_weight_kg is not None else None,
        "bags": body.bags, "variety": variety, "notes": notes,
        "initial_status": body.initial_status,
    }
    fingerprint = hashlib.sha256(json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()

    async def replay_if_present():
        if not request_key:
            return None
        existing = await db.loads.find_one(
            {"idempotency_scope": request_scope, "idempotency_key": request_key},
            {"_id": 0},
        )
        if existing:
            if existing.get("idempotency_fingerprint") != fingerprint:
                raise HTTPException(409, "idempotency_key_payload_conflict")
            return existing
        return None

    replay = await replay_if_present()
    if replay:
        return to_load(replay, user)

    inactive_client = await db.clients.find_one({"phone": phone, "active": False}, {"_id": 0, "phone": 1})
    if inactive_client:
        raise HTTPException(409, "client_inactive")
    now_local = datetime.now(_tz())
    season = await active_season()
    # Allocate the sequential code only after the replay check.
    code = await next_load_code(season)
    now = datetime.now(timezone.utc)
    doc = {
        "id": str(uuid.uuid4()), "code": code, "season_id": season, "client_name": client_name,
        "phone": phone, "olive_kg": float(net_kg), "oil_kg": None,
        "day": now_local.strftime("%Y-%m-%d"), "created_at": now,
        "created_by": user["username"], "created_by_name": user.get("full_name") or user["username"],
        "price_per_kg": money_db(await _price()),
        "bags": body.bags, "variety": variety, "notes": notes,
        "pressing": body.initial_status == "pressing",
    }
    if request_key:
        doc.update(idempotency_scope=request_scope, idempotency_key=request_key, idempotency_fingerprint=fingerprint)
    if body.gross_weight_kg is not None and body.tare_weight_kg is not None:
        doc["weight_measurement"] = {
            "gross_kg": Decimal128(body.gross_weight_kg), "tare_kg": Decimal128(body.tare_weight_kg),
            "net_kg": Decimal128(str(net_kg)), "measured_at": now,
            "operator_user_id": user.get("id"), "operator_username": user["username"],
            "source": "manual", "correction_of": None,
        }

    async def operation(session):
        # Recheck inside the transaction to close the common retry race.
        if request_key:
            existing = await db.loads.find_one(
                {"idempotency_scope": request_scope, "idempotency_key": request_key},
                {"_id": 0}, session=session,
            )
            if existing:
                if existing.get("idempotency_fingerprint") != fingerprint:
                    raise HTTPException(409, "idempotency_key_payload_conflict")
                return existing
        client_doc = await db.clients.find_one({"phone": phone}, {"_id": 0, "active": 1}, session=session)
        if client_doc and client_doc.get("active") is False:
            raise HTTPException(409, "client_inactive")
        if client_doc:
            guard = await db.clients.update_one(
                {"phone": phone, "active": {"$ne": False}},
                {"$inc": {"intake_guard_version": 1}}, session=session,
            )
            if not guard.matched_count:
                raise HTTPException(409, "client_inactive")
        else:
            await db.clients.insert_one({
                "phone": phone, "client_name": client_name, "active": True,
                "intake_guard_version": 1, "created_at": now,
            }, session=session)
        await db.loads.insert_one(doc, session=session)
        await _audit_load_event(doc, user, "LOAD_CREATED", {
            "olive_kg": doc.get("olive_kg"), "variety": doc.get("variety"),
            "phone": doc.get("phone"), "initial_status": body.initial_status,
            "weight_measurement": weight_measurement_audit_snapshot(doc.get("weight_measurement")),
        }, session=session)
        return doc

    try:
        result = await run_transaction(operation)
    except DuplicateKeyError:
        # A concurrent request may have won the unique idempotency index.
        replay = await replay_if_present()
        if replay:
            return to_load(replay, user)
        raise
    if request_key and result.get("id") != doc["id"]:
        return to_load(result, user)
    result.pop("_id", None)
    await send_load_sms(result, "arrival")
    return to_load(result, user)


@router.get("/loads", response_model=list[Load])
async def list_loads(q: str = "", status: str = "", season: str = "", worker: str = "", user: dict = Depends(current_user)):
    flt: dict = await season_filter(season)
    # A fully transferred load is no longer an active customer load.
    flt["ownership_transferred"] = {"$ne": True}
    if worker:
        flt["created_by"] = worker
    if q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        flt["$or"] = [{"code": rx}, {"client_name": rx}, {"phone": rx}]
    if status == "pending":
        flt["oil_kg"] = None
        flt["cancelled"] = {"$ne": True}
        flt["pressing"] = {"$ne": True}
    elif status == "pressing":
        flt["oil_kg"] = None
        flt["cancelled"] = {"$ne": True}
        flt["pressing"] = True
    elif status == "done":
        flt["oil_kg"] = {"$ne": None}
        flt["cancelled"] = {"$ne": True}
        flt["delivered"] = {"$ne": True}
    elif status == "delivered":
        flt["delivered"] = True
        flt["cancelled"] = {"$ne": True}
    elif status == "cancelled":
        flt["cancelled"] = True
    docs = await db.loads.find(flt, {"_id": 0}).sort("created_at", -1).to_list(500)
    labs = await _labs_for([d["id"] for d in docs])
    return [to_load(d, user, labs.get(d["id"])) for d in docs]


@router.get("/loads/by-code/{code}", response_model=Load)
async def get_by_code(code: str, user: dict = Depends(current_user)):
    doc = await db.loads.find_one({"code": code.strip(), **(await season_filter())}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "code_not_found")
    labs = await _labs_for([doc["id"]])
    return to_load(doc, user, labs.get(doc["id"]))


async def _ensure_load_invoice(id: str, user: dict) -> None:
    """Create the automatic invoice, treating an existing invoice as a safe retry."""
    try:
        await create_load_invoice({"load_id": id, "paid_amount": 0}, user)
    except HTTPException as exc:
        # Only the invoice uniqueness conflict means another request already
        # created the invoice. Other 409 responses must remain visible.
        if exc.status_code != 409 or exc.detail != "load_already_invoiced":
            raise


async def _complete_load_and_invoice(id: str, oil_kg: float, user: dict):
    """Persist the oil weight and its invoice atomically; return (load, notify_customer)."""

    async def operation(session):
        before = await db.loads.find_one(
            {"id": id},
            {"_id": 0, "olive_kg": 1, "customer_available_olive_kg": 1, "ownership_transferred": 1, "oil_kg": 1, "cancelled": 1, "delivered": 1},
            session=session,
        )
        if not before:
            raise HTTPException(404, "not_found")
        if before.get("cancelled"):
            raise HTTPException(409, "load_cancelled")
        if before.get("delivered"):
            raise HTTPException(409, "load_already_delivered")
        if before.get("ownership_transferred") or float(before.get("customer_available_olive_kg", before.get("olive_kg", 0)) or 0) <= 0:
            raise HTTPException(409, "load_ownership_transferred_to_mill")

        if before.get("oil_kg") is not None:
            if float(before["oil_kg"]) != float(oil_kg):
                raise HTTPException(409, "oil_already_entered")
            # A same-value retry repairs an invoice missing after an older
            # non-transactional completion, but never sends a duplicate SMS.
            existing = await db.invoices.find_one({"load_id": id}, session=session)
            if not existing:
                await _create_invoice_in_session(
                    {"load_id": id, "paid_amount": 0}, user, session
                )
            doc = await db.loads.find_one({"id": id}, {"_id": 0}, session=session)
            return doc, False

        upd = {
            "oil_kg": oil_kg,
            "oil_by": user["username"],
            "oil_ready_at": datetime.now(timezone.utc),
        }
        doc = await db.loads.find_one_and_update(
            {
                "id": id,
                "oil_kg": None,
                "cancelled": {"$ne": True},
                "delivered": {"$ne": True},
            },
            {"$set": upd},
            projection={"_id": 0},
            return_document=True,
            session=session,
        )
        if not doc:
            raise HTTPException(409, "oil_already_entered")

        # Invoice insertion and source-load guard run in this same transaction.
        await _create_invoice_in_session(
            {"load_id": id, "paid_amount": 0}, user, session
        )
        await _audit_load_event(doc, user, "LOAD_OIL_RECORDED", {
            "oil_kg": oil_kg, "previous_oil_kg": before.get("oil_kg")
        }, session=session)
        return doc, True

    return await run_transaction(operation)


@router.patch("/loads/{id}/oil", response_model=Load)
async def set_oil(id: str, body: OilUpdate, user: dict = Depends(current_user)):
    doc, should_notify = await _complete_load_and_invoice(id, body.oil_kg, user)

    # Notification is deliberately outside the transaction: a provider outage
    # must not roll back the completed load or its accounting invoice.
    if should_notify:
        try:
            await send_load_sms(doc, "ready")
        except Exception:
            log.exception("Ready SMS failed for completed load %s", id)

    labs = await _labs_for([id])
    return to_load(doc, user, labs.get(id))


@router.patch("/loads/{id}/status", response_model=Load)
async def set_status(id: str, body: StatusUpdate, user: dict = Depends(current_user)):
    async def operation(session):
        cur = await db.loads.find_one({"id": id}, {"_id": 0}, session=session)
        if not cur:
            raise HTTPException(404, "not_found")
        if cur.get("cancelled"):
            raise HTTPException(409, "load_cancelled")
        if body.status in ("pending", "pressing") and (cur.get("ownership_transferred") or float(cur.get("customer_available_olive_kg", cur.get("olive_kg", 0)) or 0) <= 0):
            raise HTTPException(409, "load_ownership_transferred_to_mill")
        has_oil = cur.get("oil_kg") is not None
        st = body.status
        if st in ("pending", "pressing") and has_oil:
            raise HTTPException(409, "oil_already_entered")
        if st in ("done", "delivered") and not has_oil:
            raise HTTPException(409, "oil_not_ready")
        previous_status = ("delivered" if cur.get("delivered") else ("done" if has_oil else ("pressing" if cur.get("pressing") else "pending")))
        upd = {"pressing": st == "pressing"}
        if st == "delivered":
            if not cur.get("delivered"):
                upd.update(delivered=True, delivered_at=datetime.now(timezone.utc), delivered_by=user["username"])
        else:
            upd.update(delivered=False, delivered_at=None, delivered_by=None)
        doc = await db.loads.find_one_and_update(
            {"id": id, "cancelled": {"$ne": True}},
            {"$set": upd}, projection={"_id": 0}, return_document=True, session=session,
        )
        if not doc:
            raise HTTPException(409, "load_changed_retry")
        await _audit_load_event(doc, user, "LOAD_STATUS_UPDATED", {
            "previous_status": previous_status, "new_status": st,
        }, session=session)
        return doc

    doc = await run_transaction(operation)
    labs = await _labs_for([id])
    return to_load(doc, user, labs.get(id))


@router.post("/loads/{id}/deliver", response_model=Load)
async def deliver_load(id: str, user: dict = Depends(current_user)):
    async def operation(session):
        cur = await db.loads.find_one({"id": id}, {"_id": 0}, session=session)
        if not cur:
            raise HTTPException(404, "not_found")
        if cur.get("cancelled"):
            raise HTTPException(409, "load_cancelled")
        if cur.get("oil_kg") is None:
            raise HTTPException(409, "oil_not_ready")
        if cur.get("delivered"):
            raise HTTPException(409, "already_delivered")
        delivered_at = datetime.now(timezone.utc)
        doc = await db.loads.find_one_and_update(
            {"id": id, "delivered": {"$ne": True}, "cancelled": {"$ne": True}, "oil_kg": {"$ne": None}},
            {"$set": {"delivered": True, "delivered_at": delivered_at, "delivered_by": user["username"]}},
            projection={"_id": 0}, return_document=True, session=session,
        )
        if not doc:
            raise HTTPException(409, "load_changed_retry")
        await _audit_load_event(doc, user, "LOAD_DELIVERED", {"delivered_at": doc.get("delivered_at")}, session=session)
        return doc

    doc = await run_transaction(operation)
    labs = await _labs_for([id])
    return to_load(doc, user, labs.get(id))


@router.get("/loads/cancellations", response_model=list[Load])
async def cancellations(month: str = Query("", pattern=r"^(\d{4}-\d{2})?$"), user: dict = Depends(require_admin)):
    m = month or today_iso()[:7]
    y, mo = int(m[:4]), int(m[5:7])
    tz = _tz()
    start = datetime(y, mo, 1, tzinfo=tz)
    end = datetime(y + (mo == 12), 1 if mo == 12 else mo + 1, 1, tzinfo=tz)
    start_utc, end_utc = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    docs = await db.loads.find(
        {
            "$or": [
                # Ordinary cancellations remain scoped to the selected month.
                {"cancelled": True, "cancelled_at": {"$gte": start_utc, "$lt": end_utc}},
                # A direct sale to the mill must remain visible in Annuler even
                # when the purchase date differs from the current month, or an
                # older record is missing its transfer timestamp.
                {"ownership_transferred": True},
            ],
        },
        {"_id": 0},
    ).sort([("cancelled_at", -1), ("ownership_transferred_at", -1)]).to_list(1000)
    return [to_load(d, user) for d in docs]


@router.post("/loads/{id}/cancel", response_model=Load)
async def cancel_load(id: str, body: CancelBody, user: dict = Depends(require_admin)):
    async def operation(session):
        current = await db.loads.find_one({"id": id}, {"_id": 0, "ownership_transferred": 1}, session=session)
        if not current:
            raise HTTPException(404, "not_found")
        if current.get("ownership_transferred"):
            raise HTTPException(409, "load_ownership_transferred_to_mill")
        if current.get("cancelled"):
            raise HTTPException(409, "load_cancelled")
        cancelled_at = datetime.now(timezone.utc)
        doc = await db.loads.find_one_and_update(
            {"id": id, "cancelled": {"$ne": True}, "ownership_transferred": {"$ne": True}},
            {"$set": {"cancelled": True, "cancel_reason": body.reason.strip(),
                      "cancelled_at": cancelled_at, "cancelled_by": user["username"]}},
            projection={"_id": 0}, return_document=True, session=session,
        )
        if not doc:
            if await db.loads.find_one({"id": id}, session=session):
                raise HTTPException(409, "load_cancelled")
            raise HTTPException(404, "not_found")
        await _audit_load_event(doc, user, "LOAD_CANCELLED", {
            "cancel_reason": doc.get("cancel_reason"), "cancelled_at": doc.get("cancelled_at")
        }, session=session)
        return doc

    doc = await run_transaction(operation)
    labs = await _labs_for([id])
    return to_load(doc, user, labs.get(id))


async def _ensure_load_has_no_invoice(load_id: str, session=None) -> None:
    """Preserve accounting history, using the caller's transaction when supplied."""
    options = {"session": session} if session is not None else {}
    invoice = await db.invoices.find_one(
        {"load_id": load_id},
        {"_id": 0, "number": 1},
        **options,
    )
    if invoice:
        raise HTTPException(409, "load_has_invoice")


async def _ensure_load_is_deletable(load_id: str, session=None, load_doc: dict | None = None) -> dict:
    """Shared hard-delete guard for every traditional-load deletion entry point."""
    options = {"session": session} if session is not None else {}
    doc = load_doc or await db.loads.find_one({"id": load_id}, {"_id": 0}, **options)
    if not doc:
        raise HTTPException(404, "not_found")

    await _ensure_load_has_no_invoice(load_id, session=session)

    if doc.get("ownership_transferred") or to_decimal(doc.get("custody_received_kg", 0)) > 0:
        raise HTTPException(409, "load_ownership_or_custody_transferred")
    original = to_decimal(doc.get("olive_kg", 0))
    available_raw = doc.get("customer_available_olive_kg")
    available = to_decimal(original if available_raw is None else available_raw)
    if available < original:
        raise HTTPException(409, "load_ownership_or_custody_transferred")

    if doc.get("pressing") or doc.get("delivered") or doc.get("cancelled") or doc.get("oil_kg") is not None:
        raise HTTPException(409, "load_has_operational_history")

    for collection_name in (
        "commercial_direct_load_purchases",
        "commercial_customer_custody_receipts",
        "commercial_lots",
    ):
        reference = await db[collection_name].find_one(
            {"source_load_id": load_id}, {"_id": 0, "id": 1}, **options
        )
        if reference:
            raise HTTPException(409, "load_has_gs_reference")

    lab = await db.lab.find_one({"load_id": load_id}, {"_id": 0, "id": 1}, **options)
    if lab:
        raise HTTPException(409, "load_has_lab_history")
    sms = await db.sms_log.find_one({"load_id": load_id}, {"_id": 0, "id": 1}, **options)
    if sms:
        raise HTTPException(409, "load_has_sms_history")
    return doc


async def _delete_load_in_transaction(load_id: str, session, user: dict):
    doc = await _ensure_load_is_deletable(load_id, session=session)
    res = await db.loads.delete_one({"id": load_id}, session=session)
    if not res.deleted_count:
        raise HTTPException(404, "not_found")
    await _audit_load_event(doc, user, "LOAD_DELETED", {
        "olive_kg": doc.get("olive_kg"), "oil_kg": doc.get("oil_kg"),
        "created_at": doc.get("created_at"),
        "weight_measurement": weight_measurement_audit_snapshot(doc.get("weight_measurement")),
    }, session=session)
    return {"ok": True}


@router.delete("/loads/{id}")
async def delete_load(id: str, user: dict = Depends(require_admin)):
    return await run_transaction(lambda session: _delete_load_in_transaction(id, session, user))


@router.get("/stats", response_model=Stats)
async def stats(user: dict = Depends(current_user)):
    is_admin = user["role"] == "admin"
    today = today_iso()
    season = await active_season()
    docs = await db.loads.find({"cancelled": {"$ne": True}, **(await season_filter(season))}, {"_id": 0}).to_list(100000)
    by_day: dict[str, list[float]] = {}
    o_t = oil_t = rev_t = 0.0
    olive_done = oil_done = 0.0
    for d in docs:
        rev = money_float(to_decimal(d["olive_kg"]) * to_decimal(d.get("price_per_kg", 0)))
        oil = d.get("oil_kg") or 0.0
        agg = by_day.setdefault(d["day"], [0.0, 0.0, 0.0, 0.0])
        agg[0] += d["olive_kg"]; agg[1] += oil; agg[2] += rev; agg[3] += 1
        o_t += d["olive_kg"]; oil_t += oil; rev_t += rev
        if d.get("oil_kg") is not None:
            olive_done += d["olive_kg"]; oil_done += d["oil_kg"]
    start = datetime.strptime(today, "%Y-%m-%d") - timedelta(days=13)
    daily = []
    for i in range(14):
        day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        a = by_day.get(day, [0.0, 0.0, 0.0, 0.0])
        daily.append(DailyPoint(day=day, olive_kg=round(a[0], 2), oil_kg=round(a[1], 2),
                                revenue=round(a[2], 3) if is_admin else None))
    t = by_day.get(today, [0.0, 0.0, 0.0, 0.0])
    non_terminated = sum(
        1 for d in docs if d.get("oil_kg") is None
    )
    return Stats(
        today=today, season=season, loads_today=int(t[3]),
        non_terminated=non_terminated, loads_total=len(docs),
        pending=sum(1 for d in docs if d.get("oil_kg") is None),
        olive_kg_today=round(t[0], 2), oil_kg_today=round(t[1], 2),
        olive_kg_total=round(o_t, 2), oil_kg_total=round(oil_t, 2),
        avg_yield=round(oil_done / olive_done * 100, 2) if olive_done else None,
        revenue_today=round(t[2], 3) if is_admin else None,
        revenue_total=round(rev_t, 3) if is_admin else None,
        daily=daily,
    )
