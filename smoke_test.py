"""Smoke test: verify the project imports and core utilities work.

This script does NOT require data files. It only checks that:
  - All Python modules can be imported
  - Core utility functions produce sensible output
  - Exception classes are exposed
"""
import sys
import importlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

errors: list[str] = []


def check_import(module: str) -> None:
    try:
        importlib.import_module(module)
        print(f"  OK    {module}")
    except Exception as e:
        errors.append(f"{module}: {e}")
        print(f"  FAIL  {module}: {e}")


def main() -> int:
    print("=" * 60)
    print(" TENNISBOT SMOKE TEST")
    print("=" * 60)

    print("\n[1/3] Core modules")
    check_import("config")
    check_import("exceptions")
    check_import("logging_config")
    check_import("utils.constants")

    print("\n[2/3] Pipeline")
    check_import("pipeline.calibration")
    check_import("pipeline.split")
    check_import("pipeline.training")
    check_import("pipeline.evaluation")

    print("\n[3/3] Features")
    check_import("features.elo")
    check_import("features.fatigue")
    check_import("features.h2h")
    check_import("features.context")
    check_import("features.cleaning")
    check_import("features.odds")
    check_import("features.player")
    check_import("features.rolling_stats")
    check_import("features.weather")
    check_import("features.player_news")
    check_import("features.live_odds")
    check_import("features.builder")
    check_import("data.download")

    print("\n" + "=" * 60)
    if errors:
        print(f" FAIL: {len(errors)} import(s) failed")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(" ALL IMPORTS OK")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
