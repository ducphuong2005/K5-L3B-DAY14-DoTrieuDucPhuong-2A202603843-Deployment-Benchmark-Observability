# Benchmark & Observability Report — Day 14

- **Họ tên** Đỗ Triệu Đức Phương (MSV 2A202603843)
- **Ngày chạy CP7** 26/11/2026
- **Môi trường CP7** MacBook Pro, macOS, Python 3.12.12, Uvicorn. Agent v1 chạy trên `127.0.0.1:8011`, agent v2 trên `127.0.0.1:8012`.
- **Ngày chạy CP8** 26/11/2026
- **Môi trường CP8** Cùng MacBook Pro, chạy qua Docker Desktop. Nginx nhận request local trên cổng `8080`.

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

- [x] [Dashboard Grafana khi đang có tải](screenshots/grafana-dashboard.png)
- [x] [Trace chậm trong Jaeger](screenshots/jaeger-slow-trace.png)
- [x] [Trace lỗi trong Jaeger với event `exception` mở rộng](screenshots/jaeger-error-trace.png)
- [x] [Trang Alerts của Prometheus với hai alert cùng firing](screenshots/prometheus-alert-firing.png)

Ở mốc **17:14:37 (GMT+7)**, Locust Web UI chạy **30 users**, ramp-up **5 users/giây**, với **2 agent**. Các giá trị dưới đây lấy từ Prometheus tại thời điểm đó bằng cùng biểu thức PromQL với Grafana.

| Chỉ số | Thực đo |
|---|---:|
| Traffic `/ask` | 17.55 req/s |
| p95 latency `/ask` | 951.0 ms |
| Latency trung bình `/ask` | 289.4 ms |
| Tỷ lệ HTTP 5xx của agent | 0.83% |
| Throughput từng instance | 8.71 và 8.84 req/s |
| Input tokens | 1290.98 token/s |
| Output tokens | 685.69 token/s |

Khoảng cách giữa p95 và trung bình cho thấy một nhóm request chạy chậm hơn phần lớn lượt gọi. Hai instance nhận lượng request gần bằng nhau trong mẫu này. Input tokens cao hơn vì prompt của v2 gồm chỉ dẫn hệ thống, câu hỏi và đoạn context truy xuất được. Gọi `GET http://127.0.0.1:8080/metrics` qua Nginx trả `404`. Prometheus scrape từng agent trực tiếp trên mạng Docker. [Dashboard đã provision](06-lab-complete/benchmark-observability/production/grafana/dashboards/agent-overview.json) · [Cấu hình Nginx](06-lab-complete/benchmark-observability/production/nginx/nginx.conf)

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2`, giữ slow rate 3% | `AgentHighErrorRate` | 116.0 s | Error rate, thực đo 19.46% |
| B | `MOCK_SLOW_RATE=0.3`, giữ error rate 20% | `AgentHighLatencyP95`, cùng firing với `AgentHighErrorRate` | 76.8 s kể từ khi áp dụng B | Latency p95, thực đo 1891.1 ms |

Lệnh `promtool test rules` báo `SUCCESS`. Hai thí nghiệm giữ 30 Locust users. A bắt đầu lúc **17:14:41 (GMT+7)**. Tỷ lệ lỗi cần vượt 5% trong ít nhất một phút tính từ lúc rule sang `pending`, còn 116.0 s tính từ lúc bắt đầu đổi cấu hình. B bắt đầu lúc **17:16:41 (GMT+7)**. Alert latency đã ở trạng thái `pending` từ A, nên 76.8 s là thời gian quan sát thêm kể từ lúc áp dụng B. Rule latency vẫn yêu cầu p95 trên 1 giây trong hai phút. Prometheus được kiểm tra mỗi hai giây để ghi lần đầu quan sát thấy trạng thái `firing`. [Alert rules](06-lab-complete/benchmark-observability/production/prometheus/alert_rules.yml)

Nếu đổi sang v1 làm giảm chất lượng câu trả lời, chạy eval định kỳ trên golden dataset và so với phiên bản đã duyệt. Gate CP7 đã phát hiện 20 câu regression khi thử v1 với baseline của v2. Có thể theo dõi accuracy và cost/câu đúng theo phiên bản để phát hiện suy giảm mà các alert hạ tầng không thấy.

### 4.3 Debug bằng trace

**Trace chậm, HTTP `200`.** `trace_id` là `7b9b9c85aca6c146b126d70eb4e74ea5`. Span gốc `POST /ask` mất **2782.3 ms**. Trong hai bước xử lý con, `chat mock-llm-small` lâu nhất với **1695.2 ms**, khoảng **60.9%** tổng thời gian request. `agent.retrieve_context` mất **107.6 ms**. Dòng ứng dụng có cùng `trace_id` ghi thời gian mock LLM là **1686.6 ms**, theo bộ đo bên trong lời gọi mock.

```json
{"ts":"2026-11-26T10:12:36.750545+00:00","level":"INFO","service":"observable-agent","instance":"14b08534bcbf","event":"llm_call","trace_id":"7b9b9c85aca6c146b126d70eb4e74ea5","span_id":"743a0588a72b449e","request_id":"ce596b8e1a51","model":"mock-llm-small","agent_version":"v2","input_tokens":37,"output_tokens":20,"cost_usd":0.000018,"llm_ms":1686.6}
```

**Trace lỗi, HTTP `503`.** `trace_id` là `8736f80a6692f38cb4314e68cafced15`. Span gốc mất **143.7 ms**. Span `chat mock-llm-small` mất **93.8 ms**, có trạng thái lỗi và event `exception` ghi `utils.mock_llm.LLMError`. Dòng log `llm_error` có cùng `trace_id`.

```json
{"ts":"2026-11-26T10:14:27.018659+00:00","level":"INFO","service":"observable-agent","instance":"14b08534bcbf","event":"llm_error","trace_id":"8736f80a6692f38cb4314e68cafced15","span_id":"014ce0a1f8a3aa4c","request_id":"9fb70bb96006","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Dùng mô hình `mock-llm-small`, `MOCK_SLOW_RATE=0.03` và `MOCK_ERROR_RATE=0.01` cho cả hai lượt. Locust tăng 10 user mỗi giây. Các số liệu bên dưới lấy từ dòng `POST /ask` trong mỗi CSV.

Lần chạy ban đầu cho thấy `docker compose run` có thể khởi động lại dependencies và đưa agent về số replica mặc định là 2. Lượt đo dùng để báo cáo chạy Locust với `--no-deps`, sau khi Nginx và agent sẵn sàng. Prometheus được dùng để kiểm tra số instance thực tế.

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 48.40 | 220 | 2300 | 4400 | 56/5725 (0.98%) |
| 3 | 41.68 | 240 | 3300 | 8000 | 59/4906 (1.20%) |

Trong hai lượt đo này, tăng từ 1 lên 3 instance làm RPS giảm từ 48.40 xuống 41.68 và p95 tăng từ 2300 lên 3300 ms. Cùng lúc đó, p95 của lời gọi mock LLM theo Prometheus gần như giữ nguyên, khoảng 197.7 ms và 198.2 ms ở hai mẫu lấy gần cuối lượt đo. Chênh lệch giữa latency đầu cuối và latency mock cho thấy cần xem thêm thời gian chờ ở client, Nginx, agent và tài nguyên Docker Desktop trước khi xác định nút thắt. Hai lượt chạy trên một máy chưa đủ để kết luận rằng thêm replica luôn làm hệ thống chậm hơn.

Lượt một instance chỉ ghi nhận lỗi `503` của mock. Lượt ba instance còn ghi nhận một `502` và một `504`. Bảng giữ các lỗi này trong tỷ lệ lỗi đầu cuối của Locust. [CSV 1 instance](benchmark-results/scale_1_stats.csv) · [CSV 3 instance](benchmark-results/scale_3_stats.csv) · [Chi tiết lỗi lượt 3](06-lab-complete/benchmark-observability/production/benchmark-results/scale_3_failures.csv)

---

## 6. Kết luận

1. Nên đọc p95 và p99 cùng với RPS, tỷ lệ lỗi và số instance thực tế. Thêm replica có thể cho kết quả khác dự kiến nếu các container cùng chia sẻ tài nguyên máy.
2. Metric tổng hợp cho biết triệu chứng. Trace và log có cùng `trace_id` giúp khoanh vùng thao tác chậm hoặc exception cụ thể.
3. Eval và alert hạ tầng đo hai mặt khác nhau của agent. Accuracy và regression cần một gate dựa trên câu trả lời mẫu.

Trong production, có thể thêm tỷ lệ `502/504` và latency đầu cuối từ Nginx hoặc probe bên ngoài. Chỉ số này phản ánh lỗi client thực sự nhận được, kể cả request chưa đến được agent.
