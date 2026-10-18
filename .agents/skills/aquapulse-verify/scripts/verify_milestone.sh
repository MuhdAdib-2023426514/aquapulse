#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"
cd /home/muhammad_adib/swimming_pool_monitoring_system

echo "=== [1/4] Checking Python & uv environment ==="
uv run python --version

echo "=== [2/4] Running Ruff Linter ==="
if uv run ruff --version >/dev/null 2>&1; then
    uv run ruff check .
else
    echo "Ruff not installed yet (skipping until Milestone 1 dependencies are synced)."
fi

echo "=== [3/4] Running Pytest Suite ==="
if uv run pytest --version >/dev/null 2>&1; then
    if [ -d "tests" ] && [ -n "$(ls -A tests/*.py 2>/dev/null || true)" ]; then
        uv run pytest -v
    else
        echo "No test files in tests/ yet."
    fi
else
    echo "Pytest not installed yet (skipping until Milestone 1 dependencies are synced)."
fi

echo "=== [4/4] Checking Streamlit App Syntax ==="
if [ -f "app/streamlit_app.py" ]; then
    uv run python -m py_compile app/streamlit_app.py
    echo "app/streamlit_app.py syntax OK"
fi

echo "✅ AquaPulse verification checks passed!"
