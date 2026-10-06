# Mconet Python SDK

当前工程尚未提供模型交互 API。需要 Python 3.11+。

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

- [Initial release scope](spec/r1-scope.json)
- [Experimental API policy](spec/compatibility/experimental-api-policy.json)
- [Package names](spec/compatibility/package-names.json)
- [Initial OpenAI-compatible endpoint](spec/compatibility/r1-openai-endpoint.json)
- [Initial OpenAI-compatible protocol](spec/compatibility/r1-openai-protocol.json)
- [Runtime compatibility](spec/compatibility/runtime-matrix.json)
- [Test log policy](spec/compatibility/test-log-policy.json)
- [Test secret placeholders](spec/compatibility/test-secret-placeholders.json)
- [Version policy](spec/compatibility/version-policy.json)
