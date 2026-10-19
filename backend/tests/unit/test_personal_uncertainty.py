"""Paired resampling keeps shared-date dependence and identical reference losses."""

import numpy as np
import pytest

from pipeline.personal_uncertainty import paired_date_bootstrap


def inputs():
    return (
        np.asarray([1, 1, 0, 1, 0, 0], dtype=np.int64),
        np.asarray([0.9, 0.7, 0.2, 0.4, 0.6, 0.3]),
        np.asarray(
            [
                "2026-01-01",
                "2026-01-01",
                "2026-01-08",
                "2026-01-08",
                "2026-01-15",
                "2026-01-15",
            ],
            dtype="datetime64[D]",
        ),
    )


def test_paired_identical_forecasts_have_zero_difference_and_reproducible_intervals():
    labels, probabilities, dates = inputs()
    report = paired_date_bootstrap(
        labels, probabilities, probabilities, dates, resamples=200
    )
    assert report == paired_date_bootstrap(
        labels, probabilities, probabilities, dates, resamples=200
    )
    assert report["date_blocks"] == 3
    assert report["ml"]["accuracy"]["estimate"] == pytest.approx(4 / 6)
    for value in report["ml_minus_elo"].values():
        assert value == {"estimate": 0.0, "lower_95": 0.0, "upper_95": 0.0}


def test_paired_reference_labels_and_loss_directions_are_explicit():
    labels, probabilities, dates = inputs()
    report = paired_date_bootstrap(
        labels,
        probabilities,
        np.full(6, 0.5),
        dates,
        resamples=200,
        reference_name="frozen_ml",
    )
    assert "frozen_ml" in report and "elo" not in report
    assert report["ml_minus_frozen_ml"]["brier"]["estimate"] < 0
    assert report["ml_minus_frozen_ml"]["log_loss"]["estimate"] < 0


@pytest.mark.parametrize(
    "problem", ["one_date", "nan", "misaligned", "bad_label", "bad_date", "resamples"]
)
def test_invalid_or_insufficient_bootstrap_inputs_do_not_report_certainty(problem):
    labels, probabilities, dates = inputs()
    if problem == "one_date":
        dates[:] = dates[0]
    if problem == "nan":
        probabilities[0] = np.nan
    if problem == "misaligned":
        probabilities = probabilities[:-1]
    if problem == "bad_label":
        labels[0] = 2
    if problem == "bad_date":
        dates[0] = np.datetime64("NaT")
    with pytest.raises(ValueError):
        paired_date_bootstrap(
            labels,
            probabilities,
            probabilities,
            dates,
            resamples=1 if problem == "resamples" else 200,
        )
