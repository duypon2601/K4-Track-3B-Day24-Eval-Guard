# Blueprint CI/CD cho RAG và guardrails

Nhóm: ThaiDuy

Người phụ trách: Trần Nguyễn Thái Duy – 2A202602991

Đây là **đề xuất CI/CD**, không phải workflow đã được triển khai/chạy.
Nguồn kết quả: artifacts/ragas_50q.json, judge_results.json, guard_results.json.
Run timestamp: 2026-10-12T08:29:41.829460+00:00; guard models: gemini-3.5-flash-lite.
Models generation/evaluator/judge từ A/B: generation = gemini-3.5-flash-lite (ragas_50q.json và
judge_results.json); evaluator = BAAI/bge-m3, gemini-3.1-flash-lite (ragas_50q.json);
judge = gemini-3.5-flash-lite (judge_results.json).

## Kiến trúc và failure action

Input → Presidio → NeMo input → RAG → NeMo output → response.
Request thực dừng sớm khi bị chặn; khác phép đo input layers chạy đủ hai tầng.

Luồng dữ liệu và hành động khi lỗi ở từng tầng:

| Tầng | Việc làm | Khi phát hiện vi phạm | Khi tầng lỗi/timeout |
|---|---|---|---|
| Presidio | Regex CCCD/CMND, số điện thoại VN, email; chạy local, khoảng 12ms | Chặn request, trả câu từ chối cố định; không gọi LLM | Fail-closed: từ chối, vì đây là tầng rẻ và không phụ thuộc mạng |
| NeMo input | Self-check bằng LLM: off-topic, jailbreak, prompt injection, xin dữ liệu người khác | Chặn, trả câu từ chối trong `guardrails/rails.co` | Fail-closed kèm thông báo thử lại; retry tối đa 2 lần |
| RAG | Hybrid search, rerank, generation chỉ từ contexts | Không có context phù hợp thì trả lời không tìm thấy | Trả thông báo lỗi tạm thời, không trả answer không có nguồn |
| NeMo output | Self-check answer: PII, lương cá nhân, credentials | Thay toàn bộ answer bằng câu từ chối | Fail-closed: không trả answer chưa kiểm tra |

Presidio chỉ tính ba loại entity của hợp đồng (VN_CCCD, VN_PHONE, EMAIL_ADDRESS). Các recognizer
mặc định tiếng Anh gắn nhãn PERSON lên gần như mọi câu tiếng Việt, kể cả 7/8 câu sạch; nếu chặn theo
chúng thì false positive sẽ gần 100%.

Log: ghi id request, tầng chặn, loại entity và độ trễ từng tầng; chỉ ghi văn bản đã anonymize của
Presidio (ví dụ `<VN_CCCD>`), không ghi input gốc khi có PII. Secrets: key LLM nằm trong `.env` ở
máy dev và trong secret store của CI khi triển khai, không vào source, log hay artifacts. Fallback:
nếu provider LLM bị rate limit hoặc hết quota, guard không tự chuyển sang “cho qua”; request bị từ
chối với mã lỗi riêng để phân biệt với block do chính sách.

## Phạm vi và số đo latency

Bắt buộc Task 12: **input_layers_sequential**, Presidio + NeMo input, không
short-circuit. Engines tạo trước đo; có hai warm-up thật không tính vào mẫu.
Percentile nội suy tuyến tính từ raw samples; tổng từ tổng từng sample.

Số mẫu timed: 20; warm-up: 2;
phương pháp: linear.

| Layer / scope | P50 ms | P95 ms | P99 ms | Tình trạng |
|---|---|---|---|---|
| Presidio | 11.8 | 13.8 | 14.5 | Đã đo Task 12 |
| NeMo input | 705.4 | 1063.8 | 1350.8 | Đã đo Task 12 |
| Input guard sequential | 718.8 | 1077.3 | 1363.2 | Đã đo Task 12, vượt target 500ms |
| RAG | chưa đo | chưa đo | chưa đo | Ngoài phạm vi bắt buộc |
| NeMo output | chưa đo | chưa đo | chưa đo | Ngoài phạm vi bắt buộc |
| Full guard / short-circuit request | chưa đo | chưa đo | chưa đo | Không suy từ input_guard_ms |

Input-layer budget target: 500ms; kết quả thực tế/budget_ok: P95 = 1077.3ms, latency_budget_ok = false.

Bottleneck là NeMo input: mỗi request gọi một lần LLM self-check qua mạng tới Gemini free tier,
P50 khoảng 705ms và có 2/20 mẫu trên 1 giây (1045ms và 1423ms). Presidio chỉ chiếm khoảng 1–2%
tổng. Ngay cả P50 của input guard (719ms) cũng vượt 500ms, nên vấn đề không phải vài mẫu chậm mà là
bản thân lời gọi LLM. Khi đo, giữa các mẫu có nghỉ 4.5 giây để không vượt 15 request/phút; khoảng
nghỉ nằm ngoài đoạn bấm giờ. Vì vậy số đo là độ trễ khi không có tải đồng thời, và chưa phản ánh
hàng đợi rate limit trong vận hành thật.

Kế hoạch đo phần chưa đo: dùng cùng cách (engine tạo trước, 2 warm-up, ít nhất 20 mẫu, perf_counter,
percentile tuyến tính). RAG: bấm giờ riêng search, rerank, generation trên 8 câu sạch. NeMo output:
bấm giờ `check_output_rail` trên answers thật của RAG. Full request: bấm giờ từ lúc nhận input đến
lúc trả response, có short-circuit, tách riêng mẫu bị chặn sớm và mẫu đi hết luồng, ghi timestamp
đầu/cuối mỗi tầng để cộng lại khớp tổng.

## CI gates đề xuất

- RAGAS faithfulness ≥0.75, avg_score ≥0.65 trên 50 câu.
- Attacks ≥18/20 cho CI đề xuất; clean 8/8 allowed; output cases đúng.
- Full guard P95 <500ms chỉ áp dụng sau khi thực sự đo full guard.

Mốc bắt buộc lab vẫn attacks ≥15/20; bonus ≥18/20 kèm clean controls đạt.

Workflow chưa được triển khai; repo không có file CI nào. Đề xuất hai job:

1. Mỗi pull request: `python -m pytest tests/ -q` (offline, không cần key) và
   `python scripts/check_lab.py` để validate schema, hash nguồn và phép tính của artifacts đã commit.
   Cả hai lệnh hiện đã trả mã khác 0 khi không đạt.
2. Hằng đêm hoặc trước release, có key trong secret store: chạy ba lệnh
   `python scripts/run_experiments.py --phase a/b/c --live` rồi một script gate mới đọc ba JSON và
   thoát mã 1 nếu vi phạm ngưỡng.

Script gate đó chưa tồn tại. `check_lab.py` hiện chỉ ép attacks ≥15/20, clean 8/8 và output đúng;
nó không kiểm tra ngưỡng RAGAS. Các biến như MIN_FAITHFULNESS=0.75, MIN_AVG_SCORE=0.65,
MIN_ATTACKS=18 chỉ là tên đề xuất và không tạo ra quality gate cho đến khi script gate đọc chúng.
So với số hiện tại: faithfulness 0.887 và avg_score 0.784 đạt hai ngưỡng RAGAS; attacks
20/20 đạt ngưỡng 18; gate latency chưa áp dụng được vì full guard chưa đo. Nên thêm gate theo
từng distribution, vì mean chung che mất multi_hop (0.650, sát ngưỡng 0.65).

Chạy live trong CI tốn khoảng 450 request LLM cho cả ba phase; với free tier 500 request/ngày mỗi
model thì chỉ chạy được một lần mỗi ngày, nên job 2 cần key trả phí hoặc tập câu hỏi rút gọn.

## Monitoring và cải tiến

Metric cần theo dõi trong vận hành và ngưỡng cảnh báo đề xuất:

| Metric | Cách lấy | Ngưỡng cảnh báo đề xuất |
|---|---|---|
| Tỷ lệ block theo tầng (presidio / nemo_input / nemo_output) | Đếm từ log quyết định của guard | Lệch quá 2 lần so với trung bình 7 ngày |
| False positive trên câu sạch | Chạy lại 8 câu clean hằng ngày và lấy mẫu request bị chặn cho người xem | Bất kỳ câu clean nào bị chặn |
| Độ trễ từng tầng P50/P95 | Timestamp đầu/cuối mỗi tầng | P95 tầng NeMo input trên 1500ms trong 15 phút |
| Lỗi provider (429, timeout) | Đếm theo mã lỗi | Trên 1% request |
| Chất lượng RAG | RAGAS trên 50 câu hằng đêm, tách theo distribution | faithfulness dưới 0.75 hoặc mean một distribution giảm quá 0.05 |
| Độ tin cậy judge | Người chấm lại 10 câu mẫu mỗi tháng, tính lại κ | κ dưới 0.6 |

Xử lý false positive: request bị chặn được ghi ở dạng đã anonymize kèm tầng chặn; người phụ trách
guard xem mẫu hằng tuần, câu chặn nhầm được thêm vào bộ clean controls trước khi sửa prompt
self-check, để lần sửa sau không tái phạm. Drift: khi đổi model, prompt hoặc corpus phải chạy lại cả
ba phase, vì hash nguồn trong metadata chỉ phát hiện dữ liệu đầu vào đổi, không phát hiện provider
đổi hành vi của cùng một tên model. Privacy: không lưu input gốc có PII; mẫu gửi cho người chấm đã
qua Presidio.

RAGAS mean/worst distribution: avg_score 0.784 trên 50 câu; yếu nhất là multi_hop với mean 0.650.
Cohen’s κ: 1.0.
Attacks passed: 20/20; clean false_positive_rate: 0.0.

Trong 20 attacks, Presidio chặn 4 câu có PII và NeMo input chặn 16 câu còn lại; cả 4 output
case đúng (2 answer sạch giữ nguyên, 2 answer nhạy cảm bị thay bằng câu từ chối).

Giới hạn của bằng chứng: 20 attacks, 8 câu sạch và 4 output là bộ nhỏ, cố định, và prompt
self-check được viết với đúng các loại tấn công này trong đầu; 20/20 không nói lên khả năng chống
tấn công mới. κ = 1.0 chỉ dựa trên 10 nhãn. Mỗi phase chạy một lượt, chưa đo độ dao động giữa các
lượt.

Cải tiến có thể kiểm tra:

1. Giảm độ trễ input guard: chạy Presidio và NeMo input song song, và thêm bộ lọc regex/embedding rẻ
   cho các mẫu jailbreak rõ ràng để chỉ gọi LLM khi chưa chắc. Kiểm tra bằng cách đo lại Task 12 và
   so P95 với 1077ms, đồng thời attacks vẫn ≥18/20 và clean 8/8.
2. Tăng chất lượng multi_hop: trả parent chunk và tách truy vấn nhiều vế (chi tiết trong
   failure_clusters.md). Kiểm tra bằng context_precision của multi_hop, hiện là 0.392.
3. Mở rộng bộ thử guard: thêm attacks diễn đạt lại, tiếng Việt không dấu, và câu sạch có từ nhạy cảm
   (ví dụ hỏi quy trình đổi mật khẩu) để đo false positive ngoài 8 câu hiện có.
4. Thêm Presidio vào output: hiện output chỉ dựa vào LLM self-check; quét CCCD/số điện thoại bằng
   regex trước khi gọi LLM vừa rẻ vừa không phụ thuộc phán đoán của model.
5. Chấm judge bằng model khác model generation và mở rộng bộ nhãn người lên vài chục câu có cả trường
   hợp đúng một phần, rồi tính lại κ.
