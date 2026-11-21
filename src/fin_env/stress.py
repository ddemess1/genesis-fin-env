"""Mass robustness run: N random seeds with randomly sampled configs; every episode must pass I01-I17.

`python -m fin_env.stress --n 1000 --out reports/stress.json`
"""
from __future__ import annotations

import argparse
import collections
import sys
import tempfile
import time
from pathlib import Path

from . import canon
from .books.clean import ERROR_KINDS, TWIN_KINDS, GenerationError, _nominal_micro
from .money import EXP
from .generator import generate_episode
from .rng import DetRng
from .selfcheck.runner import EpisodeInvalid

MONTHS = ("2026-01-01", "2026-03-01", "2026-04-01", "2026-05-01", "2026-06-01", "2026-07-01", "2026-08-01",
          "2026-09-01", "2026-10-01", "2026-11-01", "2026-12-01")
TZS = ("+05:00", "+06:00", "-04:00", "+00:00", "+01:00", "+03:00", "-05:00", "+09:00", "+10:00", "-08:00")


def sample_config(seed: int) -> dict:
    r = DetRng(seed, ("stress-config",))
    def pool_for(b):
        # currencies worth < 1 base minor unit per minor unit make partial allocations unrecoverable
        return [c for c in ("EUR", "JPY", "KWD", "KZT", "USD")
                if c != b and _nominal_micro(c, b) * 10 ** (EXP[b] - EXP[c]) >= 1_000_000]
    base = r.choice(["KZT", "KZT", "USD", "EUR"])
    pool = pool_for(base)
    if not pool:
        base, pool = "KZT", pool_for("KZT")
    cfg: dict = {"base_currency": base, "currencies": sorted(r.pick(pool, r.randint(1, 3))),
                 "period_start": r.choice(list(MONTHS)), "timezone": r.choice(list(TZS)),
                 "n_invoices": r.randint(30, 90), "n_misc": r.randint(40, 200), "alt_tz_pct": r.randint(0, 40)}
    errors = {k: r.choice([0, 0, 0, 1, 1, 2]) for k in ERROR_KINDS}
    inter = {"INT1": r.choice([0, 0, 1, 1, 2]), "INT2": r.choice([0, 0, 1, 1])}
    while sum(errors.values()) + 2 * sum(inter.values()) > 12:
        errors[r.choice(list(ERROR_KINDS))] = 0
    twins = {k: r.choice([0, 0, 1]) for k in TWIN_KINDS}
    if not any(errors.values()) and not any(inter.values()):
        for k in ("TWIN_SUBSCRIPTION", "TWIN_REFUND", "TWIN_BOUNDARY_TZ"):
            twins[k] = max(1, twins[k])
    cfg["errors"], cfg["interactions"], cfg["twins"] = ({k: v for k, v in d.items() if v}
                                                         for d in (errors, inter, twins))
    return cfg


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m fin_env.stress")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--first-seed", type=int, default=100000)
    ap.add_argument("--out", type=Path, default=Path("reports/stress.json"))
    a = ap.parse_args(argv)
    fails: collections.Counter = collections.Counter()
    examples: dict = {}
    times = []
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="fin-stress-") as d:
        for seed in range(a.first_seed, a.first_seed + a.n):
            t1 = time.monotonic()
            cfg = sample_config(seed)
            try:
                generate_episode(seed, cfg, Path(d))
            except EpisodeInvalid as exc:
                for res in exc.report.results:
                    if not res.passed:
                        fails[res.check_id] += 1
                        examples.setdefault(res.check_id, {"seed": seed, "detail": res.detail[:300]})
            except GenerationError as exc:
                fails["GenerationError:" + str(exc)[:60]] += 1
                examples.setdefault("GenerationError:" + str(exc)[:60], {"seed": seed, "config": cfg})
            except Exception as exc:  # noqa: BLE001
                key = "Exception:" + type(exc).__name__
                fails[key] += 1
                examples.setdefault(key, {"seed": seed, "detail": str(exc)[:300]})
            times.append(time.monotonic() - t1)
    total = time.monotonic() - t0
    times.sort()
    report = {"episodes": a.n, "first_seed": a.first_seed, "failures": dict(fails), "examples": examples,
              "total_s": round(total, 1), "mean_ms": int(1000 * total / a.n), "p95_ms": int(1000 * times[int(0.95 * len(times))])}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    canon.write_json(a.out, report)
    print(f"{a.n} episodes in {report['total_s']} s (mean {report['mean_ms']} ms, p95 {report['p95_ms']} ms); "
          f"failures: {dict(fails) or 'none'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
