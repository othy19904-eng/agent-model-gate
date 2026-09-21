from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path


class AgentUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentUsage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0


@dataclass(frozen=True)
class AgentRun:
    provider: str
    model: str
    returncode: int
    duration_seconds: float
    stdout: str
    stderr: str
    usage: AgentUsage
    total_cost_usd: float | None = None


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def parse_codex_jsonl(stdout: str) -> AgentUsage:
    input_tokens = 0
    cached_input_tokens = 0
    output_tokens = 0
    reasoning_output_tokens = 0

    for raw in stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "turn.completed":
            continue
        usage = event.get("usage") or {}
        input_tokens += int(usage.get("input_tokens") or 0)
        cached_input_tokens += int(usage.get("cached_input_tokens") or 0)
        output_tokens += int(usage.get("output_tokens") or 0)
        reasoning_output_tokens += int(usage.get("reasoning_output_tokens") or 0)

    return AgentUsage(
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        reasoning_output_tokens=reasoning_output_tokens,
    )


def parse_claude_json(stdout: str) -> tuple[AgentUsage, float | None]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return AgentUsage(), None

    usage = payload.get("usage") or {}
    tokens = AgentUsage(
        input_tokens=int(usage.get("input_tokens") or 0),
        cached_input_tokens=int(
            usage.get("cache_read_input_tokens")
            or usage.get("cached_input_tokens")
            or 0
        ),
        output_tokens=int(usage.get("output_tokens") or 0),
        reasoning_output_tokens=int(usage.get("reasoning_output_tokens") or 0),
    )
    cost = payload.get("total_cost_usd")
    return tokens, (float(cost) if cost is not None else None)


def estimate_cost_usd(
    usage: AgentUsage,
    *,
    input_price_per_million: float,
    output_price_per_million: float,
    cached_input_price_per_million: float | None = None,
) -> float:
    if min(input_price_per_million, output_price_per_million) < 0:
        raise ValueError("Token prices cannot be negative")
    cached_price = (
        input_price_per_million
        if cached_input_price_per_million is None
        else cached_input_price_per_million
    )
    if cached_price < 0:
        raise ValueError("Token prices cannot be negative")

    cached = min(usage.cached_input_tokens, usage.input_tokens)
    uncached = max(usage.input_tokens - cached, 0)
    return (
        uncached * input_price_per_million
        + cached * cached_price
        + usage.output_tokens * output_price_per_million
    ) / 1_000_000


def _run_argv(argv: list[str], cwd: Path, timeout_seconds: int) -> tuple[int, float, str, str]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return (
            completed.returncode,
            time.monotonic() - started,
            completed.stdout,
            completed.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        return (
            124,
            time.monotonic() - started,
            _text(exc.stdout),
            _text(exc.stderr) + f"\nTimed out after {timeout_seconds}s",
        )


def run_agent(
    provider: str,
    *,
    model: str,
    prompt: str,
    cwd: Path,
    timeout_seconds: int = 900,
) -> AgentRun:
    provider = provider.lower()
    executable = shutil.which(provider)
    if executable is None:
        raise AgentUnavailableError(
            f"{provider!r} executable was not found on PATH. Install and authenticate the coding-agent CLI first."
        )

    if provider == "codex":
        argv = [
            executable,
            "exec",
            "--json",
            "--ephemeral",
            "--sandbox",
            "workspace-write",
            "-m",
            model,
            prompt,
        ]
    elif provider == "claude":
        argv = [
            executable,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--model",
            model,
            "--allowedTools",
            "Read,Edit,Write,Glob,Grep",
            "--disallowedTools",
            "Bash",
        ]
    else:
        raise ValueError("provider must be 'codex' or 'claude'")

    returncode, duration, stdout, stderr = _run_argv(argv, cwd, timeout_seconds)

    if provider == "codex":
        usage = parse_codex_jsonl(stdout)
        total_cost_usd = None
    else:
        usage, total_cost_usd = parse_claude_json(stdout)

    return AgentRun(
        provider=provider,
        model=model,
        returncode=returncode,
        duration_seconds=duration,
        stdout=stdout,
        stderr=stderr,
        usage=usage,
        total_cost_usd=total_cost_usd,
    )


def _copy_ignore(directory: str, names: list[str]) -> set[str]:
    ignored = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "dist", "build"}
    return ignored.intersection(names)


def replay_agent_once(
    *,
    provider: str,
    repo: str | Path,
    task_id: str,
    category: str,
    baseline_model: str,
    candidate_model: str,
    baseline_cost_usd: float,
    prompt: str,
    verify_command: list[str],
    candidate_cost_usd: float | None = None,
    input_price_per_million: float | None = None,
    output_price_per_million: float | None = None,
    cached_input_price_per_million: float | None = None,
    escalation_cost_usd: float = 0.0,
    rework_cost_usd: float = 0.0,
    timeout_seconds: int = 900,
) -> dict:
    source = Path(repo).resolve()
    if not source.is_dir():
        raise ValueError(f"Repository path does not exist: {source}")
    if min(baseline_cost_usd, escalation_cost_usd, rework_cost_usd) < 0:
        raise ValueError("Costs cannot be negative")

    with tempfile.TemporaryDirectory(prefix="agent-model-gate-agent-") as tmp:
        workdir = Path(tmp) / "repo"
        shutil.copytree(source, workdir, ignore=_copy_ignore)

        agent = run_agent(
            provider,
            model=candidate_model,
            prompt=prompt,
            cwd=workdir,
            timeout_seconds=timeout_seconds,
        )

        if candidate_cost_usd is None:
            if agent.total_cost_usd is not None:
                candidate_cost_usd = agent.total_cost_usd
            elif input_price_per_million is not None and output_price_per_million is not None:
                candidate_cost_usd = estimate_cost_usd(
                    agent.usage,
                    input_price_per_million=input_price_per_million,
                    output_price_per_million=output_price_per_million,
                    cached_input_price_per_million=cached_input_price_per_million,
                )
            else:
                raise ValueError(
                    "Candidate cost is unavailable. Supply --candidate-cost-usd or token prices."
                )

        verifier_returncode = None
        verifier_duration_seconds = None
        verifier_stdout = ""
        verifier_stderr = ""
        verified = False

        if agent.returncode == 0:
            (
                verifier_returncode,
                verifier_duration_seconds,
                verifier_stdout,
                verifier_stderr,
            ) = _run_argv(verify_command, workdir, timeout_seconds)
            verified = verifier_returncode == 0

        return {
            "task_id": task_id,
            "category": category,
            "baseline_model": baseline_model,
            "candidate_model": candidate_model,
            "baseline_cost_usd": baseline_cost_usd,
            "candidate_cost_usd": candidate_cost_usd,
            "candidate_verified": verified,
            "escalation_cost_usd": escalation_cost_usd,
            "rework_cost_usd": rework_cost_usd,
            "agent": {
                **asdict(agent),
                "usage": asdict(agent.usage),
            },
            "verifier": {
                "argv": verify_command,
                "returncode": verifier_returncode,
                "duration_seconds": verifier_duration_seconds,
                "stdout": verifier_stdout,
                "stderr": verifier_stderr,
            },
        }
