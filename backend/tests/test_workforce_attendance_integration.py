import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

import lib.db as db_module
import routers.workforce as workforce


@pytest.mark.asyncio
async def test_manager_attendance_lifecycle_is_unique_and_audited(monkeypatch):
    test_db = db_module.client[
        f"{os.environ['DB_NAME']}_workforce_{uuid.uuid4().hex}"
    ]
    monkeypatch.setattr(workforce, "db", test_db)
    await test_db["workforce_attendance"].create_index(
        [("worker_id", 1), ("day", 1)], unique=True
    )
    await test_db["workforce_attendance_events"].create_index(
        [("id", 1)], unique=True
    )

    admin = {"id": "admin-test", "username": "admin-test"}
    worker_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    for index, worker_id in enumerate(worker_ids):
        await test_db.users.insert_one({
            "id": worker_id,
            "username": f"worker-{index}-{uuid.uuid4().hex[:8]}",
            "full_name": f"Worker {index}",
            "role": "worker",
            "active": True,
        })

    today = workforce._today_tunis()
    try:
        first = await workforce.check_in(
            workforce.AttendanceAction(worker_id=worker_ids[0], day=today),
            admin,
        )
        assert first["status"] == "PRESENT"
        assert first["check_in_at"] is not None

        with pytest.raises(HTTPException) as duplicate_checkin:
            await workforce.check_in(
                workforce.AttendanceAction(worker_id=worker_ids[0], day=today),
                admin,
            )
        assert duplicate_checkin.value.status_code == 409

        departed = await workforce.check_out(
            workforce.AttendanceAction(worker_id=worker_ids[0], day=today),
            admin,
        )
        assert departed["check_out_at"] is not None

        with pytest.raises(HTTPException) as duplicate_checkout:
            await workforce.check_out(
                workforce.AttendanceAction(worker_id=worker_ids[0], day=today),
                admin,
            )
        assert duplicate_checkout.value.status_code == 409

        absent = await workforce.mark_absent(
            workforce.AttendanceAction(worker_id=worker_ids[1], day=today),
            admin,
        )
        assert absent["status"] == "ABSENT"

        restored = await workforce.check_in(
            workforce.AttendanceAction(worker_id=worker_ids[1], day=today),
            admin,
        )
        assert restored["status"] == "PRESENT"
        assert restored["check_in_at"] is not None

        start = datetime.now(timezone.utc) - timedelta(hours=2)
        end = datetime.now(timezone.utc) - timedelta(hours=1)
        corrected = await workforce.correct_attendance(
            restored["id"],
            workforce.AttendanceCorrection(
                check_in_at=start,
                check_out_at=end,
                status="PRESENT",
                reason="Corrected from the manager time sheet",
            ),
            admin,
        )
        assert corrected["check_out_at"] >= corrected["check_in_at"]

        absence_corrected = await workforce.correct_attendance(
            restored["id"],
            workforce.AttendanceCorrection(
                check_in_at=None,
                check_out_at=None,
                status="ABSENT",
                reason="Corrected the absence status after review",
            ),
            admin,
        )
        assert absence_corrected["status"] == "ABSENT"
        assert absence_corrected["marked_absent_at"] is not None

        events = await test_db["workforce_attendance_events"].find(
            {}, {"_id": 0, "action": 1}
        ).to_list(20)
        actions = {event["action"] for event in events}
        assert {
            "CHECK_IN",
            "CHECK_OUT",
            "MARK_ABSENT",
            "CHECK_IN_AFTER_ABSENCE_MARK",
            "CORRECT",
        } <= actions
        assert len(events) == 6

        with pytest.raises(HTTPException) as past_day:
            await workforce.check_in(
                workforce.AttendanceAction(
                    worker_id=worker_ids[0], day=today - timedelta(days=1)
                ),
                admin,
            )
        assert past_day.value.status_code == 400
    finally:
        await db_module.client.drop_database(test_db.name)
