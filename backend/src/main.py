"""TennisBot - AI Tennis Match Prediction Pipeline.

Main entry point for the pipeline.

Usage:
    python main.py download --tour atp
    python main.py features --tour atp
    python main.py train --tour atp
    python main.py train --tour atp --use-odds
    python main.py refresh --tour both
    python main.py settle --tour both
    python main.py all --tour atp
"""
from __future__ import annotations

import argparse
import time
import traceback

from logging_config import get_logger

logger = get_logger(__name__)


def cmd_download(args: argparse.Namespace) -> None:
    """Download raw CSV data from the ATP/WTA mirror + tennis-data odds."""
    from data.download import download_all
    tours = ["atp", "wta"] if args.tour == "both" else [args.tour]
    for tour in tours:
        download_all(tour, args.start, args.end, args.overwrite)


def cmd_features(args: argparse.Namespace):
    """Run the full feature engineering pipeline."""
    from features.builder import build_features
    return build_features(
        tour=args.tour,
        start_year=args.start,
        end_year=args.end,
        odds_path=args.odds,
        stats_from_year=args.stats_from,
    )


def cmd_train(args: argparse.Namespace):
    """Train the stacking ensemble model."""
    from pipeline.training import train_pipeline
    return train_pipeline(
        tour=args.tour,
        n_optuna_trials=args.optuna_trials,
        start_year=args.start_year,
        end_year=args.end_year,
        use_odds=getattr(args, "use_odds", False),
    )


def cmd_settle(args: argparse.Namespace) -> None:
    """Settle open track predictions against feature dataset outcomes."""
    from pipeline.track import settle_predictions

    tours = ["atp", "wta"] if args.tour == "both" else [args.tour]
    for tour in tours:
        result = settle_predictions(tour)
        logger.info(f"[{tour.upper()}] settle → {result}")


def cmd_refresh(args: argparse.Namespace) -> None:
    """Weekly refresh: download → features → retrain both variants → settle.

    Flags:
      --settle-only   only settle track (no download/train)
      --skip-train    download + features + settle, no retrain
      --optuna-trials Optuna budget per model (default 20 for weekly speed)
    """
    import config
    from data.download import download_all
    from features.builder import build_features
    from pipeline.training import train_pipeline
    from pipeline.track import settle_predictions

    tours = ["atp", "wta"] if args.tour == "both" else [args.tour]
    this_year = time.localtime().tm_year
    errors: list[str] = []

    logger.info("\n" + "#" * 70)
    logger.info("  WEEKLY REFRESH")
    logger.info(f"  tours={tours}  settle_only={args.settle_only}  "
                f"skip_train={args.skip_train}  optuna={args.optuna_trials}")
    logger.info("#" * 70)

    if args.settle_only:
        for tour in tours:
            try:
                result = settle_predictions(tour)
                logger.info(f"[{tour.upper()}] settle → {result}")
            except Exception as exc:
                msg = f"[{tour}] settle failed: {exc}"
                logger.error(msg)
                errors.append(msg)
        if errors:
            raise SystemExit(f"Refresh settle-only finished with errors: {errors}")
        logger.info("\n>>> SETTLE-ONLY COMPLETE <<<")
        return

    for tour in tours:
        try:
            logger.info(f"\n>>> [{tour.upper()}] downloading match history <<<")
            download_all(
                tour,
                start_year=config.MATCH_YEAR_START,
                end_year=this_year + 1,
                overwrite=True,
            )

            logger.info(f"\n>>> [{tour.upper()}] rebuilding features <<<")
            build_features(tour=tour)

            if not args.skip_train:
                logger.info(f"\n>>> [{tour.upper()}] retraining pure-stats + market-aware <<<")
                train_pipeline(tour=tour, n_optuna_trials=args.optuna_trials)
                train_pipeline(tour=tour, n_optuna_trials=args.optuna_trials, use_odds=True)
            else:
                logger.info(f"\n>>> [{tour.upper()}] skip-train: keeping existing models <<<")

            logger.info(f"\n>>> [{tour.upper()}] settling track record <<<")
            logger.info(str(settle_predictions(tour)))
        except Exception as exc:
            msg = f"[{tour}] refresh failed: {exc}"
            logger.error(msg)
            logger.error(traceback.format_exc())
            errors.append(msg)

    if errors:
        logger.error(f"\n>>> REFRESH COMPLETED WITH ERRORS: {errors} <<<")
        raise SystemExit(1)
    logger.info("\n>>> REFRESH COMPLETE <<<")


def cmd_all(args: argparse.Namespace) -> None:
    """Run everything: download + features + train."""
    logger.info("\n" + "#" * 70)
    logger.info("  TENNISBOT - FULL PIPELINE")
    logger.info("#" * 70)
    t0 = time.time()
    logger.info("\n>>> PHASE 1: DOWNLOAD <<<")
    cmd_download(args)
    logger.info("\n>>> PHASE 2: FEATURE ENGINEERING <<<")
    cmd_features(args)
    logger.info("\n>>> PHASE 3: MODEL TRAINING <<<")
    cmd_train(args)
    if getattr(args, "train_odds", False):
        logger.info("\n>>> PHASE 3b: MARKET-AWARE TRAINING <<<")
        args.use_odds = True
        cmd_train(args)
    elapsed = time.time() - t0
    logger.info(f"\n>>> PIPELINE COMPLETE in {elapsed:.1f}s <<<")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TennisBot - AI Tennis Match Prediction Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py download --tour atp
  python main.py features --tour atp
  python main.py train --tour atp
  python main.py train --tour atp --use-odds
  python main.py refresh --tour both
  python main.py refresh --tour both --settle-only
  python main.py settle --tour both
  python main.py all --tour wta --train-odds
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_download = sub.add_parser("download", help="Download raw match CSVs")
    p_download.add_argument("--tour", default="atp", choices=["atp", "wta", "both"])
    p_download.add_argument("--start", type=int, default=None)
    p_download.add_argument("--end", type=int, default=None)
    p_download.add_argument("--overwrite", action="store_true")
    p_download.set_defaults(func=cmd_download)

    p_features = sub.add_parser("features", help="Run feature engineering")
    p_features.add_argument("--tour", default="atp", choices=["atp", "wta"])
    p_features.add_argument("--start", type=int, default=None)
    p_features.add_argument("--end", type=int, default=None)
    p_features.add_argument("--odds", type=str, default=None, help="Path to odds CSV file")
    p_features.add_argument("--stats-from", type=int, default=None)
    p_features.set_defaults(func=cmd_features)

    p_train = sub.add_parser("train", help="Train stacking ensemble")
    p_train.add_argument("--tour", default="atp", choices=["atp", "wta"])
    p_train.add_argument("--optuna-trials", type=int, default=50)
    p_train.add_argument("--start-year", type=int, default=None)
    p_train.add_argument("--end-year", type=int, default=None)
    p_train.add_argument(
        "--use-odds",
        action="store_true",
        help="Train market-aware variant with opening-odds features",
    )
    p_train.set_defaults(func=cmd_train)

    p_refresh = sub.add_parser(
        "refresh",
        help="Weekly: download + features + retrain both variants + settle track",
    )
    p_refresh.add_argument("--tour", default="both", choices=["atp", "wta", "both"])
    p_refresh.add_argument(
        "--optuna-trials", type=int, default=20,
        help="Optuna trials per model (default 20 for weekly speed)",
    )
    p_refresh.add_argument(
        "--settle-only", action="store_true",
        help="Only settle open track predictions (no download/train)",
    )
    p_refresh.add_argument(
        "--skip-train", action="store_true",
        help="Download + features + settle without retraining models",
    )
    p_refresh.set_defaults(func=cmd_refresh)

    p_settle = sub.add_parser("settle", help="Settle open track predictions")
    p_settle.add_argument("--tour", default="both", choices=["atp", "wta", "both"])
    p_settle.set_defaults(func=cmd_settle)

    p_all = sub.add_parser("all", help="Download + features + train")
    p_all.add_argument("--tour", default="atp", choices=["atp", "wta"])
    p_all.add_argument("--start", type=int, default=None)
    p_all.add_argument("--end", type=int, default=None)
    p_all.add_argument("--overwrite", action="store_true")
    p_all.add_argument("--odds", type=str, default=None)
    p_all.add_argument("--stats-from", type=int, default=None)
    p_all.add_argument("--optuna-trials", type=int, default=50)
    p_all.add_argument("--start-year", type=int, default=None)
    p_all.add_argument("--end-year", type=int, default=None)
    p_all.add_argument("--use-odds", action="store_true")
    p_all.add_argument(
        "--train-odds", action="store_true",
        help="Also train market-aware model after pure-stats",
    )
    p_all.set_defaults(func=cmd_all)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
