# Đánh giá LLM Judge Phase B

Nhóm: ThaiDuy

Người phụ trách: Trần Nguyễn Thái Duy – 2A202602991

Nguồn: `artifacts/judge_results.json`; run timestamp: 2026-10-12T08:25:24.751415+00:00.
Models generation/judge: generation = gemini-3.5-flash-lite; judge = gemini-3.5-flash-lite
(cùng một model Gemini, gọi qua endpoint tương thích OpenAI, temperature=0).

## Năm cặp A/B và hai lượt

Nguồn cố định: A từ artifacts/answers_50q.json:answer; B từ
fixtures/human_labels_10q.json:model_answer; reference từ fixtures/test_set_50q.json:ground_truth.
Ids: 1, 5, 12, 21, 41. Không đổi nguồn sau khi xem kết quả judge.

Winner và scores của lượt 2 trong bảng đã được quy về A/B gốc.

| id | Candidate A (pipeline) | Candidate B (supplied) | winner_pass1 | winner_pass2 | final_winner | position_consistent | scores lượt 1 | scores lượt 2 |
|---|---|---|---|---|---|---|---|---|
| 1 | Dựa trên context, nhân viên được nghỉ **3 ngày làm việc** khi kết hôn. | Nhân viên được nghỉ 3 ngày làm việc có lương khi kết hôn. | B | tie | tie | không | A=0.8, B=1.0 | A=0.85, B=0.9 |
| 5 | Tổng Giám đốc (CEO) | Cần Giám đốc phòng ban phê duyệt. | A | A | A | có | A=1.0, B=0.0 | A=1.0, B=0.0 |
| 12 | 1 tháng lương | Nhân viên được thưởng Tết tối thiểu 1 tháng lương. | tie | tie | tie | có | A=1.0, B=1.0 | A=1.0, B=1.0 |
| 21 | Dựa trên context: - Nhân viên có 9 năm thâm niên được **18 ngày phép** (15 + 3). - Không tìm thấy thông tin về mức lương hoặc khoảng lương của nhân viên này trong context. | Được nghỉ 18 ngày phép (15 cơ bản + 3 thâm niên). Lương Senior từ 20 đến 35 triệu. | B | B | B | có | A=0.5, B=1.0 | A=0.5, B=1.0 |
| 41 | Dựa trên context: - Nhân viên chính thức theo chính sách năm 2024 được hưởng **15 ngày phép năm** có lương. - Nhân viên chính thức theo chính sách năm 2023 được hưởng **12 ngày phép năm** có lương. | Nhân viên được nghỉ 12 ngày phép năm. | A | A | A | có | A=0.9, B=0.3 | A=0.9, B=0.2 |

Reasoning của judge. Lượt 2 judge nhìn thấy thứ tự đã hoán đổi, nên chữ “Answer A” trong
reasoning lượt 2 là candidate B gốc và ngược lại; JSON giữ nguyên văn judge viết.

| id | reasoning lượt 1 (thứ tự A/B) | reasoning lượt 2 (thứ tự B/A, nhãn theo góc nhìn judge) |
|---|---|---|
| 1 | Answer B đầy đủ hơn Answer A khi bao gồm ý 'có lương', khớp sát với reference. | Cả hai câu trả lời đều nêu chính xác số ngày nghỉ là 3 ngày làm việc khi kết hôn theo reference. Answer A đầy đủ hơn một chút về ý 'có lương', trong khi Answer B nêu đúng trọng tâm nhưng thiếu từ 'có lương'. Tuy nhiên, cả hai đều tương đương về chất lượng cơ bản so với reference. |
| 5 | Answer A chính xác theo reference (trên 50 triệu cần Tổng Giám đốc phê duyệt, trong khi 55 triệu vượt mức này). Answer B sai đối tượng phê duyệt. | Answer B trả lời chính xác theo reference là đơn hàng trên 50 triệu cần Tổng Giám đốc (CEO) phê duyệt, trong khi Answer A sai hoàn toàn. |
| 12 | Cả hai câu trả lời đều nêu chính xác mức thưởng Tết tối thiểu là 1 tháng lương theo đúng reference. Mặc dù Answer A ngắn gọn và Answer B diễn đạt đầy đủ hơn một chút, cả hai đều đáp ứng tốt yêu cầu câu hỏi và không chứa thông tin sai lệch. | Cả hai câu trả lời đều nêu chính xác con số '1 tháng lương' theo reference, ngắn gọn và không chứa thông tin sai lệch. |
| 21 | Answer B trả lời đầy đủ cả hai ý của câu hỏi (số ngày phép và khoảng lương dựa trên reference), trong khi Answer A bỏ sót thông tin về lương. | Answer A trả lời chính xác và đầy đủ cả hai ý về số ngày phép và mức lương theo đúng reference. Answer B bỏ sót thông tin về mức lương. |
| 41 | Answer A đã cung cấp đúng số ngày phép theo chính sách v2024 hiện hành (15 ngày) và có đề cập thêm chi tiết, trong khi Answer B trả lời theo chính sách cũ (v2023) là 12 ngày. | Answer B trả lời đúng theo chính sách phiên bản v2024 hiện hành (15 ngày) và có đề cập đến chính sách cũ (12 ngày) như trong reference, trong khi Answer A chỉ đưa ra con số cũ của năm 2023. |

Position bias count/rate: 1/5 = 0.2.
Verbosity win rate: 0.333; decisive cases: 3
(A thắng và A dài hơn: 1; B thắng và B dài hơn: 0).

Case không nhất quán duy nhất là id 1. Hai answer cùng nêu đúng “3 ngày làm việc”; B có thêm
“có lương” như reference. Lượt 1 judge chọn B vì chi tiết này (0.8 so với 1.0). Lượt 2, khi B
đứng trước, judge vẫn chấm B cao hơn (0.9 so với 0.85 sau khi quy đổi) nhưng kết luận “tương
đương” và trả tie. Tức là thứ tự không làm đảo người thắng, chỉ làm judge đổi ngưỡng giữa
“hơn một chút” và “tie” trên một khác biệt nhỏ. Đây là dấu hiệu judge không ổn định ở các cặp
sát nhau, chưa đủ để kết luận judge thiên vị vị trí đầu hay vị trí sau; swap-and-average xử lý
đúng bằng cách hạ cặp này về tie.

Bốn cặp còn lại nhất quán và có lý do nội dung rõ: id 5 A đúng người phê duyệt (CEO) còn B sai;
id 41 A nêu bản v2024 hiện hành còn B trả lời theo v2023 đã hết hiệu lực; id 21 B trả lời đủ cả
phép và khung lương còn A nói không tìm thấy lương; id 12 hai answer cùng đúng nên tie.

Về độ dài: trong 3 cặp decisive, answer dài hơn chỉ thắng 1 lần (id 41, A dài 197 ký tự so với
37). Ở id 5 answer ngắn hơn thắng (A 19 ký tự), ở id 21 answer ngắn hơn thắng (B 82 so với 171).
Cả ba lần, bên thắng là bên đúng theo reference, nên tỷ lệ 0.333 không cho thấy judge ưu tiên câu
dài. Với id 41, A thắng vì đúng phiên bản, không phải vì dài; tuy nhiên A liệt kê cả hai phiên bản
mà không nói bản nào hiện hành, và judge không trừ điểm điều đó nhiều (0.9).

## Calibration đúng model_answer

Helper đánh giá đúng question/model_answer đang có trong fixtures/human_labels_10q.json;
không lấy answer mới của pipeline. Prompt chỉ nhận question, answer, reference.
Không gửi human_label, human_note hoặc phân bố nhãn human vào prompt.

| question_id | model_answer gốc | judge | reasoning của judge | human_label | agree |
|---|---|---|---|---|---|
| 1 | Nhân viên được nghỉ 3 ngày làm việc có lương khi kết hôn. | 1 | Answer trả lời đúng và đủ ý chính theo reference (nghỉ 3 ngày làm việc có lương khi kết hôn). Việc thiếu vế 'không trừ vào phép năm' không phải là ý thiết yếu bị bỏ sót làm sai lệch bản chất chính sách trả phép. | 1 | có |
| 5 | Cần Giám đốc phòng ban phê duyệt. | 0 | Answer sai so với reference. Thiết bị trị giá 55 triệu (trên 50 triệu) theo reference cần Tổng Giám đốc (CEO) phê duyệt, nhưng answer lại trả lời là Giám đốc phòng ban. | 0 | có |
| 12 | Nhân viên được thưởng Tết tối thiểu 1 tháng lương. | 1 | Answer đã trả lời chính xác và đầy đủ ý thiết yếu theo reference là thưởng Tết tối thiểu 1 tháng lương cho nhân viên chính thức từ 6 tháng trở lên. | 1 | có |
| 21 | Được nghỉ 18 ngày phép (15 cơ bản + 3 thâm niên). Lương Senior từ 20 đến 35 triệu. | 1 | Câu trả lời đáp ứng chính xác số ngày phép (18 ngày) và khoảng lương (20 đến 35 triệu) theo đúng dữ liệu trong reference. | 1 | có |
| 23 | Hoàn trả 25 triệu vì chưa đủ 1 năm cam kết. | 1 | Answer trả lời đúng và đầy đủ theo reference, xác định đúng số tiền hoàn trả là 25 triệu do nghỉ trước hạn cam kết 1 năm. | 1 | có |
| 29 | Trưởng phòng phê duyệt. Phạt 2% tháng trên 8 triệu. | 0 | Thiếu người phê duyệt là Kế toán trưởng và tính sai phí phạt (reference tính trên 15 ngày quá hạn là 80.000 VNĐ, answer ghi phạt 2% tháng trên toàn bộ 8 triệu không đúng thời hạn 15 ngày). | 0 | có |
| 33 | Phép: 19 ngày. Phụ cấp: 1.500.000 VNĐ/tháng. | 1 | Answer trả lời đúng và đủ số ngày phép năm (19 ngày) và tổng phụ cấp hàng tháng (1.500.000 VNĐ) theo đúng reference. | 1 | có |
| 41 | Nhân viên được nghỉ 12 ngày phép năm. | 0 | Câu trả lời sử dụng thông tin từ chính sách cũ v2023 (12 ngày) thay vì chính sách hiện hành v2024 (15 ngày cơ bản) theo yêu cầu của reference. | 0 | có |
| 46 | Nhân viên thử việc không được nghỉ phép năm và phải xin nghỉ không lương nếu cần. | 1 | Câu trả lời hoàn toàn chính xác theo reference, nêu rõ nhân viên thử việc không được nghỉ phép năm và phải xin nghỉ không lương, không bỏ qua phủ định hay điều kiện quan trọng. | 1 | có |
| 50 | Được, miễn là đảm bảo kết nối an toàn. | 0 | Reference cấm tuyệt đối việc sử dụng VPN cá nhân (như NordVPN), bắt buộc dùng VPN của công ty. Answer lại trả lời là được, vi phạm nghiêm trọng chính sách. | 0 | có |

Cohen’s κ: 1.0.
Observed/chance agreement và diễn giải: judge và human trùng 10/10 nhãn nên p_o = 1.0. Cả hai bên
đều có 6 nhãn 1 và 4 nhãn 0, nên p_e = 0.6 × 0.6 + 0.4 × 0.4 = 0.52. κ = (1.0 − 0.52) / (1 − 0.52) = 1.0,
mức “almost perfect” theo thang Landis–Koch, vượt ngưỡng bonus κ > 0.6.

## Giới hạn và cách dùng judge

Judge là gemini-3.5-flash-lite với prompt nhị phân được cấp sẵn trong
`src/experiment_support.py` và prompt pairwise trong `src/phase_b_judge.py`; mỗi lời gọi chạy một
lần ở temperature=0, không lặp để đo phương sai. κ = 1.0 đến từ chỉ 10 nhãn, và cả 4 câu human=0
đều sai rõ ràng (sai người phê duyệt, thiếu Kế toán trưởng, dùng bản v2023, đảo phủ định về VPN).
Bộ này không có câu “đúng một nửa” mơ hồ, nên κ cao ở đây không bảo đảm judge đồng thuận với
người ở các câu khó hơn; với 10 mẫu, chỉ cần lệch một nhãn là κ giảm xuống khoảng 0.8.

Không có case lệch với human trong lượt chạy này. Chỗ đáng kiểm tra nhất là id 1: judge cho nhãn 1
dù answer thiếu vế “không trừ vào phép năm” và tự giải thích đó không phải ý thiết yếu; human cũng
cho 1, nhưng đây là ranh giới mà một người chấm khác có thể chấm 0. Judge pairwise cũng dao động
đúng ở câu này (B thắng rồi tie).

Cách dùng đề xuất: dùng judge để sàng lọc và xếp hạng, luôn chạy hai lượt hoán đổi và coi cặp không
nhất quán là tie; định kỳ lấy mẫu để người chấm lại, ưu tiên các cặp tie/không nhất quán và các câu
có nhiều phiên bản chính sách. Generation và judge đang dùng cùng một model nên có rủi ro judge dễ
dãi với kiểu trả lời của chính nó (candidate A); muốn loại trừ cần chấm lại bằng một model khác.
Không xem nhãn của judge là đáp án tuyệt đối.
