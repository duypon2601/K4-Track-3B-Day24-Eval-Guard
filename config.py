"""Shared configuration for K4 / Track 3B: Eval + Guardrail Stack."""

import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys / LLM provider ---
# Gemini được gọi qua endpoint tương thích OpenAI: OPENAI_API_KEY/OPENAI_BASE_URL trỏ sang
# Gemini để OpenAI(), langchain-openai (RAGAS) và NeMo engine=openai chạy không cần sửa.
# OPENAI_API_KEY ở đây nghĩa là "có LLM key", không khẳng định provider là OpenAI.
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

if GEMINI_API_KEY:
    LLM_PROVIDER = "gemini"
    LLM_MODEL = os.getenv("LLM_MODEL") or "gemini-3.5-flash-lite"
    LLM_RPM = int(os.getenv("LLM_RPM") or "12")  # free tier ~15 request/phút; 0 = không giới hạn
    OPENAI_API_KEY = GEMINI_API_KEY
    os.environ["OPENAI_API_KEY"] = GEMINI_API_KEY
    os.environ["OPENAI_BASE_URL"] = GEMINI_BASE_URL
    os.environ["OPENAI_API_BASE"] = GEMINI_BASE_URL
else:
    LLM_PROVIDER = "openai" if OPENAI_API_KEY else ""
    LLM_MODEL = os.getenv("LLM_MODEL") or "gpt-4o-mini"
    LLM_RPM = int(os.getenv("LLM_RPM") or "0")
HF_TOKEN = os.getenv("HF_TOKEN", "")  # Optional: for HuggingFace models

# --- Qdrant (same as Day 18) ---
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "lab24_production"
NAIVE_COLLECTION = "lab24_naive"

# --- Embedding (same as Day 18) ---
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024

# --- Chunking (same as Day 18) ---
HIERARCHICAL_PARENT_SIZE = 2048
HIERARCHICAL_CHILD_SIZE = 256
SEMANTIC_THRESHOLD = 0.85

# --- Search (same as Day 18) ---
BM25_TOP_K = 20
DENSE_TOP_K = 20
HYBRID_TOP_K = 20
RERANK_TOP_K = 3

# --- Paths ---
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT_DIR, "data")
FIXTURES_DIR = os.path.join(ROOT_DIR, "fixtures")
ARTIFACTS_DIR = os.path.join(ROOT_DIR, "artifacts")
TEST_SET_PATH = os.path.join(FIXTURES_DIR, "test_set_50q.json")
ANSWERS_PATH = os.path.join(ARTIFACTS_DIR, "answers_50q.json")
HUMAN_LABELS_PATH = os.path.join(FIXTURES_DIR, "human_labels_10q.json")
ADVERSARIAL_SET_PATH = os.path.join(FIXTURES_DIR, "adversarial_set_20.json")
CLEAN_SET_PATH = os.path.join(FIXTURES_DIR, "clean_set_8.json")
OUTPUT_SET_PATH = os.path.join(FIXTURES_DIR, "output_set_4.json")
GUARDRAILS_CONFIG_DIR = os.path.join(ROOT_DIR, "guardrails")
PAIR_QUESTION_IDS = (1, 5, 12, 21, 41)

# --- LLM Judge ---
GENERATION_MODEL = LLM_MODEL
JUDGE_MODEL = LLM_MODEL
GUARD_MODEL = LLM_MODEL  # ghi đè model `main` của guardrails/config.yml khi tạo NeMo
# Evaluator RAGAS có thể dùng model khác generation (hạn mức free tier tính riêng theo model).
EVALUATOR_MODEL = os.getenv("EVALUATOR_MODEL") or LLM_MODEL
RAGAS_CACHE_PATH = os.path.join(ROOT_DIR, ".cache", "ragas_scores.json")

# --- Guardrail latency budget ---
LATENCY_BUDGET_P95_MS = 500  # Full guard target; Task 12 currently measures input guards only.
PRESIDIO_LANGUAGE = "en"    # Presidio base language; custom VN recognizers added via PatternRecognizer
