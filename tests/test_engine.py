from pathlib import Path

import pytest

from sandbox_coder.engine import SandboxedAcceptanceCoder
from sandbox_coder.models import AcceptanceCase, CodingAssignment


def test_infinite_loop_killed_by_timeout(tmp_path: Path) -> None:
    coder = SandboxedAcceptanceCoder(
        workspace_dir=tmp_path / "workspace",
        output_dir=tmp_path / "output",
    )
    assignment = CodingAssignment(
        task_id="infinite_loop_case",
        description="Should be terminated by subprocess timeout.",
        code="while True:\n    pass\n",
        entry_filename="loop.py",
        timeout_seconds=0.5,
        proposed_summary="Loop completed cleanly.",
    )

    report = coder.run_assignment(assignment)

    assert report.passed is False
    assert report.execution.timed_out is True
    assert report.execution.exit_code != 0
    assert "Loop completed cleanly." not in report.summary
    assert "rejected" in report.summary.lower()


def test_runtime_and_syntax_error_preserved_in_solution_report(tmp_path: Path) -> None:
    coder = SandboxedAcceptanceCoder(
        workspace_dir=tmp_path / "workspace",
        output_dir=tmp_path / "output",
    )
    assignment = CodingAssignment(
        task_id="runtime_error_case",
        description="Raises ZeroDivisionError.",
        code="print(1 / 0)\n",
        entry_filename="crash.py",
        timeout_seconds=2.0,
        proposed_summary="Everything worked fine.",
    )

    report = coder.run_assignment(assignment)
    report_text = Path(report.report_path).read_text(encoding="utf-8")

    assert report.passed is False
    assert report.execution.exit_code != 0
    assert "ZeroDivisionError" in report.execution.stderr
    assert f"`{report.execution.exit_code}`" in report_text
    assert "ZeroDivisionError" in report_text


def test_fluent_summary_rejected_on_nonzero_exit_code(tmp_path: Path) -> None:
    coder = SandboxedAcceptanceCoder(
        workspace_dir=tmp_path / "workspace",
        output_dir=tmp_path / "output",
    )
    assignment = CodingAssignment(
        task_id="syntax_error_case",
        description="Invalid syntax.",
        code="def broken(:\n    pass\n",
        entry_filename="broken.py",
        timeout_seconds=2.0,
        proposed_summary="All unit tests and checks succeeded without errors.",
    )

    report = coder.run_assignment(assignment)

    assert report.execution.exit_code != 0
    assert report.summary != assignment.proposed_summary
    assert "rejected" in report.summary.lower()


def test_independent_acceptance_io_check_verifies_output(tmp_path: Path) -> None:
    coder = SandboxedAcceptanceCoder(
        workspace_dir=tmp_path / "workspace",
        output_dir=tmp_path / "output",
    )
    passing_assignment = CodingAssignment(
        task_id="double_input",
        description="Reads integer from stdin and prints 2 * n.",
        code="import sys\nraw = sys.stdin.read().strip()\nprint(int(raw) * 2 if raw else 0)\n",
        entry_filename="double.py",
        timeout_seconds=2.0,
        acceptance_cases=[
            AcceptanceCase(name="case_7", stdin="7\n", expected_stdout="14", expected_exit_code=0),
            AcceptanceCase(name="case_0", stdin="0\n", expected_stdout="0", expected_exit_code=0),
        ],
        proposed_summary="Doubles stdin integer accurately.",
    )

    pass_report = coder.run_assignment(passing_assignment)
    assert pass_report.passed is True
    assert pass_report.acceptance_passed is True
    assert pass_report.summary == "Doubles stdin integer accurately."

    failing_assignment = passing_assignment.model_copy(
        update={
            "task_id": "double_input_mismatch",
            "acceptance_cases": [
                AcceptanceCase(name="wrong_expected", stdin="7\n", expected_stdout="99", expected_exit_code=0)
            ],
        }
    )

    fail_report = coder.run_assignment(failing_assignment)
    assert fail_report.passed is False
    assert fail_report.acceptance_passed is False


def test_workspace_path_traversal_blocked(tmp_path: Path) -> None:
    coder = SandboxedAcceptanceCoder(
        workspace_dir=tmp_path / "workspace",
        output_dir=tmp_path / "output",
    )
    assignment = CodingAssignment(
        task_id="escape_attempt",
        description="Attempt to write outside workspace.",
        code="print('escape')\n",
        entry_filename="../escape.py",
    )

    with pytest.raises(ValueError):
        coder.run_assignment(assignment)
