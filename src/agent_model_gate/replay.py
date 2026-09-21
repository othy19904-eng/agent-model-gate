from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    command: str
    returncode: int
    duration_seconds: float
    stdout: str
    stderr: str


def _run(command: str, cwd: Path, timeout_seconds: int) -> CommandResult:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            shlex.split(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return CommandResult(
            command=command,
            returncode=completed.returncode,
            duration_seconds=time.monotonic() - started,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=command,
            returncode=124,
            duration_seconds=time.monotonic() - started,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + f"\nTimed out after {timeout_seconds}s",
        )


def _ignore_copy(directory: str, names: list[str]) -> set[str]:
    ignored = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "dist", "build"}
    return ignored.intersection(names)


def replay_once(
    *,
    repo: str | Path,
    task_id: str,
    category: str,
    baseline_model: str,
    candidate_model: str,
    baseline_cost_usd: float,
    candidate_cost_usd: float,
    candidate_command: str,
    verify_command: str,
    escalation_cost_usd: float = 0.0,
    rework_cost_usd: float = 0.0,
    timeout_seconds: int = 900,
) -> dict:
    source = Path(repo).resolve()
    if not source.is_dir():
        raise ValueError(f"Repository path does not exist: {source}")
    if baseline_cost_usd < 0 or candidate_cost_usd < 0 or escalation_cost_usd < 0 or rework_cost_usd < 0:
        raise ValueError("Costs cannot be negative")

    with tempfile.TemporaryDirectory(prefix="agent-model-gate-") as tmp:
        workdir = Path(tmp) / "repo"
        shutil.copytree(source, workdir, ignore=_ignore_copy)

        candidate = _run(candidate_command, workdir, timeout_seconds)
        verifier = None
        verified = False
        if candidate.returncode == 0:
            verifier = _run(verify_command, workdir, timeout_seconds)
            verified = verifier.returncode == 0

        row = {
            "task_id": task_id,
            "category": category,
            "baseline_model": baseline_model,
            "candidate_model": candidate_model,
            "baseline_cost_usd": baseline_cost_usd,
            "candidate_cost_usd": candidate_cost_usd,
            "candidate_verified": verified,
            "escalation_cost_usd": escalation_cost_usd,
            "rework_cost_usd": rework_cost_usd,
            "candidate_command": asdict(candidate),
            "verifier_command": asdict(verifier) if verifier else None,
        }
        return row


def append_jsonl(path: str | Path, row: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
