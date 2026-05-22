# Tổng Hợp Bài Tập Thực Hành: Xây Dựng costctl mini CLI

Tài liệu này tổng hợp chi tiết yêu cầu đề bài, phương pháp triển khai (cách làm), danh sách các file đã thực hiện, và kết quả đạt được của bài thực hành cá nhân/nhóm: **Xây dựng một `costctl` mini CLI**.

---

## 1. Yêu cầu đề bài (Requirements Overview)

### Mục tiêu
Xây dựng một Python CLI tên `costctl` để quản lý tài nguyên AWS (EC2, RDS, S3, EBS Volume) nhằm tối ưu hóa chi phí tương tự như các thao tác thủ công trong Tuần 6 (W6).

### Cấu trúc dự án có sẵn (Template)
- **Scaffolding:** `costctl.py` (Argparse entrypoint, dispatch).
- **Utility Helpers:** `commands/_common.py` (`parse_kv`, `tags_to_dict`, `tags_match`, `confirm`).
- **Specs:** 25 test cases viết bằng `pytest` + `moto` dùng để định nghĩa hành vi mong muốn.

### Các lệnh cần triển khai
*   **Required (Bắt buộc):** Triển khai lệnh `list` + ít nhất 2 trong các lệnh sau:
    - `cost --tag k=v --days N`
    - `terminate <type> --id <id>` (mặc định yêu cầu xác nhận `y/N`, có hỗ trợ `--force`)
    - `tag <type> --id <id> --set k=v`
*   **Stretch (Mở rộng - Không bắt buộc nhưng đã hoàn thành 100%):**
    - `clean --tag purpose=practice --apply` (Xóa hàng loạt tài nguyên theo tag, mặc định dry-run)
    - `idle --threshold 5 --hours 24` (Phát hiện EC2 chạy không tải bằng CloudWatch CPU avg)
    - `migrate-gp3 --apply --volume-id <id>` (Lên kế hoạch hoặc chuyển đổi trực tiếp gp2 → gp3 EBS volume)

*   **Goal:** Vượt qua **25/25 test cases** thành công.

---

## 2. Các file đã thực hiện (Modified Files)

Toàn bộ logic xử lý đã được triển khai hoàn chỉnh trong các file dưới đây:

1.  **[list_cmd.py](file:///E:/x-brain/W6/XB-DN26-103-assm/xbrain-costctl-starter/commands/list_cmd.py)** - Triển khai liệt kê tài nguyên và bộ lọc tags.
2.  **[terminate_cmd.py](file:///E:/x-brain/W6/XB-DN26-103-assm/xbrain-costctl-starter/commands/terminate_cmd.py)** - Hủy tài nguyên an toàn và kiểm tra điều kiện an toàn của S3.
3.  **[tag_cmd.py](file:///E:/x-brain/W6/XB-DN26-103-assm/xbrain-costctl-starter/commands/tag_cmd.py)** - Gán/cập nhật tags (xử lý merge tags cho S3 và fetch ARN cho RDS).
4.  **[cost_cmd.py](file:///E:/x-brain/W6/XB-DN26-103-assm/xbrain-costctl-starter/commands/cost_cmd.py)** - Tổng hợp và tính toán chi phí qua Cost Explorer.
5.  **[clean_cmd.py](file:///E:/x-brain/W6/XB-DN26-103-assm/xbrain-costctl-starter/commands/clean_cmd.py)** - Tìm kiếm mục tiêu và dọn dẹp hàng loạt theo tag (dry-run/apply).
6.  **[idle_cmd.py](file:///E:/x-brain/W6/XB-DN26-103-assm/xbrain-costctl-starter/commands/idle_cmd.py)** - Phân tích hiệu suất CPU để tìm EC2 không dùng đến.
7.  **[migrate_gp3_cmd.py](file:///E:/x-brain/W6/XB-DN26-103-assm/xbrain-costctl-starter/commands/migrate_gp3_cmd.py)** - Tính toán lượng tiết kiệm và nâng cấp EBS từ gp2 lên gp3 không gây downtime.

---

## 3. Phương pháp triển khai chi tiết (Cách làm)

### Lệnh `list <type>`
- **EC2 & EBS Volumes:** Sử dụng `boto3` client kèm theo `get_paginator` để tránh giới hạn số lượng trả về khi có quá nhiều tài nguyên. Dùng helper `tags_match` để lọc.
- **RDS:** Mô hình RDS yêu cầu lấy thông tin chi tiết từng DB instance trước, sau đó gọi thêm API `list_tags_for_resource` qua ARN của DB instance để lấy tag set.
- **S3:** Liệt kê các buckets thông qua `list_buckets`. Với mỗi bucket, gọi `get_bucket_tagging`. Trường hợp bucket chưa từng được gán tag (ném ra `ClientError`), bắt ngoại lệ và xử lý như bộ tag trống `{}` để tránh làm crash ứng dụng.

### Lệnh `terminate <type>`
- Triển khai prompt xác nhận trước khi thực thi bằng hàm `confirm(prompt, force)`. Nếu người dùng từ chối, CLI sẽ in `Aborted.` và dừng lại.
- **Quy tắc an toàn cho S3:** Gọi `list_objects_v2(Bucket=name).get("KeyCount", 0)`. Nếu lớn hơn 0, in thông báo từ chối `Refusing — bucket my-bucket has N object(s). Empty it first.` và không thực hiện xóa.
- **Quản lý ngoại lệ:** Tất cả các thao tác gọi AWS API được bọc trong block `try-except ClientError` để trích xuất mã lỗi và thông điệp lỗi của AWS, in ra dưới định dạng `AWS error [ErrorCode]: ErrorMessage`.

### Lệnh `tag <type>`
- Chuyển đổi định dạng tham số `--set key=value` thành `[{'Key': key, 'Value': value}]` thông qua hàm helper `parse_kv`.
- **RDS:** Bắt buộc lấy thông tin ARN qua `describe_db_instances` trước khi gọi `add_tags_to_resource`.
- **S3:** Do `put_bucket_tagging` ghi đè toàn bộ tags có sẵn, chương trình sẽ lấy danh sách tags hiện tại (`get_bucket_tagging`), tiến hành hợp nhất (merge) chúng với tags mới (các tags trùng key sẽ bị ghi đè bằng giá trị mới), sau đó mới đẩy ngược trở lại S3.

### Lệnh `cost`
- Lấy ngày hiện tại làm mốc `End` và trừ đi số ngày cấu hình `--days` để làm mốc `Start`.
- Gọi Cost Explorer API `get_cost_and_usage` với tag filter. Các nhóm chi phí được phân tích theo Service.
- Chuyển đổi chuỗi Amount thành kiểu số thực `float`, tính toán tổng cộng và hiển thị bảng chi phí đẹp mắt được sắp xếp giảm dần.

### Lệnh `clean`
- Triển khai bộ tìm kiếm `_find_targets` để lọc ra các EC2 không nằm trong trạng thái terminal (`terminated` hoặc `shutting-down`) và các EBS Volume chỉ ở trạng thái `available` (chưa được gắn vào EC2 nào).
- Mặc định in ra danh sách dự kiến dọn dẹp (Dry-run). Khi người dùng truyền `--apply`, hệ thống sẽ thực thi xóa hàng loạt song song an toàn.

### Lệnh `idle`
- Quét qua danh sách các EC2 đang chạy (trừ các instance có tag `keep=true`).
- Gọi CloudWatch API `get_metric_statistics` để tính CPUUtilization trung bình trong vòng `N` giờ đã chọn. Nếu trung bình nhỏ hơn ngưỡng `--threshold`, đánh dấu instance đó là `IDLE`.

### Lệnh `migrate-gp3`
- Quét toàn bộ EBS volume loại `gp2`. 
- Tính toán tiền tiết kiệm mỗi tháng theo công thức: `Size * (GP2_PRICE - GP3_PRICE)` (với mức chênh lệch là $0.02/GB mỗi tháng).
- Chế độ Dry-run hiển thị bảng chi tiết các Volume cùng chi phí tiết kiệm. Chế độ Apply thực hiện sửa đổi loại volume thông qua `modify_volume` với baseline 3000 IOPS và 125 MiB/s throughput đi kèm miễn phí của gp3.

---

## 4. Kết quả đạt được (Validation & Test Results)

### Kết quả chạy kiểm thử (Local Tests)
Toàn bộ 25 test cases tích hợp đã chạy thành công mỹ mãn:

```powershell
pytest -v tests/
```

**Báo cáo đầu ra chi tiết:**
```text
============================= test session starts =============================
platform win32 -- Python 3.12.0, pytest-9.0.3, pluggy-1.6.0
plugins: anyio-4.12.0, cov-7.1.0
collected 25 items

tests/test_clean.py::test_find_targets_finds_tagged_instance PASSED      [  4%]
tests/test_clean.py::test_clean_dry_run_does_not_delete PASSED           [  8%]
tests/test_clean.py::test_clean_apply_terminates PASSED                  [ 12%]
tests/test_clean.py::test_clean_no_matches PASSED                        [ 16%]
tests/test_common.py::test_parse_kv_simple PASSED                        [ 20%]
tests/test_common.py::test_parse_kv_empty_value PASSED                   [ 24%]
tests/test_common.py::test_parse_kv_value_with_equals PASSED             [ 28%]
tests/test_common.py::test_parse_kv_no_key_raises PASSED                 [ 32%]
tests/test_common.py::test_tags_to_dict_empty PASSED                     [ 36%]
tests/test_common.py::test_tags_to_dict_roundtrip PASSED                 [ 40%]
tests/test_common.py::test_tags_match_all_match PASSED                   [ 44%]
tests/test_common.py::test_tags_match_missing_value_fails PASSED         [ 48%]
tests/test_common.py::test_tags_match_missing_key_filter PASSED          [ 52%]
tests/test_common.py::test_tags_match_no_filter PASSED                   [ 56%]
tests/test_list.py::test_list_ec2_empty PASSED                           [ 60%]
tests/test_list.py::test_list_ec2_no_filter_returns_all PASSED           [ 64%]
tests/test_list.py::test_list_ec2_filter_by_tag PASSED                   [ 68%]
tests/test_list.py::test_list_ec2_missing_tag PASSED                     [ 72%]
tests/test_list.py::test_list_ec2_combined_tag_and_missing PASSED        [ 76%]
tests/test_list.py::test_list_s3_no_tagging_treated_as_empty_tags PASSED [ 80%]
tests/test_list.py::test_list_volume_returns_type_size PASSED            [ 84%]
tests/test_terminate.py::test_terminate_ec2_with_force PASSED            [ 88%]
tests/test_terminate.py::test_terminate_s3_refuses_nonempty PASSED       [ 92%]
tests/test_terminate.py::test_terminate_s3_deletes_empty PASSED          [ 96%]
tests/test_terminate.py::test_terminate_nonexistent_handles_clienterror PASSED [100%]

============================= 25 passed in 17.23s =============================
```

---

## 5. Mẫu báo cáo nộp bài (Slack Submission Format)

Dưới đây là mẫu báo cáo nộp bài hoàn chỉnh tương ứng với kết quả của nhóm:

```text
G<N> — <repo-url> — 25/25 tests passing — implemented: list, cost, terminate, tag, clean, idle, migrate-gp3
```
*(Hãy thay thế `<N>` bằng số nhóm thực tế và `<repo-url>` bằng đường dẫn Git repository trước khi nộp)*
