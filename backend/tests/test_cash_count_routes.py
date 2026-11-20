import ast
from pathlib import Path


def test_cash_count_endpoints_are_admin_only_and_do_not_calculate_balances():
    source = (Path(__file__).parents[1] / "routers" / "accounting.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    routes = {node.name: node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)}
    assert {"create_cash_count", "list_cash_counts"} <= routes.keys()
    create = ast.get_source_segment(source, routes["create_cash_count"])
    listing = ast.get_source_segment(source, routes["list_cash_counts"])
    assert "Depends(require_admin)" in create
    assert "Depends(require_admin)" in listing
    assert "accounting_cash_counts.insert_one" in create
    assert "accounting_cash_count_events.insert_one" in create
    assert "expected_amount_calculated" in create
    assert "variance_calculated" in create
    assert "update_one" not in create and "delete_one" not in create
    assert "expected_cash_calculated" in listing
    assert "variance_calculated" in listing


def test_cash_count_collections_have_immutable_identity_and_audit_indexes():
    source = (Path(__file__).parents[1] / "lib" / "db.py").read_text(encoding="utf-8")
    assert '"accounting_cash_counts"' in source
    assert '"accounting_cash_count_events"' in source
    assert '"season_account_count_date"' in source
