from types import SimpleNamespace

import pytest

from scripts.run_rag_smoke import METRICS, comparison, main, scored_rows, select_baseline

pytestmark = pytest.mark.support


def sample(question_id=22):
    return {"id": question_id, "question": "Q", "distribution": "multi_hop",
            "ground_truth": "reference", "answer": "answer", "contexts": ["context"]}


def test_smoke_requires_live_before_loading_runtime():
    with pytest.raises(SystemExit):
        main([])


@pytest.mark.parametrize("name", ["answers_50q.json", "ragas_50q.json", "judge_results.json", "guard_results.json"])
def test_smoke_refuses_to_overwrite_required_artifacts(monkeypatch, name):
    import config
    from pathlib import Path
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-only-key")
    destination = Path(config.ARTIFACTS_DIR) / name
    with pytest.raises(ValueError, match="overwrite"):
        main(["--live", "--output", str(destination)])


def test_smoke_selects_requested_order_and_checks_source():
    rows = [sample(22), sample(33)]
    assert select_baseline(rows, rows, [33, 22]) == list(reversed(rows))
    with pytest.raises(ValueError, match="distinct"):
        select_baseline(rows, rows, [22, 22])
    with pytest.raises(ValueError, match="Missing"):
        select_baseline(rows, rows, [39])
    changed = [{**rows[0], "ground_truth": "changed"}, rows[1]]
    with pytest.raises(ValueError, match="ground_truth"):
        select_baseline(rows, changed, [22])


def test_smoke_scores_and_compares_real_evaluator_rows():
    baseline = scored_rows([sample()], [SimpleNamespace(**{metric: .25 for metric in METRICS})])
    improved = scored_rows([sample()], [SimpleNamespace(**{metric: .75 for metric in METRICS})])
    summary = comparison(baseline, improved)
    assert summary["baseline_mean"] == .25
    assert summary["improved_mean"] == .75
    assert summary["mean_delta"] == .5
    assert summary["per_question"][0]["metric_deltas"] == {metric: .5 for metric in METRICS}


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 2])
def test_smoke_rejects_invalid_measured_scores(value):
    with pytest.raises(ValueError, match="invalid"):
        scored_rows([sample()], [SimpleNamespace(**{metric: value for metric in METRICS})])


def test_smoke_rejects_incomplete_or_mismatched_comparisons():
    with pytest.raises(ValueError, match="count"):
        scored_rows([sample()], [])
    with pytest.raises(ValueError, match="non-empty"):
        comparison([], [])
    baseline = scored_rows([sample()], [SimpleNamespace(**{metric: .5 for metric in METRICS})])
    improved = [{**baseline[0], "id": 33}]
    with pytest.raises(ValueError, match="mismatch"):
        comparison(baseline, improved)
