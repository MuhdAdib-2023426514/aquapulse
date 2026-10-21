#!/usr/bin/env bash
set -euo pipefail

export PATH="/home/muhammad_adib/swimming_pool_monitoring_system/.venv/bin:$HOME/.local/bin:$PATH"
cd /home/muhammad_adib/swimming_pool_monitoring_system

if [ -x ".venv/bin/python" ]; then
    RUNNER=""
else
    RUNNER="uv run"
fi

echo "=== [1/4] Checking Python & uv environment ==="
$RUNNER python --version

echo "=== [2/4] Running Ruff Linter ==="
if $RUNNER ruff --version >/dev/null 2>&1; then
    $RUNNER ruff check .
else
    echo "Ruff not installed yet (skipping until Milestone 1 dependencies are synced)."
fi

echo "=== [3/4] Running Pytest Suite ==="
if $RUNNER pytest --version >/dev/null 2>&1; then
    if [ -d "tests" ] && [ -n "$(ls -A tests/*.py 2>/dev/null || true)" ]; then
        $RUNNER pytest -v
    else
        echo "No test files in tests/ yet."
    fi
else
    echo "Pytest not installed yet (skipping until Milestone 1 dependencies are synced)."
fi

echo "=== [4/4] Checking Streamlit App Syntax ==="
if [ -f "app/streamlit_app.py" ]; then
    $RUNNER python -m py_compile app/streamlit_app.py
    echo "app/streamlit_app.py syntax OK"
fi

echo "✅ AquaPulse verification checks passed!"
