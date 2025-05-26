# Python 3.9 Compatibility Issues Requiring Manual Attention
The following issues cannot be automated and require manual fixes:

1. Function signature mismatches between utils/cost_tracker.py and bin/budget_audit.py that are too complex for regex
2. Complex type annotation issues that require context-aware parsing
3. Inconsistent variable naming patterns that can't be safely automated
4. Missing library stubs (install via pip: types-requests, types-pytz, etc.)
5. Import cycles that need manual restructuring

Files with potential issues:
- ./.venv/lib/python3.11/site-packages/_pytest/python_api.py
- ./.venv/lib/python3.11/site-packages/_pytest/recwarn.py
- ./.venv/lib/python3.11/site-packages/setuptools/dist.py
- ./venv/lib/python3.9/site-packages/_pytest/python_api.py
- ./venv/lib/python3.9/site-packages/_pytest/recwarn.py
- ./venv/lib/python3.9/site-packages/jinja2/filters.py
- ./venv/lib/python3.9/site-packages/lxml/html/formfill.py
- ./venv/lib/python3.9/site-packages/mypy/message_registry.py
- ./venv/lib/python3.9/site-packages/mypy/messages.py
- ./venv/lib/python3.9/site-packages/mypy/semanal.py
- ./venv/lib/python3.9/site-packages/mypy/semanal_enum.py
- ./venv/lib/python3.9/site-packages/mypy/semanal_typeddict.py
- ./venv/lib/python3.9/site-packages/mypy/test/meta/test_update_data.py
