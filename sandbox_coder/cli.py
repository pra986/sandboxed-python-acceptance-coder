from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional

from sandbox_coder.engine import SandboxedAcceptanceCoder
from sandbox_coder.models import AcceptanceCase, CodingAssignment


def _default_demo_assignment() -> CodingAssignment:
    return CodingAssignment(
        task_id="demo_fibonacci",
        description="Read integer N from stdin and print the Nth Fibonacci number (0-indexed).",
        code=(
            "import sys\n"
            "raw = sys.stdin.read().strip()\n"
            "n = int(raw) if raw else 10\n"
            "a, b = 0, 1\n"
            "for _ in range(n):\n"
            "    a, b = b, a + b\n"
            "print(a)\n"
        ),
        entry_filename="fibonacci.py",
        timeout_seconds=3.0,
        memory_limit_mb=256,
        acceptance_cases=[
            AcceptanceCase(name="fib_0", stdin="0\n", expected_stdout="0", expected_exit_code=0),
            AcceptanceCase(name="fib_10", stdin="10\n", expected_stdout="55", expected_exit_code=0),
        ],
        proposed_summary="Implemented iterative Fibonacci calculator verified against stdin/stdout cases.",
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sandbox-coder",
        description="Run Python coding assignments in a sandboxed workspace with I/O acceptance checks.",
    )
    parser.add_argument(
        "--eval-file",
        type=Path,
        default=None,
        help="Optional path to a JSON file containing CodingAssignment objects.",
    )
    parser.add_argument("--workspace-dir", type=Path, default=Path("workspace"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    args = parser.parse_args(argv)

    coder = SandboxedAcceptanceCoder(
        workspace_dir=args.workspace_dir,
        output_dir=args.output_dir,
    )

    if args.eval_file is not None:
        raw_items = json.loads(args.eval_file.read_text(encoding="utf-8"))
        assignments = [CodingAssignment.model_validate(item) for item in raw_items]
    else:
        assignments = [_default_demo_assignment()]

    all_passed = True
    for assignment in assignments:
        report = coder.run_assignment(assignment)
        all_passed = all_passed and report.passed
        print(
            json.dumps(
                {
                    "task_id": report.task_id,
                    "passed": report.passed,
                    "exit_code": report.execution.exit_code,
                    "timed_out": report.execution.timed_out,
                    "acceptance_passed": report.acceptance_passed,
                    "summary": report.summary,
                    "report_path": report.report_path,
                },
                indent=2,
            )
        )

    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
