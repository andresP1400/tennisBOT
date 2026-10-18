"""A result refresh cannot erase models or hide missing point statistics."""

from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from api.personal_engine import statistics_age, model_warning
from features.personal_schedule import Fixture
from pipeline.personal_model import PersonalBundle
from pipeline.personal_train import activate_version, save_artifacts


def test_candidate_does_not_replace_active_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pipeline import personal_train as training

    monkeypatch.setattr(training, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(training, "REPORTS_DIR", tmp_path / "reports")
    directory = tmp_path / "models/personal"
    directory.mkdir(parents=True)
    pointer = directory / "atp-latest.json"
    pointer.write_text('{"version":"preserved"}')
    report: dict[str, object] = {"data_through": "2026-01-01", "feature_schema": 2}
    save_artifacts(
        "atp",
        "logistic",
        make_pipeline(StandardScaler(), LogisticRegression()),
        LogisticRegression(),
        LogisticRegression(),
        {},
        report,
        activate=False,
    )
    assert pointer.read_text() == '{"version":"preserved"}'
    activate_version("atp", str(report["model_version"]))
    assert str(report["model_version"]) in pointer.read_text()


def test_fresh_results_cannot_hide_stale_statistics() -> None:
    report: dict[str, object] = {
        "statistics_through": "2026-01-01",
        "input_limitations": "Partial result-only refresh",
    }
    bundle = PersonalBundle(
        "atp",
        "unit",
        "logistic",
        make_pipeline(StandardScaler(), LogisticRegression()),
        LogisticRegression(),
        LogisticRegression(),
        {},
        {},
        "2026-10-01",
        report,
    )
    fixture = Fixture(
        id="unit",
        tour="atp",
        player1="One",
        player2="Two",
        tournament="Event",
        commence_time=datetime.now(timezone.utc) + timedelta(days=1),
        source="unit",
        fetched_at=datetime.now(timezone.utc),
        surface="Hard",
    )
    assert statistics_age(bundle, 1) > 100
    warning = model_warning(bundle, fixture, 1)
    assert warning is not None and warning.startswith("Partial result-only refresh")
    assert "stale or missing" in warning
