"""Launch the project dashboard without writing Streamlit state into the user profile."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
os.environ["STREAMLIT_CONFIG_DIR"] = str(Path(tempfile.gettempdir()) / "naver-brand-dashboard-streamlit")
os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

from streamlit.web.cli import main  # noqa: E402


sys.argv = [
    "streamlit",
    "run",
    str(ROOT / "app.py"),
    "--server.headless=true",
    "--server.port=8501",
    "--browser.gatherUsageStats=false",
]
main()
