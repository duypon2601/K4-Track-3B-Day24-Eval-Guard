"""Offline regressions for parent retrieval and cross-platform source provenance."""
import copy
import hashlib
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import setup_answers
from src.experiment_support import metadata, source_sha256, write_json
from src.report_contracts import validate_metadata

pytestmark = pytest.mark.support


@pytest.mark.parametrize("enriched", [False, True])
def test_build_pipeline_preserves_document_specific_raw_parents(monkeypatch, enriched):
    documents = [
        {"text": "Full leave policy table", "metadata": {"source": "leave.md"}},
        {"text": "Full allowance policy table", "metadata": {"source": "allowance.md"}},
    ]
    search = SimpleNamespace(index=Mock())
    reranker = object()

    def chunk_document(text, metadata):
        parent = SimpleNamespace(text=text, metadata={**metadata, "parent_id": "parent_0"})
        child = SimpleNamespace(text="child", metadata=metadata, parent_id="parent_0")
        return [parent], [child]

    def enrich(chunks):
        if not enriched:
            return []
        return [SimpleNamespace(enriched_text="generated enrichment", auto_metadata={
            "source": "wrong.md", "parent_id": "wrong", "parent_text": "generated parent",
            "topic": "HR",
        }) for chunk in chunks]

    monkeypatch.setitem(sys.modules, "src.m1_chunking", SimpleNamespace(
        load_documents=lambda: documents, chunk_hierarchical=chunk_document))
    monkeypatch.setitem(sys.modules, "src.m2_search", SimpleNamespace(HybridSearch=lambda: search))
    monkeypatch.setitem(sys.modules, "src.m3_rerank", SimpleNamespace(CrossEncoderReranker=lambda: reranker))
    monkeypatch.setitem(sys.modules, "src.m5_enrichment", SimpleNamespace(enrich_chunks=enrich))

    assert setup_answers.build_pipeline()[:2] == (search, reranker)
    indexed = search.index.call_args.args[0]
    for chunk, document in zip(indexed, documents):
        assert chunk["metadata"]["source"] == document["metadata"]["source"]
        assert chunk["metadata"]["parent_id"] == "parent_0"
        assert chunk["metadata"]["parent_text"] == document["text"]
        assert chunk["text"] == ("generated enrichment" if enriched else "child")
        if enriched:
            assert chunk["metadata"]["topic"] == "HR"


def test_select_contexts_deduplicates_parents_without_losing_other_documents():
    results = [SimpleNamespace(text=f"leave child {index}", metadata={
        "source": "leave.md", "parent_id": "parent_0", "parent_text": "Full leave table",
    }) for index in range(6)]
    results.extend([
        SimpleNamespace(text="allowance child", metadata={
            "source": "allowance.md", "parent_id": "parent_0", "parent_text": "Full allowance table",
        }),
        SimpleNamespace(text="VPN child", metadata={"parent_text": "Full VPN policy"}),
    ])
    assert setup_answers.select_contexts(results, 3) == [
        "Full leave table", "Full allowance table", "Full VPN policy",
    ]


def test_select_contexts_handles_missing_and_empty_parent_metadata():
    results = [
        SimpleNamespace(text="context"),
        SimpleNamespace(text="context", metadata=None),
        SimpleNamespace(text="other context", metadata={"parent_text": "   "}),
        SimpleNamespace(text="   ", metadata={}),
    ]
    assert setup_answers.select_contexts(results, 3) == ["context", "other context"]


@pytest.mark.parametrize("top_k", [0, -1])
def test_select_contexts_rejects_nonpositive_limits(top_k):
    with pytest.raises(ValueError, match="positive"):
        setup_answers.select_contexts([], top_k)


def test_run_query_reranks_more_children_and_generates_from_raw_parents(monkeypatch):
    from src import llm
    monkeypatch.setattr(llm, "get_rate_limiter", lambda: None)
    monkeypatch.setattr(setup_answers, "RERANK_CANDIDATES", 10)
    candidates = [SimpleNamespace(text=f"child {index}", score=.8, metadata={
        "parent_text": f"raw parent {index // 3}",
    }) for index in range(10)]
    search = SimpleNamespace(search=Mock(return_value=candidates))
    reranker = SimpleNamespace(rerank=Mock(return_value=candidates))
    client = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(choices=[
        SimpleNamespace(message=SimpleNamespace(content="partial grounded answer")),
    ])
    answer, contexts, mode, model = setup_answers.run_query("multi-part question", search, reranker, 3, client)
    assert reranker.rerank.call_args.kwargs["top_k"] == 10
    assert contexts == ["raw parent 0", "raw parent 1", "raw parent 2"]
    assert answer == "partial grounded answer"
    assert mode == "llm"
    assert model == setup_answers.GENERATION_MODEL
    messages = client.chat.completions.create.call_args.kwargs["messages"]
    assert messages[0]["content"] == setup_answers.GENERATION_SYSTEM_PROMPT
    assert "raw parent 0" in messages[1]["content"]
    assert "child 0" not in messages[1]["content"]


def test_run_query_empty_rerank_keeps_top_three_search_fallback(monkeypatch):
    import config
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    candidates = [SimpleNamespace(text=f"child {index}", score=.8, metadata={
        "parent_text": f"raw parent {index}",
    }) for index in range(5)]
    search = SimpleNamespace(search=lambda question: candidates)
    reranker = SimpleNamespace(rerank=lambda question, docs, top_k: [])
    answer, contexts, mode, model = setup_answers.run_query("Q", search, reranker, 4)
    assert contexts == ["raw parent 0", "raw parent 1", "raw parent 2"]
    assert answer == "raw parent 0"
    assert (mode, model) == ("extractive_fallback", None)


def test_run_query_no_context_does_not_call_generation():
    search = SimpleNamespace(search=lambda question: [])
    reranker = SimpleNamespace(rerank=lambda question, docs, top_k: [])
    client = Mock()
    answer, contexts, mode, model = setup_answers.run_query("Q", search, reranker, 3, client)
    assert contexts == []
    assert answer == "Không tìm thấy thông tin."
    assert (mode, model) == ("extractive_fallback", None)
    client.chat.completions.create.assert_not_called()


def test_metadata_accepts_crlf_checkout_with_original_lf_hash(tmp_path):
    source = tmp_path / "answers.json"
    original = b'{\n  "answer": "policy"\n}\n'
    source.write_bytes(original)
    report = {"metadata": metadata([source], models={
        "generation": ["generator-test"], "evaluator": [], "judge": [], "guard": [],
    })}
    assert report["metadata"]["source_sha256"][source.name] == hashlib.sha256(original).hexdigest()
    source.write_bytes(original.replace(b"\n", b"\r\n"))
    assert source_sha256(source) == hashlib.sha256(original).hexdigest()
    validate_metadata(report, [source])
    regenerated = metadata([source], models=report["metadata"]["models"])
    assert regenerated["source_sha256"] == report["metadata"]["source_sha256"]


@pytest.mark.parametrize("changed", [b'{\n  "answer": "different"\n}\n', b'{\n "answer": "policy"\n}\n'])
def test_metadata_still_rejects_content_or_whitespace_changes(tmp_path, changed):
    source = tmp_path / "answers.json"
    source.write_bytes(b'{\n  "answer": "policy"\n}\n')
    report = {"metadata": metadata([source], models={
        "generation": ["generator-test"], "evaluator": [], "judge": [], "guard": [],
    })}
    original_report = copy.deepcopy(report)
    source.write_bytes(changed)
    with pytest.raises(ValueError, match="Stale experiment source"):
        validate_metadata(report, [source])
    assert report == original_report


def test_json_export_always_uses_lf(tmp_path):
    destination = tmp_path / "results.json"
    write_json(destination, {"answer": "policy", "contexts": ["raw parent"]})
    content = destination.read_bytes()
    assert b"\r\n" not in content
    assert content.endswith(b"\n")
