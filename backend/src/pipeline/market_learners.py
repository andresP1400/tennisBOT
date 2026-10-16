"""Fixed independent-model candidate constructors for the optional research study."""

from __future__ import annotations
from typing import Protocol, cast
import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from lightgbm import LGBMClassifier
from xgboost import XGBClassifier


class StudyEstimator(Protocol):
    def fit(
        self, features: NDArray[np.float64], labels: NDArray[np.int64]
    ) -> object: ...
    def predict_proba(self, features: NDArray[np.float64]) -> NDArray[np.float64]: ...


def candidates() -> tuple[dict[str, StudyEstimator], list[str]]:
    """Parameters are fixed before scoring; selection-period scores do not tune test filters."""
    result: dict[str, StudyEstimator] = {
        "logistic": make_pipeline(
            StandardScaler(), LogisticRegression(C=0.1, max_iter=500, random_state=42)
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=180,
            max_leaf_nodes=15,
            learning_rate=0.05,
            l2_regularization=10,
            min_samples_leaf=60,
            early_stopping=False,
            random_state=42,
        ),
    }
    result.update(tree_candidates())
    optional, missing = catboost_candidate()
    result.update(optional)
    return result, missing


def catboost_candidate() -> tuple[dict[str, StudyEstimator], list[str]]:
    result: dict[str, StudyEstimator] = {}
    missing = []
    try:
        from catboost import CatBoostClassifier

        result["catboost"] = cast(
            StudyEstimator,
            CatBoostClassifier(
                iterations=200,
                depth=4,
                learning_rate=0.05,
                l2_leaf_reg=10,
                random_seed=42,
                thread_count=2,
                verbose=False,
                allow_writing_files=False,
            ),
        )
    except ImportError:
        missing.append(
            "CatBoost not installed; optional requirements-market-research.txt"
        )
    return result, missing


def tree_candidates() -> dict[str, StudyEstimator]:
    return {
        "lightgbm": LGBMClassifier(
            n_estimators=200,
            num_leaves=15,
            learning_rate=0.05,
            reg_lambda=10,
            min_child_samples=60,
            n_jobs=2,
            random_state=42,
            verbosity=-1,
            deterministic=True,
            force_col_wise=True,
        ),
        "xgboost": XGBClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            reg_lambda=10,
            min_child_weight=20,
            n_jobs=2,
            random_state=42,
            tree_method="hist",
            eval_metric="logloss",
        ),
    }
