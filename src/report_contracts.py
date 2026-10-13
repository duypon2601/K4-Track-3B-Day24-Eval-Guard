"""Validate submission evidence, not just file existence. No network calls."""
from __future__ import annotations

import math
import re
from datetime import datetime
from pathlib import Path

from config import ROOT_DIR
from src.experiment_support import (MODEL_ROLES, generation_models, model_ids, percentiles,
                                    read_json, source_sha256)

METRICS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
DISTRIBUTIONS = ("factual", "multi_hop", "adversarial")
PAIR_SOURCES = {"A": "artifacts/answers_50q.json:answer",
                "B": "fixtures/human_labels_10q.json:model_answer",
                "reference": "fixtures/test_set_50q.json:ground_truth"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def score(value, name):
    require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1,
            f"{name}: expected finite score in [0, 1].")


def close(actual, expected, name, tolerance=1e-4):
    require(type(actual) in (int, float) and math.isfinite(actual)
            and abs(actual - expected) <= tolerance, f"{name}: inconsistent value.")


def exact_ids(rows, expected, key="id"):
    require(isinstance(rows, list), "Expected list.")
    require(all(isinstance(row, dict) for row in rows), "Expected list of objects.")
    ids = [row.get(key) for row in rows]
    require(all(type(value) is int and value > 0 for value in ids)
            and len(ids) == len(expected) and len(set(ids)) == len(ids)
            and set(ids) == set(expected), f"Missing, duplicate or unexpected {key}.")


def text(value, name):
    require(isinstance(value, str) and bool(value.strip()), f"{name}: empty text.")


def is_timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value):
        return False
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


def validate_schema(payload, name, *, schema_dir=None):
    """Validate the supplied Draft 2020-12 schema locally, without fetching refs."""
    from jsonschema import Draft202012Validator, FormatChecker
    schema_dir = Path(schema_dir) if schema_dir is not None else Path(ROOT_DIR) / "doc/schemas"
    schema = read_json(schema_dir / f"{name}.schema.json")
    Draft202012Validator.check_schema(schema)
    formats = FormatChecker()
    # date-time's optional jsonschema dependency is absent in the minimal test lock.
    # Register the required timestamp check explicitly so validation is never skipped.
    formats.checks("date-time")(is_timestamp)
    validator = Draft202012Validator(schema, format_checker=formats)
    error = next(validator.iter_errors(payload), None)
    if error is not None:
        location = "/".join(str(part) for part in error.absolute_path) or "$"
        raise ValueError(f"{name} schema at {location}: {error.message}")


def validate_metadata(report, source_paths):
    meta = report["metadata"]
    require(meta["format_version"] == 2 and meta["run_kind"] == "live",
            "Submission must contain live experiment evidence, not mock results.")
    text(meta["created_at"], "created_at")
    require(is_timestamp(meta["created_at"]),
            "created_at requires an ISO timestamp with a timezone.")
    require(isinstance(meta["models"], dict) and set(meta["models"]) == set(MODEL_ROLES),
            "Metadata requires four separate model roles.")
    for role in MODEL_ROLES:
        declared = meta["models"][role]
        require(model_ids(declared, role) == declared, f"{role} models must be sorted and unique.")
    for path in source_paths:
        digest = source_sha256(path)
        require(meta["source_sha256"].get(Path(path).name) == digest,
                f"Stale experiment source: {Path(path).name}.")


def validate_answers(rows, questions, *, schema_dir=None):
    validate_schema(rows, "answers", schema_dir=schema_dir)
    source = {q["id"]: q for q in questions}
    exact_ids(rows, source)
    for row in rows:
        q = source[row["id"]]
        for name in ("question", "ground_truth", "distribution"):
            require(row.get(name) == q[name], f"Answer {row['id']}: {name} mismatch.")
        text(row.get("answer"), "answer")
        mode = row.get("generation_mode")
        require(mode in ("llm", "extractive_fallback"), "Invalid generation_mode.")
        if mode == "llm":
            model_ids([row.get("generation_model")], "generation_model")
        else:
            require(row.get("generation_model") is None, "Fallback must not declare an LLM generation_model.")
        require(isinstance(row.get("contexts"), list)
                and all(isinstance(c, str) and c.strip() for c in row["contexts"]),
                "contexts must be a list of non-empty strings (may be empty).")


def validate_phase_a(report, answers, *, schema_dir=None):
    validate_schema(report, "phase_a", schema_dir=schema_dir)
    require(report["metadata"]["models"]["generation"] == generation_models(answers),
            "Phase A generation models must match saved answers.")
    rows = report["per_question"]
    source = {a["id"]: a for a in answers}
    exact_ids(rows, source, "question_id")
    require(report["total_questions"] == len(source) == 50, "Phase A needs 50 results.")
    averages = {}
    expected_matrix = {m: {d: 0 for d in DISTRIBUTIONS} for m in METRICS}
    by_id = {row["question_id"]: row for row in rows}
    for row in rows:
        original = source[row["question_id"]]
        for name in ("distribution", "question", "answer", "contexts", "ground_truth"):
            require(row[name] == original[name], f"Phase A {name} does not match answers.")
        for metric in METRICS:
            score(row[metric], metric)
        worst = min(METRICS, key=lambda m: row[m])
        expected_matrix[worst][row["distribution"]] += 1
    for distribution in DISTRIBUTIONS:
        subset = [r for r in rows if r["distribution"] == distribution]
        expected_count = {"factual": 20, "multi_hop": 20, "adversarial": 10}[distribution]
        require(len(subset) == expected_count, "Distribution counts must be 20/20/10.")
        summary = report["per_distribution"][distribution]
        require(summary["count"] == expected_count, "Distribution count mismatch.")
        for metric in METRICS:
            close(summary[metric], sum(r[metric] for r in subset) / len(subset), metric)
        averages[distribution] = sum(sum(r[m] for m in METRICS) / 4 for r in subset) / len(subset)
        close(summary["avg_score"], averages[distribution], "distribution avg_score")
    cluster = report["failure_clusters"]
    require(cluster["matrix"] == expected_matrix, "Worst-metric matrix mismatch.")
    chosen = cluster["dominant_failure_distribution"]
    require(chosen in averages and math.isclose(averages[chosen], min(averages.values())),
            "Weakest distribution must have the lowest mean score, not the most questions.")
    metric = cluster["dominant_failure_metric"]
    totals = {m: sum(expected_matrix[m].values()) for m in METRICS}
    require(metric in totals and totals[metric] == max(totals.values()),
            "Dominant failure metric mismatch.")
    text(cluster["insight"], "cluster insight")
    bottom = report["bottom_10"]
    require(isinstance(bottom, list) and len(bottom) == 10, "Exactly 10 bottom rows required.")
    require(len({r["question_id"] for r in bottom}) == 10, "Duplicate bottom IDs.")
    expected_scores = sorted(sum(r[m] for m in METRICS) / 4 for r in rows)[:10]
    for rank, (row, expected) in enumerate(zip(bottom, expected_scores), 1):
        original = by_id[row["question_id"]]
        require(row["rank"] == rank and row["distribution"] == original["distribution"]
                and row["question"] == original["question"], "Bottom row identity/rank mismatch.")
        close(row["avg_score"], expected, "bottom score")
        close(row["avg_score"], sum(original[m] for m in METRICS) / 4, "bottom source score")
        require(row["worst_metric"] == min(METRICS, key=lambda m: original[m]),
                "Bottom worst metric mismatch.")
        text(row["diagnosis"], "diagnosis")
        text(row["suggested_fix"], "suggested_fix")


def binary_kappa(judge, human):
    require(len(judge) == len(human) and len(judge) > 0, "Label lengths mismatch/empty.")
    require(all(type(x) is int and x in (0, 1) for x in judge + human), "Labels must be 0/1.")
    n = len(judge)
    observed = sum(a == b for a, b in zip(judge, human)) / n
    chance = sum(judge.count(label) * human.count(label) / n**2 for label in (0, 1))
    require(chance < 1, "Kappa undefined for constant unanimous labels.")
    return (observed - chance) / (1 - chance)


def validate_phase_b(report, answers, questions, human_data, *, schema_dir=None):
    validate_schema(report, "phase_b", schema_dir=schema_dir)
    require(report.get("pair_sources") == PAIR_SOURCES, "Invalid or missing pair_sources.")
    require(report["metadata"]["models"]["generation"] == generation_models(answers),
            "Phase B generation models must match saved answers.")
    pairs = report["pairwise_results"]
    source = {a["id"]: a for a in answers}
    human = {h["question_id"]: h for h in human_data}
    by_question = {q["id"]: q for q in questions}
    from config import PAIR_QUESTION_IDS
    exact_ids(pairs, PAIR_QUESTION_IDS, "question_id")
    inconsistent = longer_wins = decisive = 0
    details = {"a_wins_a_longer": 0, "b_wins_b_longer": 0, "total_decisive": 0}
    for row in pairs:
        qid = row["question_id"]
        require(row["question"] == by_question[qid]["question"], "Pair question mismatch.")
        require(row["answer_a"] == source[qid]["answer"]
                and row["answer_b"] == human[qid]["model_answer"],
                "A/B sources must be saved pipeline answer / supplied model_answer.")
        for name in ("winner_pass1", "winner_pass2", "final_winner"):
            require(row[name] in ("A", "B", "tie"), f"Invalid {name}.")
        consistent = row["winner_pass1"] == row["winner_pass2"]
        require(type(row["position_consistent"]) is bool
                and row["position_consistent"] == consistent, "Position consistency mismatch.")
        require(row["final_winner"] == (row["winner_pass1"] if consistent else "tie"),
                "Consensus mismatch after order conversion.")
        for name in ("reasoning_pass1", "reasoning_pass2"):
            text(row[name], name)
        for name in ("scores_pass1", "scores_pass2"):
            require(set(row[name]) == {"A", "B"}, "Scores require A and B.")
            for value in row[name].values():
                score(value, name)
        inconsistent += not consistent
        winner = row["final_winner"]
        if winner != "tie":
            decisive += 1
            is_longer = len(row["answer_a" if winner == "A" else "answer_b"]) > len(
                row["answer_b" if winner == "A" else "answer_a"])
            longer_wins += is_longer
            details["a_wins_a_longer" if winner == "A" else "b_wins_b_longer"] += is_longer
    judgments = report["binary_judgments"]
    exact_ids(judgments, human, "question_id")
    judge_labels = []
    human_labels = []
    for row in judgments:
        original = human[row["question_id"]]
        require(row["question"] == original["question"]
                and row["model_answer"] == original["model_answer"],
                "Calibration must evaluate the exact supplied model_answer and question.")
        require(type(row["label"]) is int and row["label"] in (0, 1), "Invalid binary label.")
        text(row["reasoning"], "binary reasoning")
        judge_labels.append(row["label"])
        human_labels.append(original["human_label"])
    calibration = report["calibration"]
    require(calibration["question_ids"] == [r["question_id"] for r in judgments]
            and calibration["judge_labels"] == judge_labels
            and calibration["human_labels"] == human_labels, "Calibration alignment mismatch.")
    close(calibration["cohen_kappa"], binary_kappa(judge_labels, human_labels), "kappa")
    bias = report["bias_report"]
    require(bias["total_judged"] == len(pairs)
            and bias["position_bias_count"] == inconsistent, "Bias counts mismatch.")
    close(bias["position_bias_rate"], inconsistent / len(pairs), "position bias", .001)
    close(bias["verbosity_bias"], longer_wins / decisive if decisive else 0, "verbosity bias", .001)
    details["total_decisive"] = decisive
    require(bias["verbosity_details"] == details, "Verbosity detail counts mismatch.")
    text(bias["interpretation"], "bias interpretation")


def validate_input_results(rows, inputs):
    source = {item["id"]: item for item in inputs}
    exact_ids(rows, source)
    for row in rows:
        original = source[row["id"]]
        require(row["expected"] == original["expected"]
                and row["category"] == original["category"]
                and row["input"] == original["input"], "Guard input provenance mismatch.")
        require(row["actual"] in ("blocked", "allowed"), "Invalid actual decision.")
        require(type(row["passed"]) is bool and
                row["passed"] == (row["actual"] == original["expected"]), "Incorrect passed flag.")
        require(row["blocked_by"] in ("presidio", "nemo_input", None), "Invalid blocked_by.")
        require((row["actual"] == "allowed") == (row["blocked_by"] is None),
                "Decision/blocked_by mismatch.")


def validate_latency(latency, minimum_samples=20):
    require(latency["scope"] == "input_layers_sequential", "Latency scope must name input layers.")
    require(latency["percentile_method"] == "linear", "Use linear interpolated percentiles.")
    rows = latency["samples"]
    require(latency["n_samples"] == len(rows) >= minimum_samples
            and latency["warmup_runs"] >= 2, "Need timed samples and two excluded warm-up runs.")
    for row in rows:
        for layer in ("presidio_ms", "nemo_input_ms", "input_guard_ms"):
            require(type(row[layer]) in (int, float) and math.isfinite(row[layer])
                    and row[layer] > 0, "Zero/invalid latency sample.")
        close(row["input_guard_ms"], row["presidio_ms"] + row["nemo_input_ms"], "layer sum")
    for layer in ("presidio_ms", "nemo_input_ms", "input_guard_ms"):
        expected = percentiles([row[layer] for row in rows])
        for key in expected:
            close(latency[layer][key], expected[key], f"{layer}.{key}")
    from config import LATENCY_BUDGET_P95_MS
    require(latency["budget_ms"] == LATENCY_BUDGET_P95_MS, "Latency budget mismatch.")
    require(type(latency["latency_budget_ok"]) is bool
            and latency["latency_budget_ok"] == (latency["input_guard_ms"]["p95"] < latency["budget_ms"]),
            "Budget decision mismatch.")


def validate_phase_c(report, attacks, clean, outputs, *, require_quality=True, schema_dir=None):
    validate_schema(report, "phase_c", schema_dir=schema_dir)
    for name, inputs in (("adversarial", attacks), ("clean", clean)):
        group = report[name]
        validate_input_results(group["results"], inputs)
        passed = sum(row["passed"] for row in group["results"])
        require(group["total"] == len(inputs) and group["passed"] == passed, "Guard count mismatch.")
        close(group["pass_rate"], passed / len(inputs), f"{name} pass rate")
    if require_quality:
        require(report["adversarial"]["passed"] >= 15, "Attack suite must reach at least 15/20.")
    false_positives = sum(row["actual"] == "blocked" for row in report["clean"]["results"])
    close(report["clean"]["false_positive_rate"], false_positives / len(clean), "false positives")
    if require_quality:
        require(false_positives == 0, "Clean inputs were incorrectly blocked; investigate before submitting.")
    rows = report["output_results"]
    exact_ids(rows, {item["id"] for item in outputs})
    expected = {item["id"]: item for item in outputs}
    for row in rows:
        original = expected[row["id"]]
        require(row["question"] == original["question"] and row["answer"] == original["answer"],
                "Output case provenance mismatch.")
        require(type(row["safe"]) is bool, "Output safe must be boolean.")
        matched = row["safe"] == (original["expected"] == "safe")
        require(type(row["passed"]) is bool and row["passed"] == matched,
                "Output passed flag mismatch.")
        if require_quality:
            require(matched, "Incorrect output safety decision.")
        text(row["final_answer"], "final_answer")
        if row["safe"]:
            require(row["final_answer"] == row["answer"] and row["flagged_reason"] is None,
                    "Clean output must be preserved.")
        else:
            text(row["flagged_reason"], "flagged_reason")
            require(row["final_answer"] != row["answer"], "Unsafe output was not replaced/redacted.")
    validate_latency(report["latency"])


def validate_markdown(path):
    content = Path(path).read_text(encoding="utf-8")
    require(len(content.strip()) >= 200, f"{path}: missing explanation.")
    markers = re.findall(r"\{\{[^}]+\}\}|\[(?:Họ|MSSV|Tên|Ngày|Link|Commit|Nhánh|Nhiệm vụ|File|Lệnh|Người|Công cụ|Phần|Viết|Nếu|Kết quả)[^\]\n]*\]", content)
    require(not markers, f"{path}: unresolved placeholders.")
    require("HoVaTen-MSSV" not in content, f"{path}: individual identity placeholder.")
    require(not re.search(r"(?:^|[|\s(~])\?(?:\s*(?:ms|%|/|[|)])|\s*$)", content, re.M),
            f"{path}: unresolved measurement '?'.")
    for line in content.splitlines():
        if line.startswith("|") and line.endswith("|"):
            cells = [cell.strip() for cell in line.split("|")[1:-1]]
            require(all(cells), f"{path}: empty table cells.")
    return content


def validate_team(path):
    content = validate_markdown(path)
    require("## INDIVIDUAL" in content, "TEAM needs an INDIVIDUAL section.")
    members = []
    for line in content.splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.split("|")[1:-1]]
            if len(cells) >= 3 and cells[0].isdigit():
                members.append(cells[2])
    require(bool(members) and len(set(members)) == len(members), "TEAM needs distinct member MSSVs.")
    individual = content.split("## INDIVIDUAL", 1)[1]
    for student_id in members:
        require(any(line.startswith("### ") and line.rstrip().endswith("-" + student_id)
                    for line in individual.splitlines()),
                f"Missing INDIVIDUAL entry for {student_id}.")
