"""
================================================================
Run_All_Fixed.py — Automation driver
================================================================
Runs Step6_DataProcessing_FIXED.py then Step7_ML_Pipeline_FIXED.py
in sequence. Stops immediately if Step 6 fails (no point running
Step 7 on stale/broken context data).

Usage:
    python Run_All_Fixed.py
================================================================
"""

import subprocess
import sys
from datetime import datetime


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def run(script_name):
    log(f"Running {script_name}...")
    result = subprocess.run([sys.executable, script_name])
    if result.returncode != 0:
        log(f"{script_name} FAILED (exit code {result.returncode}). Stopping.")
        sys.exit(result.returncode)
    log(f"{script_name} completed successfully.")


if __name__ == "__main__":
    run("Step6_DataProcessing_FIXED.py")
    run("Step7_ML_Pipeline_FIXED.py")
    log("All steps complete.")
