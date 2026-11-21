"""Run one policy on one episode; record trajectories (fields exactly per the case) with leak checks."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from . import canon, leak
from .env import FinAuditEnv


@dataclass
class RunResult:
    policy: str
    episode_id: str
    reward: float
    terminated: bool
    truncated: bool
    inspection_steps: int
    time_ms: int
    evaluation: dict
    trajectory: list[dict] = field(default_factory=list)


def run_policy(policy, episode_dir: Path, mode: str = "open", seed: int | None = None,
               evaluator_mode: str = "inproc", time_limit_s: float | None = None,
               check_leaks: bool = True) -> RunResult:
    traj: list[dict] = []
    tokens = leak.seed_tokens(seed) if seed is not None else ()

    def rec(line: dict) -> None:
        if check_leaks:
            hits = leak.find_leaks(canon.dumps(line), tokens)
            if hits:
                raise RuntimeError(f"trajectory leak: {hits}")
        traj.append(line)

    env = FinAuditEnv(evaluator_mode=evaluator_mode, recorder=rec)
    cfg = {"episode_dir": str(episode_dir), "mode": mode}
    if time_limit_s is not None:
        cfg["time_limit_s"] = time_limit_s
    t0 = time.monotonic()
    obs, info = env.reset(None, cfg)
    policy.start(obs)
    terminated = truncated = False
    reward = 0.0
    while not (terminated or truncated):
        obs, reward, terminated, truncated, info = env.step(policy.act(obs))
    ev = env.evaluation_result()
    steps = env.inspection_steps
    env.close()
    return RunResult(policy.name, traj[0]["episode_id"], reward, terminated, truncated, steps,
                     int((time.monotonic() - t0) * 1000), ev, traj)


def write_trajectories(path: Path, results: list[RunResult], append: bool = False) -> None:
    lines = "".join(canon.dumps(line) + "\n" for r in results for line in r.trajectory)
    with open(path, "a" if append else "w", encoding="utf-8", newline="") as fh:
        fh.write(lines)
