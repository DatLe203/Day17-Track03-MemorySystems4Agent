# Báo cáo Phân tích Hệ thống Bộ nhớ (Memory Systems Analysis Report)

Báo cáo này phân tích hiệu năng, chi phí, và các trade-off giữa **Baseline Agent** (chỉ có bộ nhớ trong phiên) và **Advanced Agent** (kết hợp Persistent Profile và Compact Memory) dựa trên kết quả thực tế thu được từ benchmark.

---

## 1. Kết quả Benchmark Thực tế (Offline Mode)

### Standard Benchmark (data/conversations.json)
| Agent | Agent Tokens Only | Prompt Tokens Processed | Cross-session Recall | Response Quality | Memory Growth (bytes) | Compactions |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline Agent** | 1,307 | 12,906 | 0.00% | 10.00% | 0 B | 0 |
| **Advanced Agent** | 1,594 | 21,656 | 100.00% | 100.00% | 304 B | 0 |

### Long-Context Stress Benchmark (data/advanced_long_context.json)
| Agent | Agent Tokens Only | Prompt Tokens Processed | Cross-session Recall | Response Quality | Memory Growth (bytes) | Compactions |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline Agent** | 342 | 22,189 | 0.00% | 10.00% | 0 B | 0 |
| **Advanced Agent** | 554 | 10,368 | 100.00% | 100.00% | 379 B | 4 |

---

## 2. Phân tích Chi tiết & Đánh giá Trade-off

### A. Tại sao Advanced Agent có khả năng Recall vượt trội?
* **Cơ chế hoạt động:** `Baseline Agent` chỉ lưu trữ hội thoại hiện tại trong RAM (Session Memory). Khi chuyển sang thread mới (Recall Thread), Baseline hoàn toàn không có thông tin cũ và trả lời *"Tôi không biết"* (đạt 0% Recall).
* **Giải pháp của Advanced Agent:** Lưu trữ các thuộc tính định danh dài hạn (Tên, Nơi ở, Nghề nghiệp, Sở thích, Thói quen ăn uống) vào một file Markdown vật lý (`state/profiles/{user_id}.md`). Khi có câu hỏi ở bất kỳ thread mới nào, Advanced Agent sẽ đọc profile này và đưa vào system prompt, giúp khôi phục ngữ cảnh tức thì và đạt **100% Recall**.

### B. Chi phí ở hội thoại ngắn (Short Conversations)
* **Hiện tượng:** Ở Standard Benchmark, lượng `Prompt Tokens Processed` của Advanced Agent cao hơn Baseline (21,656 tokens so với 12,906 tokens).
* **Nguyên nhân:** Ở mỗi lượt hội thoại, Advanced Agent luôn phải load thêm toàn bộ nội dung file `User.md` (profile) và các thông tin đã compact vào prompt ngữ cảnh gửi cho LLM. Với các hội thoại ngắn dưới ngưỡng compaction, phần overhead của profile khiến chi phí prompt token tăng khoảng **60-70%** so với Baseline.
* **Trade-off:** Chấp nhận tốn token hơn ở hội thoại ngắn để đổi lấy khả năng nhớ thông tin ổn định qua nhiều session.

### C. Lợi thế vượt trội của Compact Memory ở hội thoại dài
* **Hiện tượng:** Ở Long-Context Stress Benchmark, `Prompt Tokens Processed` của Advanced Agent **giảm hơn một nửa** so với Baseline (10,368 tokens so với 22,189 tokens), trong khi số lần compact là **4**.
* **Nguyên nhân:** 
  - `Baseline Agent` giữ lại toàn bộ lịch sử trò chuyện dài. Mỗi lượt tiếp theo phải mang theo toàn bộ các tin nhắn cũ từ trước, làm chi phí prompt token tăng theo cấp số cộng.
  - `Advanced Agent` áp dụng cơ chế **Compact Memory**: khi tổng dung lượng hội thoại vượt ngưỡng `COMPACT_THRESHOLD_TOKENS` (800 tokens), nó sẽ tóm tắt (summarize) các tin nhắn cũ nhất (chỉ giữ lại số tin nhắn gần nhất cấu hình bởi `COMPACT_KEEP_MESSAGES` - mặc định là 4). Lịch sử cũ được nén thành một chuỗi tóm tắt ngắn gọn giúp lượng prompt token luôn nằm trong tầm kiểm soát.

### D. Rủi ro về sự phình to của Memory File & Cách kiểm soát
* **Rủi ro:** Nếu không giới hạn, file `User.md` của mỗi người dùng sẽ liên tục phình to khi có thêm thông tin mới, dẫn đến chi phí đọc/ghi tăng và vượt giới hạn token hệ thống.
* **Giải pháp kiểm soát đã cài đặt:**
  - Định dạng có cấu trúc chặt chẽ (Key-Value) giúp việc tìm kiếm nhanh và dung lượng cực kỳ nhỏ gọn (chỉ tăng **379 bytes** cho toàn bộ quá trình stress test cực dài).
  - Tách biệt rõ thông tin tĩnh dài hạn (lưu profile) và thông tin động ngắn hạn (nén trong summary hội thoại của thread).

---

## 3. Các Tính năng mở rộng (Bonus Features) đã triển khai

### 1. Xử lý xung đột dữ liệu (Conflict Handling & Verification)
* **Vấn đề giải quyết:** Khi người dùng thay đổi nơi ở (từ Huế chuyển sang Đà Nẵng) hoặc thay đổi công việc, nếu chỉ lưu dồn dập sẽ khiến profile chứa cả 2 thông tin mâu thuẫn, làm LLM bị nhiễu.
* **Giải pháp:** Khi cập nhật các trường thông tin cá nhân đơn lẻ như `Nơi ở`, `Nghề nghiệp`, hệ thống sẽ ghi đè giá trị mới nhất và xóa bỏ giá trị cũ.
* **Recall cải thiện:** Giúp đạt điểm tuyệt đối ở câu hỏi stress test khi người dùng đính chính nơi làm việc từ Huế sang Đà Nẵng.

### 2. Tích lũy sở thích thông minh (Accumulative Tech Interests)
* **Vấn đề giải quyết:** Khác với địa điểm hay nghề nghiệp (chỉ có 1 trạng thái hiện tại), sở thích kỹ thuật (như Python, AI, MLOps, Benchmark) là tập hợp tích lũy. Ghi đè sẽ làm mất đi các sở thích cũ đã nói từ trước.
* **Giải pháp:** Đối với trường `Sở thích / Mối quan tâm`, hàm `upsert_fact` sẽ tự động tách chuỗi và gộp danh sách (list merge) để tích lũy dần các từ khóa quan tâm của người dùng theo thời gian mà không bị ghi đè hay trùng lặp.

### 3. Màng lọc nhiễu câu hỏi (Query Guardrails)
* **Vấn đề giải quyết:** Tránh việc lưu nhầm các thông tin tạm thời hoặc câu hỏi từ người dùng vào profile vĩnh viễn (ví dụ: khi người dùng hỏi *"Mình đang ở Huế hay Hà Nội thế?"* thì không được phép lưu Hà Nội làm nơi ở mới).
* **Giải pháp:** Hàm `is_query_message` được cấu hình tinh vi để quét các mẫu câu hỏi phổ biến, đảm bảo chỉ trích xuất thông tin từ các câu khẳng định/cung cấp dữ liệu thực tế của người dùng.
