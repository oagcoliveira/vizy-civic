"""
Cron entry point for the weekly email digest.

Run every Friday via cron or Railway scheduler:
    python -m digest.digest_weekly

This script is a thin wrapper that calls backend/digest.py with --send.
It must be run from the repo root so it can find backend/.
"""

import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent.parent / "backend"


def main():
    print("[digest_weekly] Starting weekly email digest...")
    result = subprocess.run(
        [sys.executable, "digest.py", "--send"],
        cwd=str(BACKEND_DIR),
    )
    if result.returncode != 0:
        print("[digest_weekly] digest.py exited with non-zero status", file=sys.stderr)
        sys.exit(result.returncode)
    print("[digest_weekly] Done.")


if __name__ == "__main__":
    main()
