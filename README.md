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
python scripts/check_experimental_api_policy.py
python scripts/check_package_names.py
python scripts/check_runtime_compatibility.py
python scripts/check_secrets.py
python scripts/check_version_policy.py
python scripts/check_spec_module.py
pytest tests/unit
pytest
python -m build
python scripts/build_all.py
```

- [R1 Scope](spec/r1-scope.json)
- [Task, Message, and Artifact boundaries](docs/adr/0001-task-message-artifact-boundaries.md)
- [Direct injection without registries](docs/adr/0002-direct-injection-without-registry.md)
- [Default JSON and system HTTP](docs/adr/0003-default-json-and-system-http.md)
- [R1 text unary scope](docs/adr/0004-r1-text-unary-only.md)
- [Experimental API policy](spec/compatibility/experimental-api-policy.json)
- [Package names](spec/compatibility/package-names.json)
- [Runtime compatibility](spec/compatibility/runtime-matrix.json)
- [Test secret placeholders](spec/compatibility/test-secret-placeholders.json)
- [Version policy](spec/compatibility/version-policy.json)
