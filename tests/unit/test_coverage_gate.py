import json

import pytest

from scripts.check_coverage import evaluate, main

TOTALS = {"num_statements": 200, "covered_lines": 180, "num_branches": 50, "covered_branches": 41}


@pytest.mark.parametrize(
    ("min_lines", "min_branches", "expected"),
    [(85, 80, True), (91, 80, False), (85, 83, False)],
)
def test_gate_checks_lines_and_branches_independently(min_lines, min_branches, expected):
    ok, report = evaluate(TOTALS, min_lines, min_branches)
    assert ok is expected
    assert "90.00%" in report
    assert "82.00%" in report


def test_gate_treats_empty_project_as_fully_covered():
    ok, _ = evaluate({"num_statements": 0, "covered_lines": 0}, 85, 80)
    assert ok is True


def test_main_returns_non_zero_exit_code_when_below_threshold(tmp_path, capsys):
    report = tmp_path / "coverage.json"
    report.write_text(json.dumps({"totals": TOTALS}))
    assert main(["--file", str(report), "--lines", "95"]) == 1
    assert "REPROVADO" in capsys.readouterr().out
    assert main(["--file", str(report)]) == 0
