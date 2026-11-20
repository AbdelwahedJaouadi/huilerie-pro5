import ast
from pathlib import Path


def test_treasury_account_routes_are_admin_protected_and_never_create_opening_balances():
    root = Path(__file__).parents[1]
    source = (root / "routers" / "accounting.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    routes = {node.name: node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)}
    assert {"list_treasury_accounts", "create_treasury_account", "update_treasury_account_status"} <= routes.keys()
    create_source = ast.get_source_segment(source, routes["create_treasury_account"])
    assert "Depends(require_admin)" in create_source
    assert "opening_balance_status" in create_source
    assert '"opening_balance"' not in create_source
    assert "run_transaction(operation)" in create_source


def test_treasury_directory_has_unique_account_names_and_immutable_event_indexes():
    source = (Path(__file__).parents[1] / "lib" / "db.py").read_text(encoding="utf-8")
    assert '"accounting_treasury_accounts"' in source
    assert '"type_name_unique"' in source
    assert '"accounting_treasury_account_events"' in source
