import ast
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
        assert "Depends(require_admin)" in route_source
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
