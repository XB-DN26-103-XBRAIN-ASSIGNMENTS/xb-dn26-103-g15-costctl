# Reflections — costctl CLI Challenge

Dưới đây là phần trả lời phản hồi (reflections) cho các câu hỏi thảo luận của bài tập thực hành xây dựng `costctl` CLI.

---

### 1. Multi-account: To run `costctl` against 100 AWS accounts (not just yours), what changes? Cross-account roles? Profile loop? Aggregated CSV per account?

**Trả lời:**
Để mở rộng `costctl` quản lý được 100+ tài khoản AWS trong môi trường Enterprise, kiến trúc cần chuyển đổi như sau:
*   **Cơ chế Authentication (Cross-Account Roles):** 
    - Không sử dụng credentials tĩnh (Access/Secret Key) cho từng account. Thay vào đó, thiết lập một **Central/Hub IAM Role** tại tài khoản Admin, từ đó thực hiện `sts:AssumeRole` sang các **Target/Spoke IAM Roles** tại 100 tài khoản con.
    - Cấu hình này giúp đảm bảo nguyên tắc bảo mật tối giản (Least Privilege) và dễ dàng quản lý thu hồi quyền tập trung.
*   **Cơ chế thực thi (Concurrency & Profile Loop):**
    - Sử dụng `boto3.Session` động bằng cách truyền cấu hình credentials tạm thời sau khi Assume Role thay vì dùng profile tĩnh trong file `~/.aws/config`.
    - Triển khai vòng lặp quét đa luồng (Multi-threading/Async với `asyncio` hoặc `concurrent.futures`) để quét song song 100 accounts nhằm tối ưu thời gian phản hồi (giảm từ vài phút xuống vài giây).
*   **Tổng hợp dữ liệu (Aggregation):**
    - Thay vì in ra terminal đơn thuần, CLI sẽ xuất kết quả dạng một file báo cáo tổng hợp (như CSV, JSON hoặc đẩy thẳng lên S3/Athena). File này sẽ bổ sung thêm cột `AccountId` và `AccountName` để dễ dàng Group-by và Pivot Table khi phân tích.

---

### 2. `idle` vs Trusted Advisor: `idle` uses a 24h CPU window. Trusted Advisor uses 14 days. When do you trust `idle` more, when do you trust TA more?

**Trả lời:**
Sự khác biệt về khoảng thời gian (window) và cơ chế đánh giá dẫn đến các tình huống tin cậy khác nhau:
*   **Tin tưởng lệnh `idle` (24h window) hơn khi:**
    - **Môi trường phát triển/thử nghiệm (Dev/Sandbox/Staging):** Nơi các tài nguyên được tạo ra nhanh chóng và thường bị bỏ quên sau khi kết thúc ngày làm việc. Quét 24h giúp phát hiện nhanh và dọn dẹp ngay lập tức để tiết kiệm chi phí qua đêm hoặc cuối tuần mà không cần chờ tới 14 ngày.
    - **Sau đợt release hoặc migrate:** Khi muốn kiểm tra ngay xem hệ thống mới có chịu tải hay đang chạy không (hoạt động kiểm thử khẩn cấp).
*   **Tin tưởng AWS Trusted Advisor (14 days window) hơn khi:**
    - **Môi trường Production:** Nơi có tải công việc chạy theo chu kỳ tuần (ví dụ: các tác vụ Batch processing chạy định kỳ vào cuối tuần, các dịch vụ có lượng truy cập cao vào ngày lễ). Cửa sổ 24h có thể đánh giá sai một instance là idle nếu hôm đó là ngày thấp điểm, nhưng TA quét 14 ngày sẽ nhận diện chính xác các chu kỳ tải này.
    - **Độ chính xác cao cho kế hoạch dài hạn:** TA đánh giá nhiều chiều hơn (không chỉ CPUUtilization mà còn cả Network IO, I/O Operations), hạn chế tối đa việc tắt nhầm instance quan trọng đang chờ xử lý các tác vụ đột biến định kỳ.

---

### 3. `clean --apply` blast radius: If you accidentally ran `clean --tag Environment=dev --apply` in an account shared with another team, what would you have wanted in place to limit damage?

**Trả lời:**
Khi xảy ra sự cố chạy nhầm lệnh hủy tài nguyên hàng loạt ở tài khoản dùng chung, các cơ chế phòng vệ sau đây sẽ giúp giới hạn tối đa phạm vi ảnh hưởng (Blast Radius):
*   **Resource Termination Protection (Cấp độ tài nguyên):**
    - Luôn bật thuộc tính `DisableApiTermination` cho các EC2 instances quan trọng. Khi thuộc tính này bật, API `terminate_instances` sẽ bị từ chối thẳng thừng cho đến khi tắt thuộc tính này thủ công.
*   **IAM Permissions Boundaries & Tag-based Policies (Cấp độ IAM):**
    - Cấu hình IAM Policy giới hạn quyền xóa tài nguyên dựa trên Tag `Owner` hoặc `Team`. CLI chỉ được phép xóa tài nguyên nếu tag `Owner` trùng với IAM User/Role đang chạy lệnh.
    - Quy định chặt chẽ Policy: chỉ được xóa nếu có đồng thời cặp tag `Environment=dev` AND `Team=MyTeam`.
*   **Cơ chế xác thực CLI hai lớp (Multi-Factor / Safety Gates):**
    - Yêu cầu nhập đúng tên dự án/tên tag bằng tay để xác nhận hành vi hủy (ví dụ: yêu cầu người dùng gõ chữ `CONFIRM_DELETE_ENVIRONMENT_DEV` thay vì chỉ nhấn `y/N`).
    - Triển khai **Dry-run bắt buộc** và hiển thị cảnh báo đỏ nổi bật khi số lượng tài nguyên bị ảnh hưởng vượt quá một ngưỡng nhất định (ví dụ: > 5 instances).
*   **Hạ tầng sao lưu tự động (Backup & Infrastructure as Code):**
    - Hệ thống AWS Backup chụp snapshot định kỳ cho EBS volume.
    - Tài nguyên được định nghĩa bằng Terraform/CloudFormation để có thể Re-create (tái thiết lập) lại toàn bộ hệ thống chỉ trong vài phút.
