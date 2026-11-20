import pytest

from accounting_foundation.bank_statement_preview import (
    classify_statement_line,
    movement_date_window,
    parse_bank_statement_csv,
)


def test_parse_normalized_csv_with_utf8_bom_and_decimal_amounts():
    raw = (
        b"\xef\xbb\xbftransaction_date,value_date,amount,direction,reference,description\n"
        b"2026-11-20,2026-11-21,125.450,IN,TRX-01,Client payment\n"
    )
    rows = parse_bank_statement_csv(raw)
    assert len(rows) == 1
    assert rows[0]["amount_tnd"] == "125.450"
    assert rows[0]["direction"] == "IN"
    assert rows[0]["reference"] == "TRX-01"
    assert len(rows[0]["fingerprint"]) == 64


@pytest.mark.parametrize("raw,expected", [
    (b"date,amount,direction\n2026-11-20,1,IN\n", "Missing required columns"),
    (b"transaction_date,amount,direction\n20/11/2026,1,IN\n", "Invalid ISO date"),
    (b"transaction_date,amount,direction\n2026-11-20,0,IN\n", "positive TND"),
    (b"transaction_date,amount,direction\n2026-11-20,1.2345,IN\n", "plain decimal notation"),
    (b"transaction_date,amount,direction\n2026-11-20,1e3,IN\n", "plain decimal notation"),
    (b"transaction_date,amount,direction\n2026-11-20,1,000,IN\n", "Unexpected extra CSV fields"),
    (b"transaction_date,amount,direction\n2026-11-20,1,SIDEWAYS\n", "direction must be IN or OUT"),
])
def test_parser_rejects_invalid_statement_rows(raw, expected):
    with pytest.raises(ValueError, match=expected):
        parse_bank_statement_csv(raw)


def test_parser_rejects_duplicate_headers_and_empty_statement():
    with pytest.raises(ValueError, match="duplicate column"):
        parse_bank_statement_csv(b"transaction_date,amount,amount,direction\n")
    with pytest.raises(ValueError, match="no statement lines"):
        parse_bank_statement_csv(b"transaction_date,amount,direction\n")


def test_parser_rejects_more_than_one_hundred_lines():
    rows = ["transaction_date,amount,direction"]
    rows.extend(["2026-11-20,1.000,IN"] * 101)
    with pytest.raises(ValueError, match="more than 100"):
        parse_bank_statement_csv("\n".join(rows).encode())


def test_duplicate_fingerprint_is_stable_for_identical_statement_lines():
    raw = (
        b"transaction_date,amount,direction,reference\n"
        b"2026-11-20,1.000,IN,REF\n"
        b"2026-11-20,1.000,IN,REF\n"
    )
    rows = parse_bank_statement_csv(raw)
    assert rows[0]["fingerprint"] == rows[1]["fingerprint"]


def test_reference_candidate_is_suggestion_not_automatic_match():
    line = {"reference": "REF-1"}
    candidates = [{"id": "movement-1", "external_reference": "REF-1"}]
    result = classify_statement_line(line, candidates)
    assert result["match_status"] == "REFERENCE_CANDIDATE"
    assert result["candidate_count"] == 1
    assert result["automatic_match"] is False


def test_same_amount_without_reference_remains_only_a_possible_match():
    result = classify_statement_line({"reference": None}, [{"id": "movement-1"}])
    assert result["match_status"] == "POSSIBLE_MATCH"
    assert result["automatic_match"] is False


def test_multiple_or_mismatched_references_are_never_auto_matched():
    duplicate_ref = classify_statement_line(
        {"reference": "REF"}, [
            {"id": "m1", "external_reference": "REF"},
            {"id": "m2", "external_reference": "REF"},
        ],
    )
    mismatch = classify_statement_line(
        {"reference": "OTHER"}, [{"id": "m1", "external_reference": "REF"}]
    )
    assert duplicate_ref["match_status"] == "AMBIGUOUS_REFERENCE"
    assert mismatch["match_status"] == "REFERENCE_MISMATCH"
    assert duplicate_ref["automatic_match"] is False
    assert mismatch["automatic_match"] is False


def test_statement_matching_window_is_bounded_and_symmetric():
    assert movement_date_window("2026-11-20") == ("2026-11-13", "2026-11-27")
