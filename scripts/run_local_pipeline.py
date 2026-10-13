#!/usr/bin/env python3
"""
BHIV vNEXT MASTERDB-GEO-QUEST-01: Reproducible Local Pipeline Runner
Executes local preparation, cleaning, validation, synthetic profiling, reconciliation, and tests
without fetching live external data or modifying raw source observations.
"""

import os
import sys
import subprocess
import json

def run_command(cmd, desc):
    print("\n" + "=" * 70)
    print(f"STAGE: {desc}")
    print(f"COMMAND: {' '.join(cmd)}")
    print("=" * 70)
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("[STDERR]", result.stderr)
    if result.returncode != 0:
        print(f"[ERROR] Stage failed with exit code {result.returncode}")
        sys.exit(result.returncode)
    return result

def main():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(project_root)

    print("*" * 70)
    print("BHIV vNEXT MASTERDB-GEO-QUEST-01: LOCAL PIPELINE RE-RUN")
    print("Mode: STRICTLY LOCAL (Offline, Non-destructive, Deterministic)")
    print(f"Python Interpreter: {sys.executable}")
    print(f"Python Version: {sys.version.split()[0]}")
    print("*" * 70)

    # 1. Profile Real Aircraft Data
    run_command([sys.executable, "scripts/profile_aircraft.py"], "Statistical Profiling of Raw Snapshot")

    # 2. Profile Synthetic Test Fixtures (Separately)
    run_command([sys.executable, "scripts/profile_fixtures.py"], "Statistical Profiling of Synthetic Test Fixtures")

    # 3. Clean & Normalize Real Aircraft Data
    run_command([sys.executable, "scripts/clean_aircraft.py"], "Deterministic Cleansing & Normalization")

    # 4. Validate Quality Gates on Cleaned Asset
    run_command([sys.executable, "scripts/validate_aircraft.py"], "Automated Quality Gates")

    # 5. Local Reconciliation Audit
    run_command([sys.executable, "scripts/reconcile_records.py"], "Reconciliation Audit & Integration Check")

    # 6. Pytest Executable Test Suite
    run_command([sys.executable, "-m", "pytest", "-v", "tests/test_validation.py"], "Executable Quality & Fixture Test Suite")

    print("\n" + "*" * 70)
    print("ALL LOCAL PIPELINE STAGES COMPLETED SUCCESSFULLY")
    print("*" * 70)

if __name__ == "__main__":
    main()
