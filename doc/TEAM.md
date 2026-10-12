# Nhóm thực hiện K4 Track 3B

Tên nhóm: ThaiDuy

Repo chung: https://github.com/duypon2601/K4-Track-3B-Day24-Eval-Guard

Trưởng nhóm/người nộp: Trần Nguyễn Thái Duy – 2A202602991

Ngày lab/deadline áp dụng: lab ngày 12/10/2026, deadline 11:59 ngày 13/10/2026 theo README — Asia/Ho_Chi_Minh (UTC+07:00)

Commit dùng để chấm: HEAD của nhánh `main` tại thời điểm nộp; SHA của commit chứa toàn bộ mã,
artifacts và báo cáo được ghi ở mục “Cập nhật sau khi nộp” cuối file.

Mỗi nhóm nộp một repo. Nhóm này chỉ có một thành viên, làm toàn bộ ba phase.

## Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò / công việc thật | Bằng chứng |
|---|---|---|---|---|
| 1 | Trần Nguyễn Thái Duy | 2A202602991 | Tích hợp pipeline m1–m5; Phase A, B, C; chạy batch live; ba báo cáo | Lịch sử commit trên `main`; `artifacts/*.json`; `doc/reports/*.md` |

Người tích hợp/chạy batch/nộp link: Trần Nguyễn Thái Duy — chép và chỉnh m1–m5 từ repo Day 18 của
chính mình, chạy `setup_answers.py` và ba phase với `--live`, nộp link repo.

## Môi trường và chuẩn bị trước lớp

OS/Python/compiler: macOS 27.0.1 (Darwin 27.0.0, arm64); Python 3.11.16; Apple clang 21.0.0.
Virtualenv/dependencies/imports: `uv venv --python 3.11 .venv` rồi
`uv pip install -r requirements/requirements.txt -c requirements/constraints-core.txt`; `uv pip check`
báo “All installed packages are compatible”; import ragas 0.1.22, nemoguardrails 0.10.0, presidio,
spaCy 3.8 cùng `en_core_web_lg` thành công. Phải thêm `pyarrow<20` vào constraints vì bản pyarrow mới
nhất yêu cầu NumPy 2 và làm `datasets` không import được với numpy 1.26.4.
Models/Qdrant/50 answers đã chuẩn bị: Qdrant `qdrant/qdrant:v1.9.7` qua Docker Compose; BAAI/bge-m3 và
BAAI/bge-reranker-v2-m3 có sẵn trong cache HuggingFace; `artifacts/answers_50q.json` có 50 answers
(20/20/10), tất cả generation_mode = llm, không fallback. Hai file PDF trong `data/` là scan ảnh
không có text layer nên không vào index (26 file Markdown, 107 chunks).
Full NeMo 0.10.0 đã cài và chạy thật được. LLM là Gemini gọi qua endpoint tương thích OpenAI
(`GEMINI_API_KEY` trong `.env`), không phải OpenAI: generation, judge và guard dùng
gemini-3.5-flash-lite; evaluator RAGAS dùng gemini-3.1-flash-lite cùng embeddings bge-m3 local.

## INDIVIDUAL

### TranNguyenThaiDuy-2A202602991

- Phần được giao và phần thực tế đã làm: toàn bộ bài. Tích hợp `src/m1_chunking.py`–`m5_enrichment.py`
  và `src/llm.py`; sửa `m4_eval.py` để trả `evaluator_models`, chấm theo lô có cache và không thay NaN
  bằng điểm giả; Task 1–4 trong `src/phase_a_ragas.py`; Task 5–8 trong `src/phase_b_judge.py`;
  Task 9a–12 trong `src/phase_c_guard.py`; cấu hình Gemini trong `config.py` và
  `guardrails/config.yml`; ba báo cáo trong `doc/reports/`.
- Bằng chứng: commit trên `main`; `artifacts/answers_50q.json`, `ragas_50q.json`,
  `judge_results.json`, `guard_results.json`; `doc/reports/failure_clusters.md`, `bias_report.md`,
  `blueprint.md`.
- Cách kiểm tra: `python -m pytest tests/ -q` cho 86 passed (offline, mock); chạy thật
  `python scripts/setup_answers.py --live`, `python scripts/run_experiments.py --phase b --live`,
  `GUARD_PAUSE_S=4.5 python scripts/run_experiments.py --phase c --live --latency-samples 20`,
  `EVALUATOR_MODEL=gemini-3.1-flash-lite python scripts/run_experiments.py --phase a --live`; cuối
  cùng `python scripts/check_lab.py --with-tests`. Kết quả: RAGAS avg_score 0.784 (multi_hop yếu nhất,
  0.650); κ = 1.0; attacks 20/20, clean 8/8, output 4/4; input guard P95 = 1077ms, vượt target 500ms.
- Điều đã học: bốn metric RAGAS đo bốn chuyện khác nhau và worst_metric không tự cho biết nguyên
  nhân (câu “Không tìm thấy” bị gắn nhãn hallucination dù là lỗi từ chối); faithfulness = 1.0 ở nhóm
  adversarial không có nghĩa pipeline chọn đúng phiên bản chính sách. Pairwise phải chạy hai lượt
  hoán đổi rồi quy winner/scores về A/B gốc. Guard chỉ có ý nghĩa khi đo cùng clean controls: Presidio
  mặc định gắn PERSON lên hầu hết câu tiếng Việt sạch, nên phải giới hạn loại entity.
- Giới hạn/cách xử lý: key Gemini free tier giới hạn 15 request/phút và 500 request/ngày mỗi model.
  Thêm rate limiter chung (`src/llm.py`), nghỉ giữa các lời gọi guard ngoài đoạn bấm giờ
  (`GUARD_PAUSE_S`), và sửa một dòng trong `src/experiment_runners.py` để client judge nhị phân dùng
  rate limiter. Lượt RAGAS đầu với gemini-3.5-flash-lite dừng ở khoảng 77% vì hết quota ngày và bị bỏ;
  lượt nộp chấm lại cả 50 câu bằng gemini-3.1-flash-lite. NeMo 0.10 gọi nhầm endpoint completions với
  model không phải gpt và mặc định max_tokens = 3 làm Gemini trả rỗng (bị coi là block), đã sửa bằng
  cách truyền chat model tường minh và đặt max_tokens = 256. Latency vượt budget được ghi đúng số đo.
- Nguồn/AI hỗ trợ nếu có: dùng Claude Code (Anthropic) để viết mã các Task, tích hợp module Day 18,
  chạy các lệnh và soạn báo cáo. Mọi số trong báo cáo lấy từ bốn file JSON do runner sinh ra trong các
  lần chạy thật ở trên; kiểm chứng bằng `scripts/check_lab.py` (schema, hash nguồn, phép tính) và đọc
  lại answer/contexts của các câu bottom 10. Module m1–m5 lấy từ repo Day 18 của chính tác giả.

## Cập nhật sau khi nộp

Chưa có cập nhật sau deadline. Commit chứa toàn bộ mã, artifacts và báo cáo: `e5fbb23a9a7df2d93efcc17583229eac041cd7d3`
(commit kế tiếp trên `main` chỉ ghi SHA này vào TEAM.md).
