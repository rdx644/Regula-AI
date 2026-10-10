"""Migrate and start a single-instance Render API without shell quoting."""

import os
import subprocess
import sys


def main() -> None:
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    # Replace this process so Uvicorn receives Render's shutdown signals.
    os.execv(sys.executable, [
        sys.executable,
        "-m", "uvicorn", "app.main:app",
        "--host", "0.0.0.0",
        "--port", os.environ.get("PORT") or "10000",
        "--no-proxy-headers",
    ])


if __name__ == "__main__":
    main()
