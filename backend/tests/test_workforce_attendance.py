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


def test_workforce_has_independent_employee_registry_and_safe_archive():
    source = (ROOT / "routers" / "workforce.py").read_text(encoding="utf-8")
    assert '@router.get("/workers")' in source
    assert '@router.post("/workers")' in source
    assert '@router.patch("/workers/{worker_id}")' in source
    assert '@router.delete("/workers/{worker_id}")' in source
    assert 'db.employees.find_one' in source
    assert '"salary_type"' in source and '"salary_amount"' in source
    assert 'if attendance_count:' in source
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
