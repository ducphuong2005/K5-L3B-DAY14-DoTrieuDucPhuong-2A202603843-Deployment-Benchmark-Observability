# Benchmark & Observability Report — Day 14

- **Họ tên** Đỗ Triệu Đức Phương
- **MSV** 2A202603843
- **Ngày chạy CP7** 26/11/2026
- **Môi trường CP7** MacBook Pro, macOS, Python 3.12.12, Uvicorn. Agent v1 chạy trên `127.0.0.1:8011`, agent v2 trên `127.0.0.1:8012`.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Ngưỡng mặc định của load test. p95 là mốc mà khoảng 95% request thành công phản hồi trong khoảng thời gian đó. |
| Error rate `/ask` | ≤ 2% | Ngưỡng mặc định của load test. Tỷ lệ lỗi đo riêng để phản ánh cả request thất bại. |
| Accuracy trên golden dataset | 100% sau khi sửa knowledge base | Quality gate cuối yêu cầu đúng cả 23 câu và giữ các câu v2 đã trả lời đúng ở baseline. |

### Exercise 7.1 · Đọc và thêm metrics

| Loại | Ví dụ từ `GET /metrics` | Ý nghĩa |
|---|---|---|
| Counter | `http_requests_total{method="POST",route="/ask",status="200"}` | Tổng số request thành công đến `/ask` kể từ lúc tiến trình khởi động. |
| Gauge | `agent_in_flight_requests` | Số request đang xử lý, tăng khi request vào và giảm khi kết thúc. |
| Histogram | `http_request_duration_seconds` | Phân bố thời gian xử lý theo bucket, dùng được để ước tính percentile. |

Middleware dùng route template như `/ask` và gộp URL lạ vào `unmatched`. Nếu mỗi URL thô trở thành một giá trị label, hàng nghìn URL khác nhau sẽ tạo hàng nghìn chuỗi thời gian và tăng chi phí lưu trữ, bộ nhớ và truy vấn.

Thêm histogram `agent_question_length_chars` và ghi độ dài một lần cho mỗi câu hỏi hợp lệ vào `/ask`, trước khi gọi mock LLM. Trong lần thử với tiến trình v2 mới, gửi `Prometheus là gì?` rồi đọc các dòng sau từ `/metrics`.

```text
# TYPE agent_question_length_chars histogram
agent_question_length_chars_bucket{le="20.0"} 1.0
agent_question_length_chars_count 1.0
agent_question_length_chars_sum 17.0
```

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.21 | 187.3 | 223.7 | 1700.7 | 1.33% | PASS |
| 10 | 38.17 | 191.9 | 227.5 | 1707.6 | 3.00% | FAIL · error rate |
| 50 | 75.84 | 233.6 | 1385.0 | 1895.6 | 0.33% | FAIL · p95 |
| 100 | 41.41 | 952.7 | 5219.5 | 5484.3 | 1.00% | FAIL · p95 |

Mỗi lượt gửi 300 request với `MOCK_SLOW_RATE=0.03` và `MOCK_ERROR_RATE=0.01`. RPS tăng từ 4.21 lên 75.84 khi tăng concurrency từ 1 lên 50, rồi giảm còn 41.41 ở mức 100. Đồng thời p95 ở mức 100 tăng lên 5219.5 ms. Số liệu cho thấy thêm request đồng thời đã làm thời gian chờ tăng trong điều kiện thử này. Phép đo HTTP đầu cuối chưa xác định được phần chờ thuộc client hay server. Ở mức 10, lượt đo có 9 lỗi `503` nên vượt ngưỡng 2% dù đạt SLO p95.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 191.4 | 218.6 | 226.2 |
| 0.03 (mặc định) | 222.7 | 222.6 | 1679.8 |
| 0.1 | 334.4 | 1687.4 | 1716.1 |

Mỗi lượt gửi 300 request với concurrency 20 và giữ `MOCK_ERROR_RATE=0.01`. Khi tỷ lệ chậm tăng từ 0 lên 3%, p99 tăng từ 226.2 lên 1679.8 ms, trong khi p95 vẫn quanh 220 ms và trung bình tăng 31.3 ms. Khi tỷ lệ chậm đạt 10%, p95 lên 1687.4 ms. p99 nhạy với nhóm request chậm hiếm gặp. p95 hữu ích để đặt mục tiêu cho phần lớn request, còn trung bình làm tác động của nhóm chậm bị pha loãng.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100% (23/23) |
| Avg tokens / câu | 56.8 | 108.8 | 114.1 |
| Tổng cost (USD) | 0.000400 | 0.000758 | 0.000795 |
| Cost / câu đúng (USD) | 0.00040035 | 0.00003607 | 0.00003455 |
| p95 thời gian phản hồi (ms) | 187.7 | 226.1 | 213.8 |
| Quality gate | FAIL (ngưỡng 80%) | PASS (ngưỡng 80%) | PASS (ngưỡng 100%, 0 regression) |

Hai câu v2 trả lời sai ban đầu và phần tài liệu đã bổ sung.

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm tài liệu về JWT, gồm chữ ký, hạn dùng và cách phân biệt với API key. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm tài liệu về cách Kubernetes HPA dùng chỉ số tài nguyên và custom metrics để điều chỉnh số Pod. |

Eval dùng cùng 23 câu và tắt lỗi, lượt chậm ngẫu nhiên của mock ở cả hai phiên bản. V2 sau khi sửa dùng 114.1 token/câu và có p95 213.8 ms, cao hơn 56.8 token/câu và 187.7 ms của v1 trong lượt đo này. Nhờ trả lời đúng 23 câu, chi phí trên mỗi câu đúng giảm từ 0.00040035 xuống 0.00003455 USD, tương đương khoảng 11.6 lần. Mức giảm p95 giữa hai lần chạy v2 có thể chịu ảnh hưởng của jitter và chỉ dựa vào 23 lần gọi mỗi lượt.

Các phép đo và eval được lưu trong [10 báo cáo JSON của CP7](06-lab-complete/benchmark-observability/develop/reports/).

### Quality gate trong CI

Sau khi khởi động agent v2 local và đợi `/health` trả `200`, CI chạy từ thư mục `develop` với `MOCK_ERROR_RATE=0` trên agent để tránh lỗi ngẫu nhiên của mock.

```zsh
python eval/run_eval.py --url http://127.0.0.1:8012 --min-accuracy 0.85 \
  --baseline reports/eval_v2_fixed.json
```

Script trả mã thoát `1` nếu accuracy dưới 85% hoặc có câu từ đúng thành sai so với baseline đã duyệt. Cấu hình job này làm status check bắt buộc trên nhánh chính để GitHub chặn merge khi job thất bại. Kiểm tra thực tế với v1 và baseline v2 ban đầu trả mã thoát `1`, với 20 câu regression. Lần xác minh v2 sau khi sửa dùng ngưỡng `1.0` và cùng baseline v2 ban đầu, trả mã thoát `0` với 0 regression.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [ ] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [ ] Một trace lỗi trong Jaeger (có event `exception`)
- [ ] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | | | |
| B | `MOCK_SLOW_RATE=0.3` | | | |
| C | `LLM_MODEL=mock-llm-large` | | | |
| D | `docker pause` 1 instance | | | |
| E | `AGENT_VERSION=v1` | | | |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

...

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: ...
- Tổng thời gian: ... ms
- Span chiếm nhiều thời gian nhất: ... (... ms, ...%)
- Dòng log tương ứng (grep theo `trace_id`):

```json

```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | | | | | |
| 3 | | | | | |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

...

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. ...
  2. ...
  3. ...
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

...
