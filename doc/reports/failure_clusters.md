# Phân tích lỗi Phase A

Nhóm: ThaiDuy

Người phụ trách: Trần Nguyễn Thái Duy – 2A202602991

Nguồn: `artifacts/ragas_50q.json`; run timestamp: 2026-10-12T10:32:06.469697+00:00.
Generation mode/fallback và điều kiện chạy: cả 50 answers có generation_mode = llm, không câu nào
rơi về extractive_fallback. Pipeline: chunk hierarchical (107 child chunks từ 26 file Markdown; hai
file PDF trong data/ là scan ảnh không có text layer nên bị bỏ qua), enrich từng chunk bằng LLM,
hybrid search BM25 + bge-m3 trên Qdrant v1.9.7, rerank bge-reranker-v2-m3 lấy top 3 làm contexts.
Models generation/evaluator: generation = gemini-3.5-flash-lite; evaluator =
BAAI/bge-m3, gemini-3.1-flash-lite (LLM chấm là gemini-3.1-flash-lite, embeddings cho
answer_relevancy là BAAI/bge-m3 chạy local). Evaluator khác model generation vì hạn mức free tier
500 request/ngày của gemini-3.5-flash-lite đã hết sau khi sinh answers và chạy Phase B/C.

## Điểm theo distribution

| Metric | factual (20) | multi_hop (20) | adversarial (10) |
|---|---|---|---|
| faithfulness | 0.933 | 0.784 | 1.000 |
| answer_relevancy | 0.844 | 0.738 | 0.773 |
| context_precision | 0.942 | 0.392 | 0.800 |
| context_recall | 0.875 | 0.687 | 0.717 |
| avg_score | 0.899 | 0.650 | 0.822 |

Trung bình cả 50 câu: faithfulness 0.887, answer_relevancy 0.788,
context_precision 0.693, context_recall 0.768, avg_score 0.784.

## Bottom 10 và nguyên nhân

Bảng lấy nguyên từ `bottom_10` của Task 3 trong JSON (diagnosis/suggested_fix do code Task 3 sinh).

| rank | id | question | distribution | avg_score | worst_metric | diagnosis | suggested_fix |
|---|---|---|---|---|---|---|---|
| 1 | 33 | Nhân viên Manager có thâm niên 12 năm: tổng phụ cấp hàng tháng và số ngày phép năm theo v2024 là bao nhiêu? | multi_hop | 0.1250 | faithfulness | LLM hallucinating: faithfulness=0.00 (faithfulness=0.00, answer_relevancy=0.00, context_precision=0.00, context_recall=0.50); câu multi-hop: cần ghép nhiều chunk/tài liệu, top-k nhỏ dễ thiếu một vế | Tighten system prompt, lower temperature |
| 2 | 22 | Nếu cần mua một chiếc laptop 30 triệu cho nhân viên mới, ai phê duyệt và cần gì từ phòng CNTT? | multi_hop | 0.3333 | answer_relevancy | Answer doesn't match question: answer_relevancy=0.00 (faithfulness=1.00, answer_relevancy=0.00, context_precision=0.00, context_recall=0.33); câu multi-hop: cần ghép nhiều chunk/tài liệu, top-k nhỏ dễ thiếu một vế | Improve prompt template |
| 3 | 6 | Thông tin lương thuộc cấp độ phân loại dữ liệu nào? | factual | 0.3750 | faithfulness | LLM hallucinating: faithfulness=0.00 (faithfulness=0.00, answer_relevancy=0.00, context_precision=1.00, context_recall=0.50); câu factual một bước: kiểm tra chunk chứa đúng con số có được lấy về không | Tighten system prompt, lower temperature |
| 4 | 27 | Nhân viên có thâm niên 7 năm theo v2024 được nghỉ bao nhiêu ngày phép? Nếu bị trừ thêm 4 ngày ốm không có giấy y tế thì còn lại bao nhiêu? | multi_hop | 0.3750 | answer_relevancy | Answer doesn't match question: answer_relevancy=0.00 (faithfulness=1.00, answer_relevancy=0.00, context_precision=0.00, context_recall=0.50); câu multi-hop: cần ghép nhiều chunk/tài liệu, top-k nhỏ dễ thiếu một vế | Improve prompt template |
| 5 | 39 | So sánh yêu cầu mật khẩu giữa policy v1.0 và v2.0 về độ dài tối thiểu, thời hạn đổi và MFA. | multi_hop | 0.3985 | context_precision | Too many irrelevant chunks: context_precision=0.00 (faithfulness=0.67, answer_relevancy=0.93, context_precision=0.00, context_recall=0.00); câu multi-hop: cần ghép nhiều chunk/tài liệu, top-k nhỏ dễ thiếu một vế | Add reranking or metadata filter |
| 6 | 35 | Nhân viên Junior P1 có lương cơ bản 12 triệu vừa vào thử việc: nhận lương bao nhiêu và phụ cấp gì tháng đầu tiên? | multi_hop | 0.4610 | context_precision | Too many irrelevant chunks: context_precision=0.00 (faithfulness=0.86, answer_relevancy=0.74, context_precision=0.00, context_recall=0.25); câu multi-hop: cần ghép nhiều chunk/tài liệu, top-k nhỏ dễ thiếu một vế | Add reranking or metadata filter |
| 7 | 49 | Theo chính sách nghỉ phép cũ (v2023), nhân viên được nghỉ bao nhiêu ngày? Còn chính sách nào đang có hiệu lực hiện tại? | adversarial | 0.5342 | context_precision | Too many irrelevant chunks: context_precision=0.00 (faithfulness=1.00, answer_relevancy=0.80, context_precision=0.00, context_recall=0.33); câu adversarial: corpus có bản cũ/mới và phủ định, dễ lấy hoặc trả lời theo bản hết hiệu lực | Add reranking or metadata filter |
| 8 | 37 | Nhân viên tự ý xóa malware khỏi máy và chia sẻ thông tin sự cố này trên Slack nội bộ. Vi phạm những chính sách nào cụ thể? | multi_hop | 0.5561 | context_precision | Too many irrelevant chunks: context_precision=0.00 (faithfulness=1.00, answer_relevancy=0.72, context_precision=0.00, context_recall=0.50); câu multi-hop: cần ghép nhiều chunk/tài liệu, top-k nhỏ dễ thiếu một vế | Add reranking or metadata filter |
| 9 | 30 | So sánh quyền lợi bảo hiểm giữa nhân viên thử việc và nhân viên chính thức. | multi_hop | 0.5979 | context_precision | Too many irrelevant chunks: context_precision=0.00 (faithfulness=1.00, answer_relevancy=0.89, context_precision=0.00, context_recall=0.50); câu multi-hop: cần ghép nhiều chunk/tài liệu, top-k nhỏ dễ thiếu một vế | Add reranking or metadata filter |
| 10 | 21 | Một nhân viên Senior có 9 năm thâm niên được nghỉ bao nhiêu ngày phép năm và lương trong khoảng nào? | multi_hop | 0.6049 | context_precision | Too many irrelevant chunks: context_precision=0.00 (faithfulness=1.00, answer_relevancy=0.92, context_precision=0.00, context_recall=0.50); câu multi-hop: cần ghép nhiều chunk/tài liệu, top-k nhỏ dễ thiếu một vế | Add reranking or metadata filter |

Nhãn diagnosis ở bảng trên suy máy móc từ worst_metric. Đọc lại answer, contexts và reference của
từng câu thì 10 câu rơi vào ba nhóm lỗi, và nhãn “LLM hallucinating” ở id 33 và id 6 là sai:

**Nhóm 1 — retrieval thiếu một vế của câu multi-hop (id 33, 22, 27, 21, 35, 30, 37, 39).** Top 3
contexts chỉ phủ một tài liệu trong khi câu hỏi cần hai. Id 33 hỏi phụ cấp và phép năm của Manager:
cả ba contexts đều từ chính sách nghỉ phép v2024, không có chunk phụ cấp nào, nên model trả “Không
tìm thấy” cho cả câu dù vế phép năm trả lời được. Id 21 cùng kiểu: contexts có ví dụ “9 năm thâm
niên được 18 ngày” nhưng không có bảng lương, answer đúng vế phép và nói thẳng không thấy lương.
Id 22: chunk bảng thẩm quyền phê duyệt được lấy về nhưng chỉ chứa dòng “dưới 5 triệu”, các dòng
5–50 triệu nằm ở chunk kế tiếp không lọt top 3; context thứ ba lại là chính sách đào tạo, không liên
quan. Id 39: lấy được đầu tài liệu mật khẩu v1.0 nhưng hai chunk v2.0 là phần MFA và passphrase, thiếu
chunk “tối thiểu 12 ký tự, đổi mỗi 120 ngày”. Ở nhóm này context_precision = 0 và context_recall
từ 0 đến 0.5; trừ id 33, faithfulness vẫn cao (0.67–1.0) vì model không bịa phần thiếu.

**Nhóm 2 — generation từ chối quá sớm (id 33, 27, 6).** Prompt “Nếu không có → nói 'Không tìm thấy'”
khiến model bỏ cả câu khi thiếu một phần hoặc khi phải suy luận một bước. Id 6: context thứ ba chứa
dòng bảng “3 / Bí mật / Dữ liệu khác...” và context đầu là phần bảo mật thông tin lương, nhưng model
không nối được “thông tin lương” với cấp “Bí mật” và trả “Không tìm thấy”. Id 27: contexts có 15 ngày
cơ bản của v2024 và quy định trừ phép khi nghỉ ốm không giấy, nhưng quy tắc thâm niên lấy về lại là
của bản 2023 (mỗi 5 năm), nên model không tính. Evaluator chấm câu “Không tìm thấy” không
nhất quán: faithfulness = 0 ở id 33 và id 6 nhưng = 1.0 ở id 27 và id 50, dù answer giống hệt nhau.
Câu từ chối không chứa claim nào nên điểm faithfulness của nó không có nghĩa; đây là lỗi từ chối,
không phải bịa. Vì vậy diagnosis “LLM hallucinating” của id 33 và id 6 nên đọc là “từ chối khi
context chưa đủ”.

**Nhóm 3 — lẫn phiên bản chính sách (id 49, và một phần id 27, 21).** Id 49 trả lời đúng (v2023: 12
ngày; hiện hành là v2024) nhưng thiếu “15 ngày, thêm 1 ngày mỗi 3 năm” của reference; contexts trộn
đầu tài liệu v2024, đầu tài liệu v2023 và phần thâm niên v2023. Reranker xếp chunk của bản cũ ngang
với bản mới vì hai bản gần như trùng từ ngữ.

## Matrix và nhóm yếu nhất

Mỗi câu được đếm một lần theo metric thấp nhất của chính nó; đây không phải số failure.

| worst_metric | factual | multi_hop | adversarial | tổng |
|---|---|---|---|---|
| faithfulness | 2 | 4 | 0 | 6 |
| answer_relevancy | 11 | 3 | 3 | 17 |
| context_precision | 3 | 10 | 3 | 16 |
| context_recall | 4 | 3 | 4 | 11 |

Nhóm yếu theo mean thấp nhất: multi_hop; mean: 0.650
(factual 0.899, adversarial 0.822).
Worst metric xuất hiện nhiều nhất: answer_relevancy; số câu: 17.

Hai con số này mô tả hai chuyện khác nhau. answer_relevancy là worst metric của 17 câu, nhưng 11
trong đó là câu factual có ba metric còn lại gần 1.0 và answer_relevancy khoảng 0.77–0.99: “thấp
nhất” ở đây chỉ là thấp tương đối, phần lớn do answer mở đầu bằng “Dựa trên context...” hoặc trả lời
cụt (“Tổng Giám đốc (CEO)”) nên câu hỏi sinh ngược lệch câu gốc. Nó không phải điểm yếu thật của
pipeline.

Điểm yếu thật là multi_hop với context_precision = 0.392, thấp hơn hẳn factual
(0.942) và adversarial (0.800); 10/20 câu multi_hop có worst metric là
context_precision và 8/10 câu bottom là multi_hop. Nguyên nhân là top_k = 3 với child chunk 256 ký
tự: một câu cần hai tài liệu chỉ còn một đến hai ô cho mỗi tài liệu, và bảng bị cắt giữa chừng.

Đề xuất sửa, theo thứ tự ưu tiên, và cách kiểm tra:

1. Trả parent chunk (2048 ký tự) thay vì child sau khi rerank, và tăng số ứng viên rerank lên 10
   rồi gom về 3–4 parent. Kỳ vọng context_recall và context_precision của multi_hop tăng; id 22 và
   id 39 phải có đủ bảng thẩm quyền và phần yêu cầu mật khẩu v2.0.
2. Tách câu hỏi nhiều vế thành các truy vấn con trước khi search, mỗi vế giữ ít nhất một context.
   Kiểm tra trên id 33, 21, 35, 30.
3. Sửa prompt generation: trả lời phần có trong context và nói rõ phần nào thiếu, thay vì “Không tìm
   thấy” cho cả câu; bỏ câu dẫn “Dựa trên context”. Kiểm tra bằng số answer có “Không tìm thấy” (hiện là 6:
   từ chối cả câu ở id 6, 27, 33, 50; từ chối một vế ở id 21, 39) và answer_relevancy của factual.
4. Gắn metadata phiên bản/hiệu lực vào chunk và ưu tiên bản hiện hành khi rerank, vẫn giữ bản cũ
   trong corpus.

Sau mỗi thay đổi: chạy lại `python scripts/setup_answers.py --live` rồi
`python scripts/run_experiments.py --phase a --live` với cùng evaluator, so sánh mean từng
distribution và danh sách bottom 10 với bảng trên. Vì RAGAS dùng LLM chấm, chênh lệch nhỏ hơn
khoảng 0.03 trên 20 câu chưa nên coi là cải thiện.

## Bẫy adversarial và giới hạn

Mean adversarial (0.822) thấp hơn factual (0.899) nhưng cao hơn multi_hop (0.650),
và faithfulness của adversarial là 1.000. Điểm này không có nghĩa pipeline đã vượt bẫy. Đọc 10 answer:

- **Bẫy phiên bản, chưa xử lý được (id 41, 42, 44):** pipeline liệt kê cả hai bản mà không kết luận
  bản nào hiện hành. Id 44 trả “mỗi 90 ngày (phần quy định đầu tiên)” và “mỗi 120 ngày (phần tiếp
  theo)” như hai lựa chọn ngang nhau. Faithfulness vẫn 1.0 vì cả hai con số đều có trong contexts,
  nên RAGAS không bắt được lỗi này; chỉ context_recall/precision tụt xuống 0.5.
- **Bẫy phiên bản, xử lý đúng (id 43, 45, 49):** id 43 ghi rõ v2.0 hiện hành 12 ký tự, v1.0 cũ 8 ký
  tự; id 45 trả lời theo v2.0 (MFA bắt buộc).
- **Bẫy phủ định, xử lý đúng (id 46, 47, 48):** trả lời “Không” đúng với reference.
- **Bẫy phủ định, thất bại (id 50):** câu hỏi dùng VPN cá nhân khi WFH nhận “Không tìm thấy” dù
  context_precision = 1.0, tức chunk đúng đã được lấy về; đây là lỗi generation từ chối, và là lý do
  answer_relevancy = 0.

Duy nhất id 49 của nhóm adversarial nằm trong bottom 10. Như vậy điểm adversarial thấp hơn factual
chủ yếu đến từ context_recall (0.717) và các answer hai phiên bản, không chứng minh pipeline nhận ra
xung đột phiên bản; ngược lại 3/6 câu phiên bản cho thấy nó chưa nhận ra.

Giới hạn: chỉ 10 câu adversarial và 20 câu mỗi nhóm còn lại, chạy một lượt, không đo phương sai của
evaluator. Evaluator là gemini-3.1-flash-lite, một model nhỏ, chấm tiếng Việt qua prompt tiếng Anh
của RAGAS 0.1.22; answer_relevancy dùng strictness = 1 (một câu hỏi sinh ngược) vì endpoint Gemini
không hỗ trợ n lớn hơn 1, nên metric này nhiễu hơn mặc định. Một lần chạy trước đó với evaluator
gemini-3.5-flash-lite bị dừng ở khoảng 77% do hết quota và không được dùng trong báo cáo. Corpus thiếu
hai tài liệu PDF scan, không ảnh hưởng 50 câu hỏi này nhưng là lỗ hổng của index.

## Cải tiến sau baseline — Nguyễn Hồng Phi

Ngày 13/10/2026 triển khai bước cải tiến đầu tiên trong `scripts/setup_answers.py`: giữ raw
parent context của từng child, rerank 10 candidates rồi gom context trùng về tối đa 3 parent.
Parent mapping được tạo riêng cho từng tài liệu để parent_id giống nhau không lấy nhầm policy;
enrichment không được ghi đè source/parent metadata. Result không có parent vẫn dùng child text;
rerank rỗng vẫn fallback top 3 search results. Prompt generation mới trả lời từng phần có
bằng chứng và nêu phần thiếu, không suy đoán phần chưa retrieve được.

Đây là thay đổi mã đã có 13 regression cases mới và 12 smoke-runner cases; kiểm tra offline đạt
111 tests, 3 integration tests deselected và checker không còn failed checks. Các điểm, bottom 10,
contexts và models trong phần phân tích baseline phía trên vẫn thuộc artifacts của Duy. Chưa kết luận điểm
multi_hop tăng; query decomposition và ưu tiên phiên bản bằng metadata chưa được triển khai.

### Kiểm chứng live 3 câu — 13/10/2026

Chạy `scripts/run_rag_smoke.py --live --question-ids 22 33 39`, generation
`gemini-3.5-flash-lite`, evaluator `gemini-3.1-flash-lite`, embedding `BAAI/bge-m3`. Corpus được
enrich/index 107 chunks trên collection riêng `lab24_parent_smoke`; bốn artifacts baseline không
đổi. Lượt chạy có một lỗi parse JSON enrichment dùng fallback, không thấy lỗi 429; hai PDF scan
vẫn không có text layer và bị bỏ qua. Runner chấm lại baseline và improved cùng lượt; số dưới đây
được lấy từ `artifacts/smoke_3q.json`, status `complete`, scope `smoke_only_not_50q`.

| Câu | Mean baseline chấm lại | Mean improved | Delta |
|---|---:|---:|---:|
| 22 | 0.3333 | 0.9413 | +0.6080 |
| 33 | 0.1250 | 0.5507 | +0.4257 |
| 39 | 0.3985 | 0.6981 | +0.2995 |
| **Mean 3 câu** | **0.2856** | **0.7300** | **+0.4444** |

Đọc answer/context thực tế:
- Câu 22: parent chứa đủ bảng phê duyệt, answer xác định Director cho 30 triệu và xác nhận cấu
  hình từ CNTT; context recall tăng 0.3333 → 1.0. Answer chưa nhắc yêu cầu 3 báo giá trong reference.
- Câu 33: answer mới tính đúng 19 ngày phép thay vì từ chối toàn bộ; vẫn không retrieve được phụ
  cấp và chưa trả lời 1.500.000 VNĐ/tháng. Context precision vẫn 0, recall vẫn 0.5: prompt cải thiện
  việc trả lời phần có bằng chứng, chưa giải quyết retrieval đa ý.
- Câu 39: answer phân biệt đúng 8/12 ký tự và 90/120 ngày, không còn gán chu kỳ v2 cho v1;
  faithfulness tăng 0.6667 → 1.0, recall tăng 0 → 1.0. V1 không có mục MFA nên answer nói không
  tìm thấy, không suy đoán. Context precision vẫn 0 và answer relevancy giảm 0.9275 → 0.7922,
  vì vậy không diễn giải mọi metric đều tăng hoặc bỏ qua kiểm tra thủ công.

Kết quả này là tín hiệu tích cực cho ba câu yếu đã chọn, không chứng minh mean 50 câu tăng so với
0.784 hoặc không có regression ở factual/adversarial. Chỉ một lượt evaluator, chưa đo phương sai;
strictness answer relevancy vẫn 1. Chưa chạy lại Phase B/C. Ưu tiên tiếp theo là query decomposition
để lấy đủ context cho câu 33, rồi chạy đánh giá đầy đủ trước khi thay artifacts baseline.

Kế hoạch kiểm chứng: lưu riêng bản baseline, sinh lại 50 answers với pipeline mới, chạy Phase A
và Phase B bằng runner thật vì nguồn A trong pairwise đã đổi, rồi cập nhật artifacts và báo cáo
đồng bộ. So sánh mean/context precision/recall của multi_hop, kiểm tra thủ công các câu 22, 33, 39
và bảo đảm factual/adversarial không bị suy giảm. Không chỉnh tay điểm hoặc source hashes.
