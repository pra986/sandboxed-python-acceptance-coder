"""Pydantic data contracts for the sandboxed Python acceptance coder."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class AcceptanceCase(BaseModel):
    """Independent I/O acceptance assertion for a coding assignment."""

    name: str
    stdin: str = ""
    expected_stdout: Optional[str] = None
    expected_substrings: List[str] = Field(default_factory=list)
    expected_exit_code: int = 0


class CodingAssignment(BaseModel):
    """Input specification for a sandboxed Python coding task."""

    task_id: str
    description: str
    code: str
    entry_filename: str = "solution.py"
    timeout_seconds: float = Field(default=5.0, gt=0.0, le=60.0)
    memory_limit_mb: int = Field(default=256, ge=32, le=2048)
    acceptance_cases: List[AcceptanceCase] = Field(default_factory=list)
    proposed_summary: str = ""


class SandboxExecutionResult(BaseModel):
    """Verbatim result captured from isolated subprocess execution."""

    command: List[str]
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    duration_seconds: float = 0.0


class SolutionReport(BaseModel):
    """Final verified report emitted to output/solution.md."""

    task_id: str
    passed: bool
    execution: SandboxExecutionResult
    acceptance_passed: bool
    acceptance_details: List[str] = Field(default_factory=list)
    summary: str
    summary_rejected: bool = False
    report_path: str
