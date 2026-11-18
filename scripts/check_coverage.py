"""Coverage gate: falha se linhas < --lines ou branches < --branches.

O ``fail_under`` do Coverage.py mede apenas um percentual combinado; este script
audita os dois limites exigidos separadamente a partir do ``coverage.json``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def evaluate(totals: dict, min_lines: float, min_branches: float) -> tuple[bool, str]:
    statements = totals["num_statements"]
    branches = totals.get("num_branches", 0)
    line_pct = 100.0 * totals["covered_lines"] / statements if statements else 100.0
    branch_pct = 100.0 * totals.get("covered_branches", 0) / branches if branches else 100.0
    ok = line_pct >= min_lines and branch_pct >= min_branches
    report = (
        f"Linhas/statements: {line_pct:.2f}% (mínimo {min_lines}%)\n"
        f"Branches:          {branch_pct:.2f}% (mínimo {min_branches}%)\n"
        f"Resultado:         {'APROVADO' if ok else 'REPROVADO'}"
    )
    return ok, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default="reports/coverage/coverage.json")
    parser.add_argument("--lines", type=float, default=85.0)
    parser.add_argument("--branches", type=float, default=80.0)
    args = parser.parse_args(argv)

    totals = json.loads(Path(args.file).read_text())["totals"]
    ok, report = evaluate(totals, args.lines, args.branches)
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
