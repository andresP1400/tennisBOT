"""The stale-state reference must use the same match format and safe time window."""

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from pipeline import result_update_study as study
from pipeline.personal_model import PersonalBundle
from pipeline.personal_state import Player


def bundle() -> PersonalBundle:
    return PersonalBundle(
        "atp",
        "unit",
        "logistic",
        make_pipeline(LogisticRegression()),
        LogisticRegression(),
        LogisticRegression(),
        {1: Player("One"), 2: Player("Two")},
        {"one": 1, "two": 2},
        "2026-01-01",
        {},
        feature_schema=2,
    )


def test_frozen_reference_preserves_five_set_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = []

    def raw(estimator, features):
        captured.append(features)
        return np.full(len(features), 0.5)

    monkeypatch.setattr(study, "raw_probability", raw)
    monkeypatch.setattr(study, "calibrate", lambda calibrator, values: values)
    frame = pd.DataFrame(
        {
            "date": [pd.Timestamp("2026-03-01")],
            "player1": ["One"],
            "player2": ["Two"],
            "surface": ["Hard"],
            "best_of": [5],
        }
    )
    study.frozen_state_probabilities(bundle(), frame)
    assert captured[0][0, 14] == 1


def test_frozen_reference_cannot_use_later_player_state_in_an_earlier_test() -> None:
    frame = pd.DataFrame({"date": [pd.Timestamp("2026-01-10")]})
    with pytest.raises(ValueError, match="embargo"):
        study.frozen_state_probabilities(bundle(), frame)
