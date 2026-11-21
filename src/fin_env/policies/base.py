"""Policy adapter protocol: start(obs) once, then act(obs) -> action dict until the episode ends."""
from __future__ import annotations


class Policy:
    name = "base"

    def start(self, obs: dict) -> None:
        self.manifest = obs["manifest"]
        self.queue: list[dict] = []

    def act(self, obs: dict) -> dict:
        raise NotImplementedError


class Scripted(Policy):
    """A policy that plans a list of actions up front (after seeing the first observation)."""

    def plan(self, obs: dict) -> list[dict]:
        raise NotImplementedError

    def start(self, obs: dict) -> None:
        super().start(obs)
        self.queue = self.plan(obs)

    def act(self, obs: dict) -> dict:
        return self.queue.pop(0)


def submit(findings: list[dict], episode_id: str) -> dict:
    return {"action": "submit", "findings": {"episode_id": episode_id, "findings": findings}}
