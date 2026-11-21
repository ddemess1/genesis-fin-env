PY ?= python
export PYTHONPATH := src
export PYTHONHASHSEED := 0

.PHONY: check fast test audit viz stress
check:
	$(PY) scripts/check.py
fast:
	$(PY) scripts/check.py --fast
test:
	$(PY) -m pytest -q
audit:
	$(PY) -m audit
viz:
	$(PY) -m viz --episodes episodes/train episodes/dev
stress:
	$(PY) -m fin_env.stress --n 1000
