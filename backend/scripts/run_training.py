"""
Merchant Training Server

Run this file to start the training UI:
    python3 scripts/run_training.py

Then open the URL printed in your terminal.
"""

import sys
from pathlib import Path

# Add backend dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn


def main():
    url = "http://localhost:8000/train"
    print()
    print("=" * 50)
    print("  Luka Merchant Training UI")
    print("=" * 50)
    print()
    print(f"  Open in browser: \033[1;34m{url}\033[0m")
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    print()

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(Path(__file__).resolve().parent.parent)],
    )


if __name__ == "__main__":
    main()
