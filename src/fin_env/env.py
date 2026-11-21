"""Gymnasium-style JSON environment: reset(seed, config) / step(action).

Isolation: the env reads PUBLIC files only. It holds no seed, no mutation records and no
id map. Ground truth lives in the evaluator (separate process in the default mode).
In closed mode every reward is 0 and info == {"steps_left": n}; evaluation results are
available to the harness only after the episode ends (evaluation_result()).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .evaluator import EvaluatorClient, LocalEvaluator
from .reward import to_json_number
from .tools import ERRORS, PublicTools, action_name, action_params
from decimal import Decimal

MAX_STEPS = 100
DEFAULT_TIME_LIMIT_S = 60.0

TASK = (
    "You are auditing one company for one reporting period. The books may contain hidden errors "
    "of exactly four types: duplicate_invoice, payment_allocation, fx_conversion, period_cutoff. "
    "Many suspicious-looking records are legitimate. Inspect records with list_records, "
    "get_record, get_document and calculator (max 100 steps including submit), then call "
    "submit(findings) with {episode_id, findings:[{type, affected_ids, claimed_amount_minor, "
    "currency, evidence_ids, explanation}]}. A finding counts only if type, the exact set of "
    "affected_ids, amount (exact integer minor units), currency and a sufficient set of "
    "evidence_ids all match. Silence on a clean book is correct. See policy.claims for the "
    "amount and currency rule of each type."
)


class FinAuditEnv:
    def __init__(self, evaluator_mode: str = "process", recorder=None):
        if evaluator_mode not in ("process", "inproc"):
            raise ValueError("evaluator_mode")
        self.evaluator_mode = evaluator_mode
        self.recorder = recorder
        self._tools: PublicTools | None = None
        self._evaluator = None
        self._reset_state()

    # ---- lifecycle -----------------------------------------------------
    def _reset_state(self) -> None:
        self._done = False
        self._terminated = False
        self._truncated = False
        self._steps_used = 0
        self._inspections = 0
        self._closed_mode = False
        self._time_limit = DEFAULT_TIME_LIMIT_S
        self._t0 = 0.0
        self._final: dict | None = None
        self._episode_id = ""
        self._step_no = 0

    def reset(self, seed: int | None = None, config: dict | None = None):
        self.close()
        self._reset_state()
        cfg = dict(config or {})
        mode = cfg.get("mode", "open")
        mode = {"train": "open"}.get(mode, mode)   # the jury adapter calls the open mode "train"
        if mode not in ("open", "closed"):
            raise ValueError("mode must be 'open' (alias 'train') or 'closed'")
        self._closed_mode = mode == "closed"
        self._time_limit = cfg.get("time_limit_s", DEFAULT_TIME_LIMIT_S)
        if isinstance(self._time_limit, bool) or not isinstance(self._time_limit, (int, float)):
            raise ValueError("time_limit_s must be a number")
        public_dir, sealed_dir = self._locate(seed, cfg)
        self._tools = PublicTools(public_dir)
        self._episode_id = self._tools.manifest["episode_id"]
        evaluator_cls = EvaluatorClient if self.evaluator_mode == "process" else LocalEvaluator
        self._evaluator = evaluator_cls(sealed_dir, public_dir)
        self._t0 = time.monotonic()
        obs = {"task": TASK, "manifest": self._tools.manifest, "policy": self._tools.policy,
               "steps_left": MAX_STEPS}
        info = {"steps_left": MAX_STEPS}
        self._record(None, obs, 0.0, False, False)
        return obs, info

    @staticmethod
    def _locate(seed, cfg: dict) -> tuple[Path, Path]:
        if "episode_dir" in cfg:
            root = Path(cfg["episode_dir"])
        elif "episodes_dir" in cfg and "episode_id" in cfg:
            root = Path(cfg["episodes_dir"]) / cfg["episode_id"]
        elif seed is not None and ("gen_config" in cfg or "team_config" in cfg):
            from .generator import fill_defaults, generate_episode  # open mode: generate, then forget the seed
            root = generate_episode(seed, fill_defaults(cfg.get("gen_config", cfg.get("team_config"))), Path(cfg.get("cache_dir", "episodes/_cache")),
                                    split=cfg.get("split", "open"))
        else:
            raise ValueError("config needs episode_dir, or episodes_dir+episode_id, or seed+gen_config")
        return root / "public", root / "sealed"

    def close(self) -> None:
        if self._evaluator is not None:
            self._evaluator.close()
            self._evaluator = None

    # ---- stepping ------------------------------------------------------
    def _steps_left(self) -> int:
        return max(0, MAX_STEPS - self._steps_used)

    def _obs(self, result=None, error=None) -> dict:
        return {"steps_left": self._steps_left(), "result": result,
                "error": None if error is None else {"code": error, "message": ERRORS[error]}}

    def _record(self, action, obs, reward, terminated, truncated) -> None:
        if self.recorder is not None:
            self.recorder({"episode_id": self._episode_id, "step": self._step_no, "action": action,
                           "observation": obs, "reward": reward, "terminated": terminated,
                           "truncated": truncated})
        self._step_no += 1

    def _finish(self, findings, truncated: bool) -> tuple[float, dict]:
        res = self._evaluator.evaluate(findings, self._inspections, truncated)
        self._final = res
        self._done = True
        self._terminated = not truncated
        self._truncated = truncated
        reward = 0.0 if self._closed_mode else to_json_number(Decimal(res["reward"]))
        info = {"steps_left": self._steps_left()}
        if not self._closed_mode:
            info["metrics"] = None if res["structural_error"] else {
                k: res[k] for k in ("tp", "fp", "fn", "precision", "recall", "f1", "inspection_steps")}
        return reward, info

    def step(self, action):
        if self._tools is None:
            raise RuntimeError("call reset() first")
        if self._done:
            obs = self._obs(error="EPISODE_DONE")
            info = {"steps_left": self._steps_left()}
            self._record(action, obs, 0.0, self._terminated, self._truncated)
            return obs, 0.0, self._terminated, self._truncated, info
        if time.monotonic() - self._t0 >= self._time_limit:
            reward, info = self._finish([], True)
            obs = self._obs()
            self._record(action, obs, reward, False, True)
            return obs, reward, False, True, info
        self._steps_used += 1
        if action_name(action) == "submit":
            return self._submit(action)
        self._inspections += 1
        result, err = self._tools.dispatch(action)
        if self._steps_used >= MAX_STEPS:
            reward, info = self._finish([], True)
            obs = self._obs(result, err)
            self._record(action, obs, reward, False, True)
            return obs, reward, False, True, info
        obs = self._obs(result, err)
        info = {"steps_left": self._steps_left()}
        self._record(action, obs, 0.0, False, False)
        return obs, 0.0, False, False, info

    def _submit(self, action):
        params = action_params(action)
        if set(params) != {"findings"}:
            obs = self._obs(error="BAD_ARGS")
            info = {"steps_left": self._steps_left()}
            self._record(action, obs, 0.0, False, False)
            return obs, 0.0, False, False, info
        findings = params["findings"]
        try:
            json.dumps(findings)
        except (TypeError, ValueError):
            findings = "INVALID"
        reward, info = self._finish(findings, False)
        if self._final["structural_error"]:
            obs = self._obs(error="BAD_ARGS")      # bounded structure error; the reward is -1
        else:
            obs = self._obs(result={"accepted": True})
        self._record(action, obs, reward, True, False)
        return obs, reward, True, False, info

    # ---- harness-only --------------------------------------------------
    def evaluation_result(self) -> dict:
        """Evaluator output; only available after the episode ended (harness use)."""
        if not self._done or self._final is None:
            raise RuntimeError("episode not finished")
        return dict(self._final)

    @property
    def inspection_steps(self) -> int:
        return self._inspections
