import ast
import re
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_workforce_mutations_are_admin_only_and_audited_transactionally():
    source = (ROOT / "routers" / "workforce.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    routes = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
    }
    expected = {"check_in", "check_out", "mark_absent", "correct_attendance"}
    assert expected <= routes.keys()
    for name in expected:
        route_source = ast.get_source_segment(source, routes[name])
        assert "Depends(require_workforce_admin)" in route_source
        assert "run_transaction(" in route_source
        assert "_audit(" in route_source


def test_workforce_attendance_has_one_record_per_worker_per_day():
    source = (ROOT / "lib" / "db.py").read_text(encoding="utf-8")
    assert '"workforce_attendance"' in source
    assert '"worker_day_unique"' in source
    assert 'unique=True' in source[source.index('"workforce_attendance"'):source.index('"workforce_attendance_events"')]


def test_attendance_corrections_require_reason_and_validate_time_order():
    source = (ROOT / "routers" / "workforce.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    correction = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "AttendanceCorrection")
    schema_source = ast.get_source_segment(source, correction)
    assert 'reason: str = Field(min_length=5, max_length=500)' in schema_source
    route = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "correct_attendance")
    route_source = ast.get_source_segment(source, route)
    assert '"checkout_must_follow_checkin"' in route_source
    assert '"absent_cannot_have_times"' in route_source


def test_workforce_page_uses_tunisian_clock_and_admin_navigation():
    page = (ROOT.parent / "frontend" / "src" / "pages" / "Workforce.tsx").read_text(encoding="utf-8")
    shell = (ROOT.parent / "frontend" / "src" / "components" / "AppShell.tsx").read_text(encoding="utf-8")
    assert 'timeZone: "Africa/Tunis"' in page
    assert '"/workforce"' in shell
    assert 'admin: true' in shell


def test_workforce_range_endpoint_supports_inclusive_history_without_changing_legacy_day():
    source = (ROOT / "routers" / "workforce.py").read_text(encoding="utf-8")
    assert "start_date: Date | None = None" in source
    assert "end_date: Date | None = None" in source
    assert '"$gte": selected_start.isoformat()' in source
    assert '"$lte": selected_end.isoformat()' in source
    assert '"use_day_or_date_range"' in source
    assert 'return {' in source and '"start_date": selected_start.isoformat()' in source


def test_workforce_prevents_second_checkin_until_open_shift_is_closed():
    source = (ROOT / "routers" / "workforce.py").read_text(encoding="utf-8")
    assert '"worker_has_open_shift"' in source
    assert '"check_out_at": None' in source
    assert "checkout_must_be_on_shift_day_or_next_day" in source


def test_workforce_ui_has_date_range_and_daily_weekly_monthly_summaries():
    page = (ROOT.parent / "frontend" / "src" / "pages" / "Workforce.tsx").read_text(encoding="utf-8")
    assert "start_date=" in page and "end_date=" in page
    assert "summarize(records, (record) => record.day)" in page
    assert "weekStart(record.day)" in page
    assert 'record.day.slice(0, 7)' in page
    assert "elapsed > 24 * 60 * 60 * 1000" in page
    assert "Aucune pause n’est déduite." in page
    assert "لا توجد سجلات في الفترة المختارة. عدم وجود سجل لا يعني الغياب." in page



def test_open_overnight_shifts_remain_visible_outside_selected_history_range():
    source = (ROOT / "routers" / "workforce.py").read_text(encoding="utf-8")
    page = (ROOT.parent / "frontend" / "src" / "pages" / "Workforce.tsx").read_text(encoding="utf-8")
    assert '"open_shifts": open_shifts' in source
    assert '"check_out_at": None' in source
    assert "openShiftsByWorker" in page
    assert "recordsToday.get(worker.id) ?? openShiftsByWorker.get(worker.id)" in page


def test_absence_cannot_be_marked_while_worker_has_an_open_shift():
    source = (ROOT / "routers" / "workforce.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    route = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "mark_absent")
    route_source = ast.get_source_segment(source, route)
    assert '"worker_has_open_shift"' in route_source
    assert 'raise HTTPException(409, "worker_has_open_shift")' in route_source


def test_workforce_has_independent_employee_registry_and_permanent_cascade_delete():
    source = (ROOT / "routers" / "workforce.py").read_text(encoding="utf-8")
    assert '@router.get("/workers")' in source
    assert '@router.post("/workers")' in source
    assert '@router.patch("/workers/{worker_id}")' in source
    assert '@router.delete("/workers/{worker_id}")' in source
    assert 'db.employees.find_one' in source
    assert '"salary_type"' in source and '"salary_amount"' in source
    delete_route = next(node for node in ast.parse(source).body if isinstance(node, ast.AsyncFunctionDef) and node.name == "delete_worker")
    delete_source = ast.get_source_segment(source, delete_route)
    assert "run_transaction(permanently_delete_worker)" in delete_source
    assert '"workforce_attendance_events"' in delete_source
    assert "delete_many" in delete_source
    assert "attendance_deleted" in delete_source
    assert not re.search(r'^\s*"(?:user_id|username)"\s*:', source, re.MULTILINE)
    assert 'migration_key = "workforce_employees_registry_v1"' in source
    assert 'db.users.find(' in source
    assert '$setOnInsert' in source


def test_employee_registry_import_is_one_time_and_has_no_account_link_fields():
    source = (ROOT / "routers" / "workforce.py").read_text(encoding="utf-8")
    assert 'migration_key = "workforce_employees_registry_v1"' in source
    assert 'db.settings.find_one({"key": migration_key}' in source
    assert 'db.settings.update_one(' in source
    assert not re.search(r'^\s*"(?:user_id|username)"\s*:', source, re.MULTILINE)
    indexes = (ROOT / "lib" / "db.py").read_text(encoding="utf-8")
    employee_indexes = indexes[indexes.index('"employees"'):indexes.index('"workforce_attendance"')]
    assert "user_id" not in employee_indexes


def test_employee_delete_requires_a_second_explicit_confirmation_in_ui():
    page = (ROOT.parent / "frontend" / "src" / "pages" / "Workforce.tsx").read_text(encoding="utf-8")
    assert 'data-testid="delete-employee-confirmation"' in page
    assert 'Confirmer la suppression définitive' in page
    assert 'Les données de l’employé, tous ses pointages et leur historique de corrections seront effacés.' in page
    assert 'onClick={()=>setDeletingEmployee(worker)}' in page


def test_worker_payroll_routes_are_admin_only_and_atomic_with_treasury():
    source = (ROOT / "routers" / "workforce.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    routes = {node.name: node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)}
    assert {"get_worker_payroll", "create_worker_payment"} <= routes.keys()
    create_source = ast.get_source_segment(source, routes["create_worker_payment"])
    assert "Depends(require_workforce_admin)" in create_source
    assert "run_transaction(operation)" in create_source
    assert 'db["workforce_worker_payments"].insert_one(payment, session=session)' in create_source
    assert 'db["accounting_treasury_movements"].insert_one(movement, session=session)' in create_source
    assert 'db["accounting_treasury_movement_events"].insert_one' in create_source
    assert '"idempotency_key": body.idempotency_key' in create_source


def test_worker_payroll_uses_closed_shifts_and_daily_salary_eight_hour_basis():
    source = (ROOT / "routers" / "workforce.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    shift = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_worker_shift_minutes")
    shift_source = ast.get_source_segment(source, shift)
    assert 'record.get("status") != "PRESENT"' in shift_source
    assert 'record.get("check_out_at")' in shift_source
    assert "elapsed > 24 * 60 * 60" in shift_source
    snapshot = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "_worker_payroll_snapshot")
    snapshot_source = ast.get_source_segment(source, snapshot)
    assert "Decimal(480)" in snapshot_source
    assert "Decimal(60)" in snapshot_source
    assert 'salary_type not in {"daily", "hourly"}' in snapshot_source


def test_worker_payments_enforce_account_type_and_accrued_wage_limit():
    source = (ROOT / "routers" / "workforce.py").read_text(encoding="utf-8")
    route = next(node for node in ast.parse(source).body if isinstance(node, ast.AsyncFunctionDef) and node.name == "create_worker_payment")
    route_source = ast.get_source_segment(source, route)
    assert 'expected_type = "CASH" if body.payment_method == "CASH" else "BANK"' in route_source
    assert '"payment_account_type_mismatch"' in route_source
    assert '"advance_exceeds_accrued_unpaid_wages"' in route_source
    assert '"final_payment_only_after_period_end"' in route_source
    assert '"final_payment_already_recorded"' in route_source


def test_worker_payments_are_reconciled_administratively_without_changing_other_sources():
    source = (ROOT / "routers" / "workforce.py").read_text(encoding="utf-8")
    assert '"source_type": "WORKER_PAYMENT"' in source
    assert '"reconciliation_status": "RECONCILED"' in source
    assert '"reconciliation_basis": "ADMINISTRATIVE_WORKER_PAYMENT_RECORD"' in source
    assert '"BANK_TRANSFER_RECORDED" if body.payment_method == "BANK_TRANSFER"' in source
    assert "build_movement_document(" in source
    indexes = (ROOT / "lib" / "db.py").read_text(encoding="utf-8")
    assert '"workforce_worker_payments"' in indexes
    assert '"idempotency_key_unique"' in indexes
    assert '"worker_period_final_unique"' in indexes


def test_worker_with_payment_history_cannot_be_permanently_deleted():
    source = (ROOT / "routers" / "workforce.py").read_text(encoding="utf-8")
    route = next(node for node in ast.parse(source).body if isinstance(node, ast.AsyncFunctionDef) and node.name == "delete_worker")
    route_source = ast.get_source_segment(source, route)
    assert '"worker_has_payment_history_archive_instead"' in route_source
    assert 'db["workforce_worker_payments"].find_one' in route_source


def test_worker_payroll_ui_exposes_advance_final_payment_and_three_methods():
    page = (ROOT.parent / "frontend" / "src" / "pages" / "Workforce.tsx").read_text(encoding="utf-8")
    treasury = (ROOT.parent / "frontend" / "src" / "components" / "accounting" / "TreasuryMovementRegister.tsx").read_text(encoding="utf-8")
    assert 'data-testid="workforce-advances-payments"' in page
    assert 'value="ADVANCE"' in page and 'value="FINAL"' in page
    assert 'Espèces' in page and 'Chèque' in page and 'Virement' in page
    assert "Reste à payer" in page and "Total des avances" in page
    assert 'type==="WORKER_PAYMENT"' in treasury
    assert "rapprochement administratif" in treasury


def test_payroll_month_snapshots_wage_rate_and_prevents_paid_wage_reduction():
    source = (ROOT / "routers" / "workforce.py").read_text(encoding="utf-8")
    snapshot = next(node for node in ast.parse(source).body if isinstance(node, ast.AsyncFunctionDef) and node.name == "_worker_payroll_snapshot")
    snapshot_source = ast.get_source_segment(source, snapshot)
    assert '"workforce_worker_payroll_periods"' in snapshot_source
    correction = next(node for node in ast.parse(source).body if isinstance(node, ast.AsyncFunctionDef) and node.name == "correct_attendance")
    correction_source = ast.get_source_segment(source, correction)
    assert '"attendance_correction_would_reduce_paid_wages"' in correction_source
    indexes = (ROOT / "lib" / "db.py").read_text(encoding="utf-8")
    assert '"worker_period_unique"' in indexes


def test_completed_worker_bank_transfers_are_included_in_account_balances():
    accounting = (ROOT / "routers" / "accounting.py").read_text(encoding="utf-8")
    assert '"BANK_TRANSFER_RECORDED"' in accounting
