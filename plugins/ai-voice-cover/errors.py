"""Custom exceptions for the voice cover pipeline."""

from __future__ import annotations


class VoiceCoverError(Exception):
    """Base error for the plugin."""


class ToolNotFoundError(VoiceCoverError):
    """A required external tool is not installed or not found on PATH."""


class StepError(VoiceCoverError):
    """A pipeline step failed."""

    def __init__(
        self, step_name: str, command: list[str], returncode: int, stderr: str
    ) -> None:
        self.step_name = step_name
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(
            f"Step '{step_name}' failed (exit {returncode}): {stderr[:500]}"
        )


class PlannerError(VoiceCoverError):
    """Style not found or planner configuration issue."""
