import os
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

import lib.db as db_module
import routers.workforce as workforce


@pytest.mark.asyncio(loop_scope="module")
async def test_manager_attendance_lifecycle_is_unique_and_audited(monkeypatch):
    test_db = db_module.client[
        f"{os.environ['DB_NAME'][:20]}_wf_{uuid.uuid4().hex[:12]}"
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
    # Simulate the one-time import of existing login-based workers into the
    # independent employee registry before the attendance flow is exercised.
    await workforce._ensure_legacy_employee_records()

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

        now_tunis = datetime.now(ZoneInfo("Africa/Tunis"))
        midnight = datetime.combine(today, datetime.min.time(), tzinfo=ZoneInfo("Africa/Tunis"))
        if now_tunis < midnight + timedelta(minutes=2):
            start_local = end_local = midnight
        else:
            end_local = now_tunis - timedelta(minutes=1)
            start_local = end_local - timedelta(minutes=1)
        start = start_local.astimezone(timezone.utc)
        end = end_local.astimezone(timezone.utc)
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


@pytest.mark.asyncio(loop_scope="module")
async def test_employee_without_app_login_can_be_managed_and_pointed(monkeypatch):
    test_db = db_module.client[
        f"{os.environ['DB_NAME'][:20]}_emp_{uuid.uuid4().hex[:12]}"
    ]
    monkeypatch.setattr(workforce, "db", test_db)
    await test_db["employees"].create_index("id", unique=True)
    await test_db["workforce_attendance"].create_index(
        [("worker_id", 1), ("day", 1)], unique=True
    )
    await test_db["workforce_attendance_events"].create_index("id", unique=True)
    admin = {"id": "admin-employee-test", "username": "admin"}
    today = workforce._today_tunis()
    try:
        employee = await workforce.create_worker(
            workforce.EmployeeCreate(
                first_name="Samir", last_name="Test",
                phone="+21600000000", address="Test address",
                salary_amount=45, salary_type="daily",
            ),
            admin,
        )
        assert "user_id" not in employee and "username" not in employee
        assert employee["salary_type"] == "daily"
        assert employee["salary_amount"] == 45
        assert await test_db.users.count_documents({"id": employee["id"]}) == 0

        updated = await workforce.update_worker(
            employee["id"],
            workforce.EmployeeUpdate(address="Updated address", salary_type="hourly", salary_amount=8),
            admin,
        )
        assert updated["address"] == "Updated address"
        assert updated["salary_type"] == "hourly"

        attendance = await workforce.check_in(
            workforce.AttendanceAction(worker_id=employee["id"], day=today), admin
        )
        assert attendance["worker_id"] == employee["id"]
        await workforce.check_out(
            workforce.AttendanceAction(worker_id=employee["id"], day=today), admin
        )

        other_employee = await workforce.create_worker(
            workforce.EmployeeCreate(first_name="Other", last_name="Worker"), admin
        )
        other_attendance = await workforce.check_in(
            workforce.AttendanceAction(worker_id=other_employee["id"], day=today), admin
        )
        assert other_attendance["worker_id"] == other_employee["id"]

        deleted = await workforce.delete_worker(employee["id"], admin)
        assert deleted == {
            "ok": True, "deleted": True, "attendance_deleted": 1, "events_deleted": 2,
        }
        assert await test_db.employees.find_one({"id": employee["id"]}) is None
        assert await test_db["workforce_attendance"].count_documents({"worker_id": employee["id"]}) == 0
        assert await test_db["workforce_attendance_events"].count_documents({"worker_id": employee["id"]}) == 0

        # A cascade delete must never touch another employee's data.
        assert await test_db.employees.find_one({"id": other_employee["id"]}) is not None
        assert await test_db["workforce_attendance"].count_documents({"worker_id": other_employee["id"]}) == 1
        assert await test_db["workforce_attendance_events"].count_documents({"worker_id": other_employee["id"]}) == 1
    finally:
        await db_module.client.drop_database(test_db.name)


@pytest.mark.asyncio(loop_scope="module")
async def test_worker_advances_final_payment_and_treasury_posting_are_atomic(monkeypatch):
    test_db = db_module.client[
        f"{os.environ['DB_NAME'][:18]}_pay_{uuid.uuid4().hex[:12]}"
    ]
    monkeypatch.setattr(workforce, "db", test_db)
    async def test_season():
        return "2026-2027"
    monkeypatch.setattr(workforce, "active_season", test_season)

    await test_db["employees"].create_index("id", unique=True)
    await test_db["workforce_worker_payments"].create_index("id", unique=True)
    await test_db["workforce_worker_payments"].create_index("idempotency_key", unique=True)
    await test_db["workforce_worker_payroll_periods"].create_index(
        [("worker_id", 1), ("period", 1)], unique=True
    )
    await test_db["accounting_treasury_movements"].create_index(
        [("season_code", 1), ("source_type", 1), ("source_id", 1)], unique=True
    )
    await test_db["accounting_treasury_movement_events"].create_index("id", unique=True)

    admin = {"id": "admin-payroll-test", "username": "admin"}
    today = workforce._today_tunis()
    previous_month_last_day = today.replace(day=1) - timedelta(days=1)
    period = previous_month_last_day.strftime("%Y-%m")
    attendance_day = f"{period}-01"
    shift_start = datetime.combine(
        previous_month_last_day.replace(day=1), datetime.min.time(),
        tzinfo=timezone.utc,
    ).replace(hour=8)
    shift_end = shift_start + timedelta(hours=4)
    try:
        worker = await workforce.create_worker(
            workforce.EmployeeCreate(
                first_name="Payroll", last_name="Test",
                salary_amount=80, salary_type="daily",
            ),
            admin,
        )
        await test_db["workforce_attendance"].insert_one({
            "id": str(uuid.uuid4()), "worker_id": worker["id"],
            "worker_name": worker["full_name"], "day": attendance_day,
            "status": "PRESENT", "check_in_at": shift_start,
            "check_out_at": shift_end,
        })
        await test_db["accounting_treasury_accounts"].insert_many([
            {"id": "cash-test", "name": "Caisse test", "account_type": "CASH", "active": True},
            {"id": "bank-test", "name": "Banque test", "account_type": "BANK", "active": True},
        ])

        advance = await workforce.create_worker_payment(
            workforce.WorkerPaymentInput(
                worker_id=worker["id"], idempotency_key="advance-test-key-0001",
                period=period, payment_kind="ADVANCE", amount_tnd="15.000",
                payment_method="CASH", account_id="cash-test",
            ),
            admin,
        )
        assert advance["payment"]["amount_tnd"] == "15.000"
        assert advance["reste_a_payer"] == "25.000"

        # Retrying the same request must return the original payment, not post a second one.
        retry = await workforce.create_worker_payment(
            workforce.WorkerPaymentInput(
                worker_id=worker["id"], idempotency_key="advance-test-key-0001",
                period=period, payment_kind="ADVANCE", amount_tnd="15.000",
                payment_method="CASH", account_id="cash-test",
            ),
            admin,
        )
        assert retry["payment"]["id"] == advance["payment"]["id"]

        final = await workforce.create_worker_payment(
            workforce.WorkerPaymentInput(
                worker_id=worker["id"], idempotency_key="final-test-key-000001",
                period=period, payment_kind="FINAL", payment_method="CHEQUE",
                account_id="bank-test",
            ),
            admin,
        )
        assert final["payment"]["amount_tnd"] == "25.000"
        assert final["reste_a_payer"] == "0.000"

        movements = await test_db["accounting_treasury_movements"].find(
            {"source_type": "WORKER_PAYMENT"}, {"_id": 0}
        ).to_list(10)
        assert len(movements) == 2
        cheque_movement = next(row for row in movements if row["payment_method"] == "CHEQUE")
        assert cheque_movement["settlement_status"] == "CHEQUE_CLEARED"
        assert cheque_movement["reconciliation_status"] == "RECONCILED"
        assert cheque_movement["source_party_id"] == worker["id"]

        payroll = await workforce.get_worker_payroll(period, worker["id"], admin)
        assert payroll["workers"][0]["montant_du_travail"] == "40.000"
        assert payroll["workers"][0]["total_advances"] == "15.000"
        assert payroll["workers"][0]["reste_a_payer"] == "0.000"

        # Wage changes apply to future periods; the paid month's rate remains snapshotted.
        await workforce.update_worker(
            worker["id"], workforce.EmployeeUpdate(salary_amount=100), admin
        )
        payroll_after_rate_change = await workforce.get_worker_payroll(period, worker["id"], admin)
        assert payroll_after_rate_change["workers"][0]["montant_du_travail"] == "40.000"

        with pytest.raises(HTTPException) as paid_shift_correction:
            await workforce.correct_attendance(
                (await test_db["workforce_attendance"].find_one({"worker_id": worker["id"]}))["id"],
                workforce.AttendanceCorrection(
                    check_out_at=shift_start + timedelta(hours=1),
                    reason="Attempt to reduce paid hours",
                ),
                admin,
            )
        assert paid_shift_correction.value.status_code == 409

        with pytest.raises(HTTPException) as delete_paid_worker:
            await workforce.delete_worker(worker["id"], admin)
        assert delete_paid_worker.value.status_code == 409
    finally:
        await db_module.client.drop_database(test_db.name)
