BOOTSTRAP_ZERO
1) scripts/bootstrap_psy_observer_env.py creates .venv_psy_web — PASS (venv created)
2) pip install -r requirements-observer.txt — FAIL in this environment (ProxyError to PyPI)
3) Offline acceptance used development Observer interpreter via PSY_OBSERVER_PYTHON with PYTHONPATH=<clean package only>
True first-run pip bootstrap requires network on the target machine.
