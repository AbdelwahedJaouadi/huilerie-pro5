import uuid
from datetime import date as Date, datetime, timedelta, timezone
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from lib.workforce_auth import require_workforce_admin
from lib.db import db, run_transaction

router = APIRouter(prefix="/workforce", tags=["workforce"])


class AttendanceAction(BaseModel):
    worker_id: str = Field(min_length=1, max_length=100)
    day: Date


class AttendanceCorrection(BaseModel):
    check_in_at: Optional[datetime] = None
    check_out_at: Optional[datetime] = None
    status: Optional[Literal["PRESENT", "ABSENT"]] = None
    reason: str = Field(min_length=5, max_length=500)


def _today_tunis() -> Date:
    return datetime.now(ZoneInfo("Africa/Tunis")).date()


def _ensure_today(day: Date):
    if day != _today_tunis():
        raise HTTPException(400, "attendance_actions_today_only")


async def _active_worker(worker_id: str):
    worker = await db.users.find_one(
        {"id": worker_id, "role": "worker", "active": True},
        {"_id": 0, "id": 1, "full_name": 1, "username": 1},
    )
    if not worker:
        raise HTTPException(404, "active_worker_not_found")
    return worker


async def _audit(record: dict, action: str, admin: dict, details: dict | None = None, session=None):
    event = {
        "id": str(uuid.uuid4()),
        "attendance_id": record["id"],
        "worker_id": record["worker_id"],
        "day": record["day"],
        "action": action,
        "actor_user_id": admin.get("id"),
        "actor_username": admin.get("username"),
        "details": details or {},
        "created_at": datetime.now(timezone.utc),
    }
    await db["workforce_attendance_events"].insert_one(event, session=session)


@router.get("/attendance")
async def list_attendance(day: Date | None = None, _: dict = Depends(require_workforce_admin)):
    selected_day = day or _today_tunis()
    records = await db["workforce_attendance"].find(
        {"day": selected_day.isoformat()}, {"_id": 0}
    ).sort("worker_name", 1).to_list(1000)
    recorded_worker_ids = [record["worker_id"] for record in records]
    workers = await db.users.find(
        {
            "role": "worker",
            "$or": [
                {"active": True},
                {"id": {"$in": recorded_worker_ids}},
            ],
        },
        {"_id": 0, "id": 1, "full_name": 1, "username": 1, "active": 1},
    ).sort("full_name", 1).to_list(500)
    return {"day": selected_day.isoformat(), "workers": workers, "records": records}


@router.post("/attendance/check-in")
async def check_in(body: AttendanceAction, admin: dict = Depends(require_workforce_admin)):
    _ensure_today(body.day)
    worker = await _active_worker(body.worker_id)
    day = body.day.isoformat()
    now = datetime.now(timezone.utc)
    existing = await db["workforce_attendance"].find_one(
        {"worker_id": worker["id"], "day": day}, {"_id": 0}
    )
    if existing and (existing.get("status") == "PRESENT" or existing.get("check_in_at")):
        raise HTTPException(409, "worker_already_checked_in")

    if existing:
        async def restore_absent(session):
            result = await db["workforce_attendance"].update_one(
                {"id": existing["id"], "status": "ABSENT", "check_in_at": None},
                {"$set": {
                    "status": "PRESENT", "check_in_at": now, "check_out_at": None,
                    "marked_absent_at": None, "updated_at": now,
                }},
                session=session,
            )
            if result.modified_count != 1:
                raise HTTPException(409, "attendance_changed_retry")
            record = await db["workforce_attendance"].find_one(
                {"id": existing["id"]}, {"_id": 0}, session=session
            )
            await _audit(record, "CHECK_IN_AFTER_ABSENCE_MARK", admin, session=session)
            return record
        return await run_transaction(restore_absent)

    record = {
        "id": str(uuid.uuid4()), "worker_id": worker["id"],
        "worker_name": worker["full_name"], "day": day,
        "status": "PRESENT", "check_in_at": now, "check_out_at": None,
        "marked_absent_at": None, "created_by": admin.get("id"),
        "created_at": now, "updated_at": now,
    }
    async def create_present(session):
        await db["workforce_attendance"].insert_one(record, session=session)
        await _audit(record, "CHECK_IN", admin, session=session)
        return {key: value for key, value in record.items() if key != "_id"}
    try:
        return await run_transaction(create_present)
    except DuplicateKeyError:
        raise HTTPException(409, "attendance_already_exists")


@router.post("/attendance/check-out")
async def check_out(body: AttendanceAction, admin: dict = Depends(require_workforce_admin)):
    _ensure_today(body.day)
    worker = await db.users.find_one({"id": body.worker_id, "role": "worker"}, {"_id": 0, "id": 1})
    if not worker:
        raise HTTPException(404, "worker_not_found")
    day = body.day.isoformat()
    now = datetime.now(timezone.utc)
    record = await db["workforce_attendance"].find_one(
        {"worker_id": worker["id"], "day": day}, {"_id": 0}
    )
    if not record or record.get("status") != "PRESENT" or not record.get("check_in_at"):
        raise HTTPException(409, "worker_not_checked_in")
    if record.get("check_out_at"):
        raise HTTPException(409, "worker_already_checked_out")

    async def close_attendance(session):
        result = await db["workforce_attendance"].update_one(
            {"id": record["id"], "check_out_at": None, "status": "PRESENT"},
            {"$set": {"check_out_at": now, "updated_at": now}},
            session=session,
        )
        if result.modified_count != 1:
            raise HTTPException(409, "attendance_changed_retry")
        updated = await db["workforce_attendance"].find_one(
            {"id": record["id"]}, {"_id": 0}, session=session
        )
        await _audit(updated, "CHECK_OUT", admin, session=session)
        return updated
    return await run_transaction(close_attendance)


@router.post("/attendance/mark-absent")
async def mark_absent(body: AttendanceAction, admin: dict = Depends(require_workforce_admin)):
    _ensure_today(body.day)
    worker = await _active_worker(body.worker_id)
    day = body.day.isoformat()
    now = datetime.now(timezone.utc)
    record = {
        "id": str(uuid.uuid4()), "worker_id": worker["id"],
        "worker_name": worker["full_name"], "day": day,
        "status": "ABSENT", "check_in_at": None, "check_out_at": None,
        "marked_absent_at": now, "created_by": admin.get("id"),
        "created_at": now, "updated_at": now,
    }
    async def create_absence(session):
        await db["workforce_attendance"].insert_one(record, session=session)
        await _audit(record, "MARK_ABSENT", admin, session=session)
        return {key: value for key, value in record.items() if key != "_id"}
    try:
        return await run_transaction(create_absence)
    except DuplicateKeyError:
        raise HTTPException(409, "attendance_already_exists")


@router.patch("/attendance/{attendance_id}")
async def correct_attendance(
    attendance_id: str,
    body: AttendanceCorrection,
    admin: dict = Depends(require_workforce_admin),
):
    record = await db["workforce_attendance"].find_one(
        {"id": attendance_id}, {"_id": 0}
    )
    if not record:
        raise HTTPException(404, "attendance_not_found")
    changes = {}
    if body.status is not None:
        changes["status"] = body.status
    if "check_in_at" in body.model_fields_set:
        changes["check_in_at"] = (
            body.check_in_at.astimezone(timezone.utc)
            if body.check_in_at and body.check_in_at.tzinfo
            else body.check_in_at.replace(tzinfo=timezone.utc) if body.check_in_at else None
        )
    if "check_out_at" in body.model_fields_set:
        changes["check_out_at"] = (
            body.check_out_at.astimezone(timezone.utc)
            if body.check_out_at and body.check_out_at.tzinfo
            else body.check_out_at.replace(tzinfo=timezone.utc) if body.check_out_at else None
        )
    check_in = changes.get("check_in_at", record.get("check_in_at"))
    check_out = changes.get("check_out_at", record.get("check_out_at"))
    status = changes.get("status", record.get("status"))
    if status == "PRESENT" and check_in is None:
        raise HTTPException(400, "present_requires_check_in")
    if check_out is not None and (check_in is None or check_out < check_in):
        raise HTTPException(400, "checkout_must_follow_checkin")
    now = datetime.now(timezone.utc)
    for attendance_time in (check_in, check_out):
        if attendance_time is not None:
            if attendance_time.astimezone(ZoneInfo("Africa/Tunis")).date().isoformat() != record["day"]:
                raise HTTPException(400, "attendance_time_must_match_day")
            if attendance_time > now + timedelta(minutes=1):
                raise HTTPException(400, "attendance_time_cannot_be_future")
    if status == "ABSENT" and (check_in is not None or check_out is not None):
        raise HTTPException(400, "absent_cannot_have_times")
    if not changes:
        raise HTTPException(400, "no_attendance_changes")

    if "status" in changes:
        changes["marked_absent_at"] = now if status == "ABSENT" else None
    changes.update({"updated_at": now, "last_corrected_by": admin.get("id")})
    async def apply_correction(session):
        result = await db["workforce_attendance"].update_one(
            {"id": attendance_id}, {"$set": changes}, session=session
        )
        if result.modified_count != 1:
            raise HTTPException(409, "attendance_changed_retry")
        updated = await db["workforce_attendance"].find_one(
            {"id": attendance_id}, {"_id": 0}, session=session
        )
        await _audit(updated, "CORRECT", admin, {
            "reason": body.reason,
            "before": {
                "status": record.get("status"),
                "check_in_at": record.get("check_in_at"),
                "check_out_at": record.get("check_out_at"),
            },
            "after": {
                "status": updated.get("status"),
                "check_in_at": updated.get("check_in_at"),
                "check_out_at": updated.get("check_out_at"),
            },
        }, session=session)
        return updated
    return await run_transaction(apply_correction)
