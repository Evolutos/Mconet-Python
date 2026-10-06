# Mconet Python SDK

当前处于 S0 工程基线，尚未提供模型交互 API。需要 Python 3.11+。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

```bash
ruff format --check .
ruff check .
pyright
python scripts/check_import_boundaries.py
python scripts/check_api_compatibility.py
python scripts/check_spec_module.py
pytest tests/unit
pytest
python scripts/build_all.py
```

- [R1 Scope](spec/r1-scope.json)
