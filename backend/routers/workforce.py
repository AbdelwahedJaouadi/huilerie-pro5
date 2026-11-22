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


class EmployeeCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    phone: str = Field(default="", max_length=40)
    address: str = Field(default="", max_length=300)
    salary_amount: float | None = Field(default=None, ge=0)
    salary_type: Literal["monthly", "daily", "hourly"] = "monthly"


class EmployeeUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=300)
    salary_amount: float | None = Field(default=None, ge=0)
    salary_type: Literal["monthly", "daily", "hourly"] | None = None
    active: bool | None = None


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


async def _ensure_legacy_employee_records():
    """Import legacy workers once, preserving IDs used by historical attendance."""
    migration_key = "workforce_employees_registry_v1"
    if await db.settings.find_one({"key": migration_key}, {"_id": 1}):
        return
    # Upserts are idempotent: if a request is interrupted, the next request safely resumes.
    async for user in db.users.find(
        {"role": "worker"},
        {"_id": 0, "id": 1, "full_name": 1, "active": 1},
    ):
        worker_id = user.get("id")
        if not worker_id:
            continue
        full_name = str(user.get("full_name") or "Worker").strip() or "Worker"
        # Legacy accounts without an explicit active flag remain active.
        is_active = user.get("active") is not False
        await db.employees.update_one(
            {"id": worker_id},
            {"$setOnInsert": {
                "id": worker_id, "first_name": full_name, "last_name": "",
                "full_name": full_name, "phone": "", "address": "",
                "salary_amount": None, "salary_type": "monthly",
                "active": is_active, "archived": not is_active,
                "created_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    await db.settings.update_one(
        {"key": migration_key},
        {"$set": {"key": migration_key, "value": True, "completed_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


async def _active_worker(worker_id: str):
    worker = await db.employees.find_one(
        {"id": worker_id, "active": True, "archived": {"$ne": True}},
        {"_id": 0, "id": 1, "full_name": 1},
    )
    if not worker:
        raise HTTPException(404, "active_worker_not_found")
    return worker


def _employee_name(first_name: str, last_name: str) -> str:
    return " ".join(part.strip() for part in (first_name, last_name) if part and part.strip())


@router.get("/workers")
async def list_workers(_: dict = Depends(require_workforce_admin)):
    await _ensure_legacy_employee_records()
    workers = await db.employees.find({}, {"_id": 0}).sort([("active", -1), ("full_name", 1)]).to_list(2000)
    return {"workers": workers, "total": len(workers)}


@router.post("/workers")
async def create_worker(body: EmployeeCreate, admin: dict = Depends(require_workforce_admin)):
    await _ensure_legacy_employee_records()
    first_name = body.first_name.strip()
    if not first_name:
        raise HTTPException(400, "worker_first_name_required")
    now = datetime.now(timezone.utc)
    employee = {
        "id": str(uuid.uuid4()), "first_name": first_name,
        "last_name": body.last_name.strip(), "full_name": _employee_name(first_name, body.last_name),
        "phone": body.phone.strip(), "address": body.address.strip(),
        "salary_amount": body.salary_amount, "salary_type": body.salary_type,
        "active": True, "archived": False,
        "created_at": now, "updated_at": now, "created_by": admin.get("id"),
    }
    await db.employees.insert_one(employee)
    return {key: value for key, value in employee.items() if key != "_id"}


@router.patch("/workers/{worker_id}")
async def update_worker(worker_id: str, body: EmployeeUpdate, admin: dict = Depends(require_workforce_admin)):
    await _ensure_legacy_employee_records()
    worker = await db.employees.find_one({"id": worker_id}, {"_id": 0})
    if not worker:
        raise HTTPException(404, "worker_not_found")
    changes = {key: value for key, value in body.model_dump(exclude_unset=True).items()}
    if not changes:
        raise HTTPException(400, "no_worker_changes")
    if "first_name" in changes:
        changes["first_name"] = (changes["first_name"] or "").strip()
        if not changes["first_name"]:
            raise HTTPException(400, "worker_first_name_required")
    if "last_name" in changes:
        changes["last_name"] = (changes["last_name"] or "").strip()
    for key in ("phone", "address"):
        if key in changes and changes[key] is not None:
            changes[key] = changes[key].strip()
    first_name = changes.get("first_name", worker.get("first_name", worker.get("full_name", "")))
    last_name = changes.get("last_name", worker.get("last_name", ""))
    if "first_name" in changes or "last_name" in changes:
        changes["full_name"] = _employee_name(first_name, last_name)
    if "active" in changes:
        changes["archived"] = not changes["active"]
    changes["updated_at"] = datetime.now(timezone.utc)
    changes["updated_by"] = admin.get("id")
    await db.employees.update_one({"id": worker_id}, {"$set": changes})
    return await db.employees.find_one({"id": worker_id}, {"_id": 0})


@router.delete("/workers/{worker_id}")
async def delete_worker(worker_id: str, admin: dict = Depends(require_workforce_admin)):
    await _ensure_legacy_employee_records()

    async def permanently_delete_worker(session):
        worker = await db.employees.find_one(
            {"id": worker_id}, {"_id": 0, "id": 1}, session=session
        )
        if not worker:
            raise HTTPException(404, "worker_not_found")

        attendance = await db["workforce_attendance"].find(
            {"worker_id": worker_id}, {"_id": 0, "id": 1}, session=session
        ).to_list(10000)
        attendance_ids = [record["id"] for record in attendance if record.get("id")]

        # Remove audit events tied to this employee or to any of their attendance rows.
        event_filter = {"worker_id": worker_id}
        if attendance_ids:
            event_filter = {"$or": [
                {"worker_id": worker_id},
                {"attendance_id": {"$in": attendance_ids}},
            ]}
        events_result = await db["workforce_attendance_events"].delete_many(
            event_filter, session=session
        )
        attendance_result = await db["workforce_attendance"].delete_many(
            {"worker_id": worker_id}, session=session
        )
        employee_result = await db.employees.delete_one(
            {"id": worker_id}, session=session
        )
        if employee_result.deleted_count != 1:
            raise HTTPException(409, "worker_delete_conflict")
        return {
            "ok": True,
            "deleted": True,
            "attendance_deleted": attendance_result.deleted_count,
            "events_deleted": events_result.deleted_count,
        }

    return await run_transaction(permanently_delete_worker)


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
async def list_attendance(
    day: Date | None = None,
    start_date: Date | None = None,
    end_date: Date | None = None,
    _: dict = Depends(require_workforce_admin),
):
    await _ensure_legacy_employee_records()
    # Keep the legacy single-day contract while allowing inclusive date ranges.
    if day is not None and (start_date is not None or end_date is not None):
        raise HTTPException(400, "use_day_or_date_range")
    if (start_date is None) != (end_date is None):
        raise HTTPException(400, "both_range_dates_required")
    selected_start = start_date or day or _today_tunis()
    selected_end = end_date or day or selected_start
    if selected_start > selected_end:
        raise HTTPException(400, "start_date_after_end_date")
    records = await db["workforce_attendance"].find(
        {"day": {"$gte": selected_start.isoformat(), "$lte": selected_end.isoformat()}},
        {"_id": 0},
    ).sort([("day", 1), ("worker_name", 1)]).to_list(10000)
    # Open shifts are operationally actionable even when their check-in date
    # falls before the selected history range (for example, an overnight shift).
    open_shifts = await db["workforce_attendance"].find(
        {
            "status": "PRESENT",
            "check_in_at": {"$ne": None},
            "check_out_at": None,
        },
        {"_id": 0},
    ).sort([("day", -1), ("worker_name", 1)]).to_list(10000)
    recorded_worker_ids = list({
        record["worker_id"] for record in [*records, *open_shifts]
    })
    workers = await db.employees.find(
        {
            "$or": [
                {"active": True, "archived": {"$ne": True}},
                {"id": {"$in": recorded_worker_ids}},
            ],
        },
        {"_id": 0, "id": 1, "full_name": 1, "first_name": 1, "last_name": 1, "active": 1, "salary_type": 1, "salary_amount": 1},
    ).sort("full_name", 1).to_list(2000)
    return {
        "day": selected_start.isoformat() if selected_start == selected_end else None,
        "start_date": selected_start.isoformat(),
        "end_date": selected_end.isoformat(),
        "workers": workers,
        "records": records,
        "open_shifts": open_shifts,
    }


@router.post("/attendance/check-in")
async def check_in(body: AttendanceAction, admin: dict = Depends(require_workforce_admin)):
    _ensure_today(body.day)
    worker = await _active_worker(body.worker_id)
    day = body.day.isoformat()
    now = datetime.now(timezone.utc)
    open_shift = await db["workforce_attendance"].find_one(
        {"worker_id": worker["id"], "status": "PRESENT", "check_in_at": {"$ne": None}, "check_out_at": None},
        {"_id": 0},
    )
    if open_shift:
        raise HTTPException(409, "worker_has_open_shift")
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
    worker = await db.employees.find_one({"id": body.worker_id}, {"_id": 0, "id": 1})
    if not worker:
        raise HTTPException(404, "worker_not_found")
    now = datetime.now(timezone.utc)
    # A shift belongs to its check-in date and may be closed after midnight.
    record = await db["workforce_attendance"].find_one(
        {"worker_id": worker["id"], "status": "PRESENT", "check_in_at": {"$ne": None}, "check_out_at": None},
        {"_id": 0},
        sort=[("day", -1)],
    )
    if not record:
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
    open_shift = await db["workforce_attendance"].find_one(
        {
            "worker_id": worker["id"],
            "status": "PRESENT",
            "check_in_at": {"$ne": None},
            "check_out_at": None,
        },
        {"_id": 0, "id": 1},
    )
    if open_shift:
        raise HTTPException(409, "worker_has_open_shift")
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
    if check_in is not None:
        if check_in.astimezone(ZoneInfo("Africa/Tunis")).date().isoformat() != record["day"]:
            raise HTTPException(400, "checkin_time_must_match_day")
        if check_in > now + timedelta(minutes=1):
            raise HTTPException(400, "attendance_time_cannot_be_future")
    if check_out is not None:
        checkout_day = check_out.astimezone(ZoneInfo("Africa/Tunis")).date()
        record_day = Date.fromisoformat(record["day"])
        if checkout_day not in (record_day, record_day + timedelta(days=1)):
            raise HTTPException(400, "checkout_must_be_on_shift_day_or_next_day")
        if check_out > now + timedelta(minutes=1):
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
