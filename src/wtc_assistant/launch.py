"""Installed local launcher; no shell interpolation and no external services."""
import os
from pathlib import Path
import sys

def main():
    # Use an absolute-import entry point so this also works outside the repo cwd.
    entry = Path(__file__).with_name('entrypoint.py')
    os.environ.setdefault('STREAMLIT_BROWSER_GATHER_USAGE_STATS', 'false')
    os.environ.setdefault('WTC_STORAGE_MODE', 'local')
    from streamlit.web import cli
    sys.argv = ['streamlit', 'run', str(entry), '--server.address=127.0.0.1',
                '--server.headless=true', '--server.fileWatcherType=none', *sys.argv[1:]]
    cli.main()
