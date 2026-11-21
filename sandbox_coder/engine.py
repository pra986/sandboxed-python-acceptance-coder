from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional

from sandbox_coder.models import (
    AcceptanceCase,
    CodingAssignment,
    SandboxExecutionResult,
    SolutionReport,
)


def _decode_output(data: str | bytes | None) -> str:
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return data


def _build_posix_limits(timeout_seconds: float, memory_limit_mb: int) -> Optional[Callable[[], None]]:
    if os.name != "posix":
        return None
    import resource

    cpu_seconds = max(1, int(timeout_seconds) + 1)
    mem_bytes = memory_limit_mb * 1024 * 1024

    def _apply_limits() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        try:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except (ValueError, OSError):
            pass

    return _apply_limits


class SandboxedAcceptanceCoder:
    """Executes Python assignments in an isolated workspace with independent I/O checks."""

    def __init__(
        self,
        workspace_dir: str | Path = "workspace",
        output_dir: str | Path = "output",
    ) -> None:
        self.workspace_dir = Path(workspace_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_workspace_path(self, relative_filename: str) -> Path:
        candidate = Path(relative_filename)
        if candidate.is_absolute():
            raise ValueError(f"Absolute paths are forbidden outside workspace: {relative_filename}")
        resolved = (self.workspace_dir / candidate).resolve()
        if not resolved.is_relative_to(self.workspace_dir):
            raise ValueError(f"Path traversal outside workspace is forbidden: {relative_filename}")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    def _run_subprocess(
        self,
        script_path: Path,
        stdin_data: str,
        timeout_seconds: float,
        memory_limit_mb: int,
    ) -> SandboxExecutionResult:
        cmd = [sys.executable, str(script_path)]
        preexec_fn = _build_posix_limits(timeout_seconds, memory_limit_mb)
        start = time.monotonic()
        try:
            completed = subprocess.run(
                cmd,
                cwd=str(self.workspace_dir),
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                preexec_fn=preexec_fn,
            )
            duration = round(time.monotonic() - start, 4)
            return SandboxExecutionResult(
                command=cmd,
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                timed_out=False,
                duration_seconds=duration,
            )
        except subprocess.TimeoutExpired as exc:
            duration = round(time.monotonic() - start, 4)
            stderr_text = _decode_output(exc.stderr)
            timeout_note = f"Process killed after exceeding hard timeout of {timeout_seconds}s."
            combined_stderr = f"{stderr_text}\n{timeout_note}".strip()
            return SandboxExecutionResult(
                command=cmd,
                exit_code=-1,
                stdout=_decode_output(exc.stdout),
                stderr=combined_stderr,
                timed_out=True,
                duration_seconds=duration,
            )

    def _evaluate_acceptance(
        self,
        script_path: Path,
        cases: list[AcceptanceCase],
        timeout_seconds: float,
        memory_limit_mb: int,
    ) -> tuple[bool, list[str]]:
        if not cases:
            return True, ["No independent acceptance cases configured."]

        all_passed = True
        details: list[str] = []

        for case in cases:
            result = self._run_subprocess(
                script_path=script_path,
                stdin_data=case.stdin,
                timeout_seconds=timeout_seconds,
                memory_limit_mb=memory_limit_mb,
            )
            failures: list[str] = []
            if result.timed_out:
                failures.append("timed out")
            if result.exit_code != case.expected_exit_code:
                failures.append(f"exit_code={result.exit_code} (expected {case.expected_exit_code})")
            if case.expected_stdout is not None and result.stdout.strip() != case.expected_stdout.strip():
                failures.append(
                    f"stdout={result.stdout.strip()!r} (expected {case.expected_stdout.strip()!r})"
                )
            for substr in case.expected_substrings:
                if substr not in result.stdout:
                    failures.append(f"missing substring {substr!r}")

            if failures:
                all_passed = False
                details.append(f"FAIL [{case.name}]: " + "; ".join(failures))
            else:
                details.append(f"PASS [{case.name}]")

        return all_passed, details

    def _build_summary(
        self,
        assignment: CodingAssignment,
        execution: SandboxExecutionResult,
        acceptance_passed: bool,
    ) -> str:
        if execution.timed_out or execution.exit_code != 0:
            return (
                f"Execution failed (exit_code={execution.exit_code}, timed_out={execution.timed_out}). "
                "Fluent summary rejected; inspect verbatim stdout/stderr in output/solution.md."
            )
        if not acceptance_passed:
            return (
                "Primary execution exited with code 0, but independent acceptance assertions failed. "
                "Proposed summary rejected."
            )
        if assignment.proposed_summary.strip():
            return assignment.proposed_summary.strip()
        return f"Task {assignment.task_id} passed execution and all acceptance checks."

    def _write_report(
        self,
        assignment: CodingAssignment,
        execution: SandboxExecutionResult,
        acceptance_passed: bool,
        acceptance_details: list[str],
        summary: str,
        passed: bool,
    ) -> Path:
        report_path = self.output_dir / "solution.md"
        acceptance_lines = "\n".join(f"- {line}" for line in acceptance_details)
        content = (
            f"# Solution Report: {assignment.task_id}\n\n"
            f"- **Overall Passed**: `{passed}`\n"
            f"- **Exit Code**: `{execution.exit_code}`\n"
            f"- **Timed Out**: `{execution.timed_out}`\n"
            f"- **Duration (s)**: `{execution.duration_seconds}`\n"
            f"- **Acceptance Passed**: `{acceptance_passed}`\n\n"
            f"## Summary\n\n{summary}\n\n"
            f"## Acceptance Checks\n\n{acceptance_lines}\n\n"
            f"## Verbatim stdout\n\n```text\n{execution.stdout}\n```\n\n"
            f"## Verbatim stderr\n\n```text\n{execution.stderr}\n```\n"
        )
        report_path.write_text(content, encoding="utf-8")
        return report_path

    def run_assignment(self, assignment: CodingAssignment) -> SolutionReport:
        script_path = self._resolve_workspace_path(assignment.entry_filename)
        script_path.write_text(assignment.code, encoding="utf-8")

        execution = self._run_subprocess(
            script_path=script_path,
            stdin_data="",
            timeout_seconds=assignment.timeout_seconds,
            memory_limit_mb=assignment.memory_limit_mb,
        )

        if execution.exit_code == 0 and not execution.timed_out:
            acceptance_passed, acceptance_details = self._evaluate_acceptance(
                script_path=script_path,
                cases=assignment.acceptance_cases,
                timeout_seconds=assignment.timeout_seconds,
                memory_limit_mb=assignment.memory_limit_mb,
            )
        else:
            acceptance_passed = False
            acceptance_details = [
                f"SKIPPED: primary execution failed with exit_code={execution.exit_code}, timed_out={execution.timed_out}."
            ]

        passed = (execution.exit_code == 0) and (not execution.timed_out) and acceptance_passed
        summary = self._build_summary(assignment, execution, acceptance_passed)
        report_path = self._write_report(
            assignment=assignment,
            execution=execution,
            acceptance_passed=acceptance_passed,
            acceptance_details=acceptance_details,
            summary=summary,
            passed=passed,
        )

        return SolutionReport(
            task_id=assignment.task_id,
            passed=passed,
            execution=execution,
            acceptance_passed=acceptance_passed,
            acceptance_details=acceptance_details,
            summary=summary,
            report_path=str(report_path),
        )
