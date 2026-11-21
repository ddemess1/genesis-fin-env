"""Evaluator: the only component that reads sealed/. Runs outside the agent/env process.

LocalEvaluator is the implementation; EvaluatorClient talks to it over stdin/stdout
(JSON lines) in a separate process, so the env process never holds the ground truth.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

from . import canon, publicio
from .matcher import StructureError, match, validate_structure
from .reward import prf, structural_reward, terminal_reward


class LocalEvaluator:
    def __init__(self, sealed_dir: Path, public_dir: Path):
        self.sealed_dir = Path(sealed_dir)
        truth = canon.read_json(self.sealed_dir / "truth.json")
        self.episode_id = truth["episode_id"]
        self.issues = truth["issues"]
        self.known = publicio.known_ids(publicio.load_raw(public_dir))
        self._done = False

    def evaluate(self, findings, inspection_steps: int, truncated: bool = False) -> dict:
        if self._done:
            raise RuntimeError("already evaluated")
        self._done = True
        structural = None
        pairs: list = []
        try:
            lst = validate_structure(findings, self.episode_id)
        except StructureError as exc:
            structural = str(exc)
            lst = []
        if structural:
            tp, fp, fn = 0, len(self.issues) * 0, len(self.issues)
            reward = structural_reward()
        else:
            m = match(lst, self.issues, self.known)
            tp, fp, fn, pairs = m["tp"], m["fp"], m["fn"], m["matched"]
            reward = terminal_reward(tp, fp, fn, inspection_steps)
        p, r, f1 = prf(tp, fp, fn)
        result = {
            "reward": format(reward, "f"), "tp": tp, "fp": fp, "fn": fn,
            "precision": format(p, "f"), "recall": format(r, "f"), "f1": format(f1, "f"),
            "inspection_steps": inspection_steps, "structural_error": structural,
            "truncated": truncated,
        }
        self._log({**result, "matched": [list(x) for x in pairs]})
        return result

    def _log(self, entry: dict) -> None:
        try:
            with open(self.sealed_dir / "eval_log.jsonl", "a", encoding="utf-8", newline="") as fh:
                fh.write(canon.dumps(entry) + "\n")
        except OSError:
            pass

    def close(self) -> None:
        pass


class EvaluatorClient:
    """Spawns the evaluator in its own process; exchanges JSON lines."""

    def __init__(self, sealed_dir: Path, public_dir: Path):
        src_dir = str(Path(__file__).resolve().parent.parent)
        env = dict(os.environ)
        env["PYTHONPATH"] = src_dir + os.pathsep + env.get("PYTHONPATH", "")
        env["PYTHONHASHSEED"] = "0"
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "fin_env.evaluator", str(sealed_dir), str(public_dir)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", bufsize=1, env=env)
        ready = self._proc.stdout.readline()
        if not ready or json.loads(ready).get("ready") is not True:
            raise RuntimeError("evaluator failed to start")

    def evaluate(self, findings, inspection_steps: int, truncated: bool = False) -> dict:
        msg = {"op": "evaluate", "findings": findings, "inspection_steps": inspection_steps,
               "truncated": truncated}
        self._proc.stdin.write(json.dumps(msg) + "\n")
        self._proc.stdin.flush()
        return json.loads(self._proc.stdout.readline())

    def close(self) -> None:
        if self._proc.poll() is None:
            try:
                self._proc.stdin.write(json.dumps({"op": "close"}) + "\n")
                self._proc.stdin.flush()
            except OSError:
                pass
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        for pipe in (self._proc.stdin, self._proc.stdout):
            try:
                pipe.close()
            except OSError:
                pass


def _serve(sealed_dir: str, public_dir: str) -> None:
    ev = LocalEvaluator(Path(sealed_dir), Path(public_dir))
    sys.stdout.write(json.dumps({"ready": True}) + "\n")
    sys.stdout.flush()
    for line in sys.stdin:
        msg = json.loads(line)
        if msg.get("op") == "close":
            break
        out = ev.evaluate(msg["findings"], msg["inspection_steps"], msg.get("truncated", False))
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    _serve(sys.argv[1], sys.argv[2])
