"""Keep the embedded worker's optional AI/PDF dependencies off the startup path."""
import os
from pathlib import Path
import subprocess
import sys


def test_api_and_worker_registry_start_without_loading_job_dependencies():
    # A fresh interpreter avoids unrelated tests preloading optional libraries.
    result = subprocess.run(
        [sys.executable, "-c", """
import sys
from app.main import app
from app.workers.handlers import get_handlers
from sqlalchemy.orm import configure_mappers

assert len(get_handlers()) == 14
assert any(getattr(route, 'path', None) == '/api/health' for route in app.routes)
configure_mappers()
for prefix in ('app.agents.', 'langgraph', 'langchain_core', 'openai', 'pymupdf'):
    assert not any(name.startswith(prefix) for name in sys.modules), prefix
"""],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "MODEL_EXECUTION_ENABLED": "false"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
