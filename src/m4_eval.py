from __future__ import annotations

"""Module 4: RAGAS Evaluation — 4 metrics + failure analysis."""

import os, sys, json, math
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (TEST_SET_PATH, LLM_PROVIDER, EVALUATOR_MODEL, EMBEDDING_MODEL,
                    RAGAS_CACHE_PATH)


@dataclass
class EvalResult:
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float


METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


def load_test_set(path: str = TEST_SET_PATH) -> list[dict]:
    """Load test set from JSON. (Đã implement sẵn)"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


NAN_RETRY_ROUNDS = 2  # số lượt chấm lại các câu RAGAS trả NaN (lỗi/timeout) trước khi báo lỗi


def _ragas_backend() -> dict:
    """Judge LLM + embeddings cho RAGAS, khai báo tường minh để ghi đúng evaluator_models.

    Judge là EVALUATOR_MODEL (OpenAI hoặc Gemini qua endpoint tương thích OpenAI, có rate limit),
    embeddings chạy local bằng bge-m3 để không tốn quota.
    """
    from langchain_openai import ChatOpenAI
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from ragas.metrics import answer_relevancy
    from ragas.run_config import RunConfig
    from src.llm import get_rate_limiter

    if LLM_PROVIDER == "gemini":
        answer_relevancy.strictness = 1  # Gemini không hỗ trợ n>1 completions trong 1 request
    return {
        "llm": ChatOpenAI(model=EVALUATOR_MODEL, temperature=0, max_retries=8,
                          rate_limiter=get_rate_limiter()),
        "embeddings": HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL,
                                            encode_kwargs={"normalize_embeddings": True}),
        "run_config": RunConfig(timeout=240, max_retries=6, max_wait=60, max_workers=2),
    }


def _measure(rows: list[dict], backend: dict) -> list[dict]:
    """Chạy RAGAS trên rows, trả mỗi câu 1 dict metric → float (NaN nếu câu đó lỗi)."""
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
    from datasets import Dataset

    dataset = Dataset.from_dict({key: [row[key] for row in rows]
                                 for key in ("question", "answer", "contexts", "ground_truth")})
    df = evaluate(dataset, metrics=[faithfulness, answer_relevancy,
                                    context_precision, context_recall], **backend).to_pandas()
    scores = []
    for _, row in df.iterrows():
        values = {}
        for metric in METRICS:
            value = row.get(metric)
            values[metric] = float("nan") if value is None else float(value)
        scores.append(values)
    return scores


BATCH_SIZE = 5  # số câu mỗi lượt gọi RAGAS; sau mỗi lượt điểm được lưu vào cache


def _row_key(row: dict) -> str:
    """Khóa cache: đổi model, câu hỏi, answer, contexts hay reference đều thành khóa khác."""
    import hashlib
    payload = json.dumps([EVALUATOR_MODEL, EMBEDDING_MODEL, row["question"], row["answer"],
                          row["contexts"], row["ground_truth"]], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_cache() -> dict:
    if os.path.exists(RAGAS_CACHE_PATH):
        with open(RAGAS_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(RAGAS_CACHE_PATH), exist_ok=True)
    with open(RAGAS_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def evaluate_ragas(questions: list[str], answers: list[str],
                   contexts: list[list[str]], ground_truths: list[str]) -> dict:
    """Run RAGAS evaluation.

    Trả per_question đúng thứ tự đầu vào và metadata.evaluator_models là các model thực
    sự được cấu hình cho lượt chấm này. Chấm theo lô nhỏ và lưu từng metric đã đo vào cache
    (khóa theo model + nội dung câu) để hết quota giữa chừng không mất phần đã chấm; chạy lại
    chỉ chấm phần còn thiếu. Metric NaN (lỗi/timeout) được chấm lại; nếu vẫn NaN thì báo lỗi,
    không thay bằng điểm giả.
    """
    rows = [{"question": q, "answer": a, "contexts": list(c), "ground_truth": g}
            for q, a, c, g in zip(questions, answers, contexts, ground_truths)]
    if not rows:
        raise ValueError("RAGAS needs at least one question.")
    keys = [_row_key(row) for row in rows]
    cache = _load_cache()
    backend = _ragas_backend()

    def missing():
        return [i for i, key in enumerate(keys)
                if any(not math.isfinite(cache.get(key, {}).get(m, float("nan"))) for m in METRICS)]

    for attempt in range(1 + NAN_RETRY_ROUNDS):
        todo = missing()
        if not todo:
            break
        print(f"  RAGAS lượt {attempt + 1}/{1 + NAN_RETRY_ROUNDS}: chấm {len(todo)}/{len(rows)} câu "
              f"(đã có {len(rows) - len(todo)} trong cache)", flush=True)
        for start in range(0, len(todo), BATCH_SIZE):
            batch = todo[start:start + BATCH_SIZE]
            measured = _measure([rows[i] for i in batch], backend)
            if len(measured) != len(batch):
                raise ValueError("RAGAS returned a different number of rows than it was given.")
            got = 0
            for i, values in zip(batch, measured):
                entry = cache.setdefault(keys[i], {})
                for metric in METRICS:
                    if math.isfinite(values[metric]):
                        entry[metric] = values[metric]
                        got += 1
            _save_cache(cache)
            if got == 0:
                raise ValueError("RAGAS measured nothing for a whole batch (quota/API down?); "
                                 "measured scores are kept in the cache — rerun to resume.")
    if missing():
        raise ValueError(f"RAGAS still returned NaN for rows {missing()}; no fake scores are "
                         "substituted. Rerun to retry only those rows.")

    # Sai số số học của RAGAS có thể vượt [0, 1] một chút (vd 1.0000000002) → kẹp lại.
    per_question = [EvalResult(**row, **{m: min(1.0, max(0.0, cache[key][m])) for m in METRICS})
                    for row, key in zip(rows, keys)]
    aggregate = {m: sum(getattr(r, m) for r in per_question) / len(per_question) for m in METRICS}
    return {**aggregate, "per_question": per_question,
            "metadata": {"evaluator_models": [EVALUATOR_MODEL, EMBEDDING_MODEL]}}


def failure_analysis(eval_results: list[EvalResult], bottom_n: int = 10) -> list[dict]:
    """Analyze bottom-N worst questions using Diagnostic Tree."""
    diagnostic_tree = {
        "faithfulness": ("LLM hallucinating", "Tighten prompt, lower temperature"),
        "context_recall": ("Missing relevant chunks", "Improve chunking or add BM25"),
        "context_precision": ("Too many irrelevant chunks", "Add reranking or metadata filter"),
        "answer_relevancy": ("Answer doesn't match question", "Improve prompt template"),
    }

    analyzed = []
    for r in eval_results:
        scores = {m: getattr(r, m) for m in METRICS}
        worst_metric = min(scores, key=scores.get)
        diagnosis, suggested_fix = diagnostic_tree[worst_metric]
        analyzed.append({
            "question": r.question,
            "answer": r.answer,
            "ground_truth": r.ground_truth,
            "scores": scores,
            "avg_score": sum(scores.values()) / len(scores),
            "worst_metric": worst_metric,
            "score": scores[worst_metric],
            "diagnosis": diagnosis,
            "suggested_fix": suggested_fix,
        })

    analyzed.sort(key=lambda x: x["avg_score"])
    return analyzed[:bottom_n]


def save_report(results: dict, failures: list[dict], path: str = "reports/ragas_report.json"):
    """Save evaluation report to JSON. (Đã implement sẵn)"""
    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    report = {
        "aggregate": {k: v for k, v in results.items() if k != "per_question"},
        "num_questions": len(results.get("per_question", [])),
        "failures": failures,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report saved to {path}")


if __name__ == "__main__":
    test_set = load_test_set()
    print(f"Loaded {len(test_set)} test questions")
    print("Run pipeline.py first to generate answers, then call evaluate_ragas().")
