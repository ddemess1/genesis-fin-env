"""JSON-lines driver: one JSON object per line on stdin, one reply per line on stdout.

  {"cmd":"reset","seed":1,"config":{...}}  -> {"observation":..,"info":..}
  {"cmd":"step","action":{...}}            -> {"observation":..,"reward":..,"terminated":..,"truncated":..,"info":..}
  {"cmd":"close"}                          -> {"ok":true}
"""
from __future__ import annotations

import json
import sys

from .env import FinAuditEnv


def main() -> None:
    env = FinAuditEnv()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            cmd = msg.get("cmd")
            if cmd == "reset":
                obs, info = env.reset(msg.get("seed"), msg.get("config"))
                out = {"observation": obs, "info": info}
            elif cmd == "step":
                obs, reward, term, trunc, info = env.step(msg.get("action"))
                out = {"observation": obs, "reward": reward, "terminated": term,
                       "truncated": trunc, "info": info}
            elif cmd == "close":
                env.close()
                out = {"ok": True}
            else:
                out = {"error": "BAD_ACTION"}
        except Exception:
            out = {"error": "BAD_ARGS"}
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()
        if out.get("ok"):
            break


if __name__ == "__main__":
    main()
