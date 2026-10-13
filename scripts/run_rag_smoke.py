"""Run a live, three-question comparison without replacing lab artifacts."""
from __future__ import annotations

import argparse
import gc
import math
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

METRICS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")


def select_baseline(questions, answers, question_ids):
    if not question_ids or len(set(question_ids)) != len(question_ids):
        raise ValueError("Select distinct question IDs.")
    question_index = {row["id"]: row for row in questions}
    answer_index = {row["id"]: row for row in answers}
    rows = []
    for question_id in question_ids:
        if question_id not in question_index or question_id not in answer_index:
            raise ValueError(f"Missing baseline question {question_id}.")
        answer = answer_index[question_id]
        for field in ("question", "distribution", "ground_truth"):
            if answer[field] != question_index[question_id][field]:
                raise ValueError(f"Baseline {question_id}: {field} does not match source.")
        rows.append(answer)
    return rows


def scored_rows(rows, results):
    if len(rows) != len(results):
        raise ValueError("Evaluator result count does not match the sample.")
    scored = []
    for row, result in zip(rows, results):
        scores = {metric: float(getattr(result, metric)) for metric in METRICS}
        if any(not math.isfinite(value) or not 0 <= value <= 1 for value in scores.values()):
            raise ValueError("Evaluator returned an invalid metric.")
        scored.append({**row, "scores": scores, "avg_score": sum(scores.values()) / len(METRICS)})
    return scored


def comparison(baseline, improved):
    if not baseline or len(baseline) != len(improved):
        raise ValueError("Comparison needs two equally sized, non-empty samples.")
    deltas = []
    for before, after in zip(baseline, improved):
        for field in ("id", "question", "distribution", "ground_truth"):
            if before[field] != after[field]:
                raise ValueError(f"Comparison mismatch: {field}.")
        deltas.append({
            "question_id": before["id"],
            "baseline_avg_score": before["avg_score"],
            "improved_avg_score": after["avg_score"],
            "avg_score_delta": after["avg_score"] - before["avg_score"],
            "metric_deltas": {metric: after["scores"][metric] - before["scores"][metric]
                              for metric in METRICS},
        })
    baseline_mean = sum(row["avg_score"] for row in baseline) / len(baseline)
    improved_mean = sum(row["avg_score"] for row in improved) / len(improved)
    return {"baseline_mean": baseline_mean, "improved_mean": improved_mean,
            "mean_delta": improved_mean - baseline_mean, "per_question": deltas}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--question-ids", type=int, nargs="+", default=[22, 33, 39])
    parser.add_argument("--output", type=Path, default=Path("artifacts/smoke_3q.json"))
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("This experiment calls APIs and requires --live.")

    import config
    from src.experiment_support import generation_models, metadata, read_json, write_json

    if not config.OPENAI_API_KEY:
        raise ValueError("Configure a provider key before running the live sample.")
    protected = {Path(config.ANSWERS_PATH).resolve(),
                 *(Path(config.ARTIFACTS_DIR, name).resolve() for name in
                   ("ragas_50q.json", "judge_results.json", "guard_results.json"))}
    if args.output.resolve() in protected:
        raise ValueError("Smoke output must not overwrite the four required lab artifacts.")
    questions = read_json(config.TEST_SET_PATH)
    original_answers = read_json(config.ANSWERS_PATH)
    baseline = select_baseline(questions, original_answers, args.question_ids)
    archived = read_json(Path(config.ARTIFACTS_DIR) / "ragas_50q.json")
    if generation_models(baseline) != [config.GENERATION_MODEL]:
        raise ValueError("Use the baseline generation model for a comparable experiment.")
    expected_evaluators = sorted([config.EVALUATOR_MODEL, config.EMBEDDING_MODEL])
    if archived["metadata"]["models"]["evaluator"] != expected_evaluators:
        raise ValueError("Use the baseline evaluator models for a comparable experiment.")

    config.COLLECTION_NAME = "lab24_parent_smoke"
    config.RAGAS_CACHE_PATH = str(Path(config.ROOT_DIR) / ".cache/smoke_ragas_scores.json")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    import torch
    torch.set_num_threads(4)
    from scripts.setup_answers import build_pipeline, run_query

    print("Building improved pipeline; using a separate Qdrant collection.", flush=True)
    search, reranker, top_k = build_pipeline()
    improved = []
    for row in baseline:
        answer, contexts, mode, model = run_query(row["question"], search, reranker, top_k)
        if mode != "llm":
            raise ValueError(f"Question {row['id']}: generation fell back; stop the comparison.")
        improved.append({**row, "answer": answer, "contexts": contexts,
                         "generation_mode": mode, "generation_model": model})
        print(f"Generated question {row['id']}: {len(contexts)} raw contexts.", flush=True)
    del search, reranker
    gc.collect()

    sources = [config.ANSWERS_PATH, config.TEST_SET_PATH,
               Path(config.ARTIFACTS_DIR) / "ragas_50q.json",
               Path(config.ROOT_DIR) / "scripts/setup_answers.py",
               Path(config.ROOT_DIR) / "config.py"]
    payload = {
        "scope": "smoke_only_not_50q", "status": "generated_answers_only",
        "question_ids": args.question_ids, "baseline": baseline, "improved": improved,
        "archived_baseline": [row for row in archived["per_question"]
                              if row["question_id"] in args.question_ids],
        "metadata": metadata(sources, models={"generation": generation_models(improved),
            "evaluator": expected_evaluators, "judge": [], "guard": []}),
    }
    write_json(args.output, payload)
    print("Re-evaluating baseline and improved answers together with the same models.", flush=True)
    from src.m4_eval import evaluate_ragas
    combined = baseline + improved
    evaluation = evaluate_ragas(
        [row["question"] for row in combined], [row["answer"] for row in combined],
        [row["contexts"] for row in combined], [row["ground_truth"] for row in combined],
    )
    if sorted(evaluation["metadata"]["evaluator_models"]) != expected_evaluators:
        raise ValueError("Actual evaluator models differ from the baseline.")
    results = evaluation["per_question"]
    if len(results) != len(combined):
        raise ValueError("Evaluator returned an incomplete comparison.")
    payload["baseline"] = scored_rows(baseline, results[:len(baseline)])
    payload["improved"] = scored_rows(improved, results[len(baseline):])
    payload["comparison"] = comparison(payload["baseline"], payload["improved"])
    payload["status"] = "complete"
    write_json(args.output, payload)
    summary = payload["comparison"]
    print(f"Sample mean: {summary['baseline_mean']:.4f} -> {summary['improved_mean']:.4f} "
          f"(delta {summary['mean_delta']:+.4f}); not a 50-question result.", flush=True)
    print(f"Saved {args.output}; baseline lab artifacts are unchanged.", flush=True)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
