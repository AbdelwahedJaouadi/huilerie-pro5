import ast
from pathlib import Path


def test_cash_opening_balance_is_admin_configurable_and_audited():
    source = (Path(__file__).parents[1] / "routers" / "accounting.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    routes = {node.name: node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)}
    assert "update_treasury_opening_balance" in routes
    route = ast.get_source_segment(source, routes["update_treasury_opening_balance"])
    assert "Depends(require_admin)" in route
    assert "run_transaction(operation)" in route
    assert "OPENING_BALANCE_SET" in route
    assert "OPENING_BALANCE_UPDATED" in route
    assert "accounting_treasury_account_events" in route
    assert "expected_version" in route


def test_cash_balance_only_includes_recorded_movements_on_or_after_opening_date():
    source = (Path(__file__).parents[1] / "routers" / "accounting.py").read_text(encoding="utf-8")
    assert '"movement_date": {"$gte": row["opening_balance_date"]}' in source
    assert '"settlement_status": "CASH_RECORDED"' in source
    assert "opening + incoming - outgoing" in source


def test_bank_and_unconfigured_cash_accounts_keep_movement_based_balances():
    source = (Path(__file__).parents[1] / "routers" / "accounting.py").read_text(encoding="utf-8")
    assert 'movement_scopes.append({"account_id": row["id"]})' in source
    assert '"$or": movement_scopes' in source
