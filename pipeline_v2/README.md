# Đồ án: Đánh giá tiến độ thi công bằng ảnh drone và mô hình BIM

Tài liệu này tóm tắt những gì đã làm, luồng chạy của dự án và cách chạy từ đầu đến cuối.
Cập nhật lần cuối: 14/10/2026.

## Mục lục

1. [Tổng quan](#1-tổng-quan)
2. [Những gì đã làm](#2-những-gì-đã-làm)
3. [Luồng chạy của dự án](#3-luồng-chạy-của-dự-án)
4. [Cấu trúc thư mục và vai trò từng file](#4-cấu-trúc-thư-mục-và-vai-trò-từng-file)
5. [Hướng dẫn chạy từ đầu đến cuối](#5-hướng-dẫn-chạy-từ-đầu-đến-cuối)
6. [Kế hoạch bay đề xuất cho công ty](#6-kế-hoạch-bay-đề-xuất-cho-công-ty)
7. [Câu hỏi cần hỏi GVHD và công ty](#7-câu-hỏi-cần-hỏi-gvhd-và-công-ty)
8. [Việc còn lại và giới hạn đã biết](#8-việc-còn-lại-và-giới-hạn-đã-biết)
9. [Phụ lục: số liệu file PLM.ifc](#9-phụ-lục-số-liệu-file-plmifc)

---

## 1. Tổng quan

**Mục tiêu:** từ ảnh chụp công trình bằng drone, dựng mô hình 3D (point cloud), đối chiếu với mô hình BIM
(`PLM.ifc`, xuất từ Revit) để xác định cấu kiện nào đã xây, rồi so với lịch thi công dự kiến
(file Navisworks `.nwd`) để kết luận công trình nhanh hay chậm.

**Phân công công cụ:**

| Việc | Công cụ | Ai làm |
|---|---|---|
| Bay drone, chụp ảnh | DJI Dock 3 + Matrice 4TD + D-RTK 3 | Công ty |
| Dựng 3D từ ảnh (SfM + MVS) | WebODM (OpenDroneMap) chạy bằng Docker | Dùng sẵn |
| Đọc BIM, căn chỉnh, đánh giá tiến độ | Python (IfcOpenShell, Open3D, SciPy) | Nhóm tự viết |
| Xem mô hình và lịch 4D | Revit, Navisworks Freedom | Dùng sẵn |

**Trạng thái hiện tại:** pipeline đã chạy trọn vẹn trên **dữ liệu giả lập** sinh từ chính BIM.
Chưa có ảnh drone thật của công trình, nên mọi con số hiệu năng bên dưới là **cận trên**, không phải kết quả thật.

---

## 2. Những gì đã làm

| # | Việc | Kết quả |
|---|---|---|
| 1 | Chuyển hướng đề tài | Ban đầu định tự viết firmware flight controller (STM32). Đã bỏ vì đề tài chính là dựng 3D và so sánh BIM. Code cũ nằm trong `drone_fc.zip`, không dùng cho hướng hiện tại. Drone nhóm tự chế chưa xong nên chưa tính tới |
| 2 | Lộ trình lý thuyết | Camera model, SfM/MVS, point cloud, ICP, BIM/IFC, bài toán giàn giáo, bề mặt ít texture |
| 3 | Phân tích dữ liệu BIM | `PLM.ifc` (IFC2X3, Revit 2025) và `.nwd` (xem phụ lục) |
| 4 | Sửa `bim_loader` | Trước đây 1.268/2.705 cấu kiện không có hình học. Nay có đủ 2.705/2.705 (nguyên nhân và cách sửa ở mục 4) |
| 5 | Demo SfM bằng tay | Render bình hoa 3D, chạy SIFT, Essential Matrix, triangulation (`vase_demo.zip`) và template SfM có TODO. Chỉ để hiểu cơ chế |
| 6 | Cài và chạy WebODM | Chạy thử bộ ảnh mẫu banana: 15/16 ảnh được dùng, 15.823 điểm thưa, 1.158.107 điểm dày, 12 phút 1 giây |
| 7 | Mô phỏng toàn bộ luồng | Sinh point cloud giả lập, căn chỉnh ICP, đánh giá tiến độ, so với lịch (kết quả bên dưới) |
| 8 | Kế hoạch bay | Thông số và yêu cầu gửi công ty (mục 6) |
| 9 | Danh sách câu hỏi | Cho GVHD và công ty (mục 7) |
| 10 | Phương án phụ | Firmware ESP32 trigger GoPro (`esp32_gopro_trigger_bridge.ino`). Chỉ dùng nếu sau này nhóm tự chế drone |

### Kết quả thử nghiệm trên dữ liệu giả lập

Giả lập toà nhà "xây đến tầng 8" (nhiễu 3 cm, bỏ mặt dưới, rơi 30% điểm, thêm outlier, làm lệch toạ độ).

| Thí nghiệm | Kết quả |
|---|---|
| Lệch 4,6 m và quay 4° (kiểu sai số GPS) | ICP kéo về sai khoảng 0,3 cm |
| Sai cao độ ban đầu ≤ 1,0 m | Căn đúng |
| Sai cao độ ban đầu ≥ 1,65 m | **Căn nhầm sang tầng khác** (sai 3,07 đến 3,30 m) |
| Phát hiện cấu kiện đã xây | Đúng 2.705/2.705 |
| Bỏ qua bước căn chỉnh | Chỉ đúng khoảng 51%, bỏ sót gần hết cấu kiện đã xây |
| So với lịch (giả định lịch yêu cầu xong đến tầng 9) | Báo chậm 2 tầng, 285 cấu kiện trễ |

Ba điều rút ra:

1. Cao độ phải được khoá bằng RTK hoặc GCP. Các tầng lặp lại cách nhau khoảng 3,3 m nên ICP dễ khớp nhầm tầng.
2. Kết quả 100% là cận trên: dữ liệu giả lập sinh từ đúng mô hình BIM nên rất sạch. Ảnh thật sẽ có giàn giáo, ván khuôn, che khuất.
3. Dữ liệu BIM có hai lỗi cần biết: nhãn tầng trong IFC sai ở 21 dầm, và `Pset_QuantityTakeOff` không chứa khối lượng.

---

## 3. Luồng chạy của dự án

```
 [Công ty bay]                       [WebODM / Docker]
 Dock 3 + Matrice 4TD + D-RTK 3
        │ ảnh JPEG 48 MP + log bay + toạ độ GCP
        ▼
 Lọc ảnh mờ / thừa ───────────────► SfM + MVS ───► point cloud (.laz / .ply)
                                                        │
 [BIM]                                                  │ (có toạ độ trắc địa)
 PLM.ifc ──► bim_loader.py ──► plm_elements.json        │
                              plm_meshes.npz            │
                                   │                    ▼
                                   │          căn thô bằng GCP  (CHƯA VIẾT)
                                   │                    │
                                   │                    ▼
                                   └────────► registration.py  (ICP, đưa về toạ độ BIM)
                                                        │
                                                        ▼
                              progress_evaluator.py: coverage từng cấu kiện
                                  → da xay / khong chac / chua xay
                                  → tổng hợp theo tầng, theo thể tích bê tông
                                                        │
                       lịch thi công (TimeLiner) ──────►│ so sánh dự kiến và thực tế
                                                        ▼
                                          báo cáo: chậm / đúng / nhanh bao nhiêu tầng
```

**Ý tưởng cốt lõi của phần đánh giá:** không cần AI nhận diện cột, dầm. BIM đã cho biết mỗi cấu kiện nằm ở đâu,
nên chương trình chỉ kiểm tra "ở vị trí đó có điểm ảnh thật không" (coverage trong dung sai 10 cm).

---

## 4. Cấu trúc thư mục và vai trò từng file

Theo ảnh VS Code của bạn, thư mục dự án là `D:\0. DO_AN\0. PREPARE\pipeline_v2`:

```
pipeline_v2/
├── data/                  (dữ liệu đầu vào)
├── pipeline/              (code Python)
├── results/               (kết quả chạy)
├── PLM.ifc                (mô hình BIM)
└── README.md
```

### File do mình viết (đã chạy thử)

| File | Vai trò |
|---|---|
| `bim_loader.py` | Đọc IFC, lấy hình học dầm/cột/sàn theo mét, xuất `plm_elements.json` và `plm_meshes.npz` |
| `mesh_utils.py` | Đọc lại dữ liệu BIM, gán tầng theo cao độ Z, lấy mẫu điểm trên bề mặt mesh |
| `simulate_asbuilt.py` | Sinh point cloud giả lập "toà nhà đang xây đến tầng N" từ BIM |
| `registration.py` | Căn chỉnh point cloud về toạ độ BIM bằng ICP (có sẵn hàm FPFH + RANSAC toàn cục) |
| `progress_evaluator.py` | Tính coverage từng cấu kiện, phân loại, tổng hợp theo tầng, so với lịch |
| `run_demo.py` | Chạy cả chuỗi trên dữ liệu giả lập, in kết quả và vẽ hình |

**Chi tiết `bim_loader` đã sửa:** 1.268 dầm có hai biểu diễn là `Axis` (đường trục 2D) và `Body` (thân dầm 3D).
Thư viện chọn nhầm `Axis` nên báo lỗi. Cách sửa là lấy thẳng `Body`, tự nhân ma trận placement (đổi mm sang m).
Đã đối chiếu với cách cũ trên 437 cấu kiện, sai lệch bằng 0,0 m.

**Gán tầng theo Z, không dùng nhãn tầng IFC:** 21 dầm nhỏ bị gán "TẦNG 1" nhưng nằm ở cao độ 36 đến 48 m.

### File do nhóm bạn thêm hoặc sửa (mình chưa xem nội dung)

Bạn điền mô tả ngắn vào cột bên phải để tài liệu đầy đủ:

| File | Vai trò |
|---|---|
| `config.py` | (bạn điền) |
| `check_levels.py` | (bạn điền) |
| `fusion.py` | (bạn điền) |
| `visibility.py` | (bạn điền) |
| `make_synth.py` | (bạn điền) |
| `schedule_loader.py` | (bạn điền) |
| `run_fusion_demo.py` | (bạn điền) |
| `lich_timeline_gia_mau.csv` | (bạn điền: lịch mẫu, cột nào, nguồn từ đâu) |

---

## 5. Hướng dẫn chạy từ đầu đến cuối

### 5.1 Môi trường Python (làm một lần)

Bạn đang dùng conda với môi trường tên `bim` (Python 3.11). Nếu cần tạo lại:

```powershell
conda create -n bim python=3.11 -y
conda activate bim
pip install ifcopenshell open3d scipy matplotlib numpy
```

Nếu thiếu thư viện khi chạy, đọc dòng `ModuleNotFoundError: ...` rồi `pip install` đúng thư viện đó.
Muốn đọc file `.laz` (định dạng point cloud nén của WebODM) cần thêm `pip install laspy[lazrs]`.

### 5.2 Cài và chạy WebODM bằng Docker

**Cần có:** Docker Desktop (Windows cần WSL2) và Git for Windows (đi kèm Git Bash).

**Lần đầu:**

1. Mở **Docker Desktop**, đợi đến khi trạng thái là **Running**.
2. Mở PowerShell, tải mã nguồn (một lần):
   ```powershell
   git clone https://github.com/OpenDroneMap/WebODM --depth 1
   ```
3. **Mở Git Bash** (không dùng PowerShell cho bước này, vì `webodm.sh` là bash script).
   Chạy lệnh bên dưới. Đường dẫn có dấu cách nên phải để trong ngoặc kép, ổ đĩa viết dạng `/d/`:
   ```bash
   cd "/d/BKU/4. Year 4th/0. DO_AN/WebODM"
   ./webodm.sh start
   ```
4. Lần đầu mất 15 đến 30 phút để tải image. **Không đóng cửa sổ và không để máy sleep.**
   Cảnh báo vàng `the attribute version is obsolete` là vô hại.
5. Khi thấy dòng `Congratulations! ... WebODM should be up and running!`, mở trình duyệt vào
   <http://localhost:8000> và tạo tài khoản admin.
6. Vào **Processing Nodes**, phải thấy `node-odx-1` online.

**Các lần sau:** mở Docker Desktop, vào Git Bash, `cd` đúng thư mục, chạy `./webodm.sh start`.

**Cấp đủ RAM cho Docker:** Docker Desktop → Settings → Resources. Nếu dùng WSL2, giới hạn RAM đặt trong file
`%UserProfile%\.wslconfig`, ví dụ:

```ini
[wsl2]
memory=12GB
```

Sau khi sửa phải chạy `wsl --shutdown` rồi mở lại Docker Desktop.

### 5.3 Dựng 3D từ ảnh trong WebODM

1. **Dashboard → Add Project**, đặt tên.
2. Vào project, bấm **Select Images and GCP**, chọn toàn bộ ảnh JPEG của một đợt bay
   (kèm file GCP nếu có; dùng mục **GCP Interface** ở thanh bên để tạo).
3. Chỉnh tuỳ chọn xử lý (Options). Lần đầu cứ để mặc định để thử. Với ảnh công trình, nên thử và so sánh các tham số
   `pc-quality`, `feature-quality`, `min-num-features`, và nạp file GCP (tên tham số lấy từ trang Options của WebODM).
4. **Review → Start Processing.** Theo dõi tiến độ, không để máy sleep.
5. Xem kết quả: nút **3D Model**. Bấm **Textured Model** nếu muốn nhìn liền mạch.
6. Đọc log: ở dòng **Task Output**, bấm **On**. Tìm dòng cho biết bao nhiêu ảnh được dùng trong tổng số ảnh.
   Nút **Report** cho báo cáo chất lượng tự động.
7. Tải point cloud: bấm **mũi tên nhỏ bên phải nút Download**, chọn point cloud (`.ply` hoặc `.laz`), lưu vào thư mục `data/`.

**Kiểm tra chất lượng trước khi dùng (quality gate):**

- Tỉ lệ ảnh được dùng mong muốn ≥ 90%.
- Không có lỗ lớn trên mái và mặt sàn trên cùng. Lỗ ở mặt dưới hoặc chỗ khuất là bình thường.
- Nếu không đạt thì bay lại, không cố sửa bằng thuật toán.

**Khi xem thấy toàn chấm thưa:** chỉ là cách hiển thị (LOD). Zoom lại gần, tăng Point Budget và Point Size trong
mục Appearance, hoặc bấm Textured Model. Dữ liệu tải về vẫn đủ điểm.

### 5.4 Chạy phần BIM và đánh giá tiến độ

Mở PowerShell trong VS Code:

```powershell
conda activate bim
cd "D:\0. DO_AN\0. PREPARE\pipeline_v2"
```

**Bước 1. Trích xuất cấu kiện từ IFC** (chạy một lần, hoặc khi đổi file IFC):

```powershell
python pipeline\bim_loader.py PLM.ifc results
```

Sinh ra `results\plm_elements.json` và `results\plm_meshes.npz`. Tham số dòng lệnh có thể khác nếu bạn đã sửa file;
xem phần `if __name__ == "__main__"` ở cuối `bim_loader.py`. Bước 2 cần **cả hai file** này.

**Bước 2. Kiểm thử toàn bộ luồng trên dữ liệu giả lập** (xây đến tầng 8):

```powershell
python pipeline\run_demo.py --n-top 8
```

Chạy khoảng 1 phút. In ra: sai số căn chỉnh, độ nhạy theo sai cao độ, độ chính xác phân loại,
bảng tiến độ theo tầng, so với lịch. Lưu `results\demo_results.json` và `results\demo_progress.png`.

Đổi `--n-top` (ví dụ `--n-top 5`) để giả lập tiến độ khác.

**Các file nhóm bạn thêm** (chạy khi cần): `python pipeline\run_fusion_demo.py` và các script khác. Bạn ghi lại cách dùng ở mục 4.

### 5.5 Dừng, chạy lại và reset WebODM

Làm trong **Git Bash**, đúng thư mục WebODM:

```bash
./webodm.sh stop        # dừng, giữ dữ liệu
./webodm.sh start       # chạy lại
./webodm.sh restart     # khởi động lại nhẹ
./webodm.sh down        # dọn container đang dở (giữ project), rồi chạy ./webodm.sh start
docker ps               # kiểm tra container đang chạy (phải thấy vài dòng như webapp, db, node)
```

**Máy bị sleep khi đang tải hoặc xử lý:** chạy `./webodm.sh down` rồi `./webodm.sh start`. Docker giữ lại phần đã tải.

**Quên mật khẩu admin:**

```bash
./webodm.sh resetadminpassword "mat_khau_moi"
```

**Reset sạch hoàn toàn (xoá toàn bộ project và task, chỉ làm khi chắc chắn):**
chạy `./webodm.sh down`, rồi vào Docker Desktop → tab Volumes, xoá các volume của WebODM
(tên thường bắt đầu bằng `webodm_`). Sau đó `./webodm.sh start` để dựng lại từ đầu.

**Nâng cấp WebODM:** `./webodm.sh update`.

### 5.6 Lỗi thường gặp

| Triệu chứng | Nguyên nhân và cách xử lý |
|---|---|
| `./webodm.sh : The term is not recognized` trong PowerShell | Dùng Git Bash, không dùng PowerShell |
| Chạy `start` nhưng màn hình đứng im | Docker đang tải image; mở Docker Desktop xem tiến độ. Nếu quá 45 phút không nhúc nhích thì kiểm tra mạng |
| Không mở được `localhost:8000` | Docker Desktop chưa Running, hoặc `start` chưa chạy xong |
| Task báo `out of memory` hoặc `killed` | Tăng RAM cho Docker (5.2), giảm kích thước ảnh, hoặc giảm `pc-quality` |
| Point cloud nhìn như lưới chấm thưa | Chỉ là hiển thị; zoom gần hoặc dùng Textured Model |
| Lỗ ở mặt dưới hoặc chỗ tiếp xúc | Bình thường, không ảnh nào thấy nên không dựng được |
| `ModuleNotFoundError` khi chạy `.py` | `pip install` thư viện còn thiếu trong môi trường `bim` |
| Cảnh báo `GPS position not available` | Ảnh không có GPS (như bộ banana). Ảnh công trình thật phải có geotag |

---

## 6. Kế hoạch bay đề xuất cho công ty

Thiết bị: DJI Dock 3, Matrice 4TD (tiêu đề file thông số ghi "Mavic 4TD", nội dung là Matrice 4TD),
D-RTK 3 (trạm cố định), camera góc rộng 48 MP, cảm biến 1/1.3 inch, tương đương 24 mm.

**Các con số dưới đây là ước tính** từ tiêu cự tương đương 24 mm. Công ty cần xác nhận kích thước cảm biến
và tiêu cự thật (đọc từ EXIF của ảnh mẫu). Theo thông số công bố của nhà phân phối, khoảng chụp tối thiểu ở 48 MP là 0,7 giây,
cũng cần công ty xác nhận.

| | Bay cao 50 m | Bay cao 80 m |
|---|---|---|
| GSD (độ phân giải mặt đất) | khoảng 0,9 cm | khoảng 1,4 cm |
| Vùng phủ một ảnh | 72 × 54 m | 115 × 86 m |
| Khoảng cách giữa 2 ảnh (chồng lấp dọc 80%) | 10,8 m | 17,3 m |
| Khoảng cách giữa 2 đường bay (chồng lấp ngang 70%) | 21,6 m | 34,6 m |
| Khoảng thời gian giữa 2 ảnh nếu bay 5 m/s | khoảng 2,2 s | khoảng 3,5 s |

GSD dưới 2 cm là đủ vì chương trình đánh giá dùng dung sai 10 cm.

**Một đợt bay thử (theo thứ tự ưu tiên):**

1. Lưới nadir (camera thẳng xuống): chồng lấp 80% dọc, 70% ngang, bay cao hơn điểm cao nhất của công trình
   (kể cả cần cẩu) ít nhất 20 đến 30 m. Nhà thấp tầng như video demo thì khoảng 40 đến 50 m.
2. Chụp nghiêng 5 hướng: chồng lấp 80% cả hai chiều. Camera nghiêng giúp thấy mặt đứng (cột, mép dầm).
3. Nếu còn pin: quỹ đạo quanh toà nhà chính ở 3 độ cao.
4. Bay lặp lại chuyến 1 và 2 lần thứ hai trong cùng ngày để đo độ lặp lại của cả hệ thống.

**Thời điểm và tần suất:**

- Trời mây nhẹ, tránh nắng gắt. Các đợt sau bay cùng khung giờ (lệch không quá 1 tiếng).
- Một đợt nền ban đầu, sau đó khoảng 1 tuần một lần và thêm một đợt sau mỗi lần đổ xong một sàn.
- Một đợt khoảng 15 đến 25 phút bay (ước tính, công ty biết rõ hơn).

**Giao nộp mỗi đợt:**

- Ảnh JPEG gốc 48 MP, không nén lại, không đổi tên, giữ nguyên EXIF và XMP (GPS, cờ trạng thái RTK).
- File nhiệm vụ bay và log bay.
- Toạ độ trạm D-RTK 3, hệ toạ độ (WGS84 hay VN-2000), và toạ độ 4 đến 6 mốc mặt đất nếu đo được.
- Ngày giờ bay, thời tiết, công việc thi công hôm đó. Mỗi đợt một thư mục riêng.

---

## 7. Câu hỏi cần hỏi GVHD và công ty

### Hỏi giảng viên hướng dẫn

1. Đợt bay sẽ là công trình nào, và công trình đó đã có BIM chưa? Video demo là nhà phố thấp tầng, còn `PLM.ifc`
   là cao ốc 17 tầng. Nếu không bay PLM thì phần so sánh với BIM kiểm chứng bằng cách nào?
2. Phạm vi so sánh là gì? File `PLM.ifc` có 2.705 dầm, cột, sàn và 6.089 phần tử ván khuôn. Có tính ván khuôn không?
   Mức đánh giá mong muốn là "tầng đã đổ chưa", từng cấu kiện, hay từng giai đoạn (ván khuôn, cốt thép, bê tông)?
3. Lịch tiến độ lấy ở đâu? Xin file lịch gốc (Excel, MS Project hoặc Primavera). File `.nwd` có thật sự chứa TimeLiner không
   (Navisworks Freedom của bạn chưa thấy panel Tools)? Các nhãn tầng kèm ngày trong Revit có phải lịch dự kiến không?
   Trường có cấp bản Navisworks đầy đủ không?
4. Tiêu chí thành công: sai số chấp nhận được bao nhiêu cm, lịch cần chi tiết đến ngày, tuần hay tầng?
5. Giàn giáo có bắt buộc phải lọc không, ở mức độ nào?
6. Ai sở hữu file BIM, có được đưa ảnh và mô hình của dự án thật vào báo cáo không? Có cần báo người làm mô hình về
   21 dầm bị gán nhãn sai tầng không?
7. Báo cáo giữa kỳ có chấp nhận kết quả trên dữ liệu giả lập không, yêu cầu nội dung và mốc thời gian cụ thể là gì?
8. Dữ liệu cuối cùng dùng ảnh drone của công ty hay drone nhóm tự làm? Phần drone của nhóm có liên quan đề tài này không?

### Hỏi công ty bay

1. Công trình bay là công trình nào, địa chỉ ở đâu, điểm cao nhất kể cả cần cẩu là bao nhiêu?
   Ai xin phép bay, có giới hạn độ cao không?
2. Có bật D-RTK 3 khi bay không? Có đo được 4 đến 6 mốc mặt đất (GCP) bằng GNSS RTK hoặc máy toàn đạc không?
   Cho biết toạ độ trạm D-RTK 3 và hệ toạ độ. Lý do: trong mô phỏng, sai cao độ ban đầu trên khoảng 1,0 đến 1,65 m
   làm bước căn chỉnh khớp nhầm tầng.
3. Dữ liệu giao là ảnh tĩnh (không phải video): JPEG gốc 48 MP, không nén lại, không đổi tên, giữ nguyên EXIF và XMP,
   kèm file nhiệm vụ và log bay của từng đợt.
4. FlightHub 2 trên Dock 3 có chạy được lưới nadir, chụp nghiêng 5 hướng, Smart 3D Capture không? Có lưu và bay lại đúng cùng
   một đường bay giữa các đợt không? Xác nhận đúng máy là Matrice 4TD.
5. Thông số bay đề xuất: chồng lấp 80% dọc và 70% ngang (chụp nghiêng 80% cả hai chiều), GSD không quá 2 cm,
   tốc độ không quá 5 m/s, ưu tiên chụp theo khoảng cách (nếu theo thời gian thì 2 giây), độ cao như mục 6.
6. Đợt thử: lưới nadir và chụp nghiêng, thêm quỹ đạo 3 độ cao nếu còn pin, bay lặp lại hai lần trong cùng ngày.
7. Giờ bay: trời mây nhẹ, tránh nắng gắt, các đợt sau cùng khung giờ, tránh lúc cẩu hàng hoặc đông người.
8. Tần suất và chi phí: một đợt nền, sau đó khoảng 1 tuần một lần và thêm một đợt sau mỗi lần đổ xong một sàn.
   Chi phí mỗi đợt là bao nhiêu, hạn giao dữ liệu đợt đầu là khi nào?
9. Kèm theo mỗi đợt: ngày giờ bay, thời tiết, công việc thi công hôm đó. Dữ liệu nặng nên gửi qua link hoặc ổ cứng.
10. Dữ liệu có được dùng trong đồ án và báo cáo không?

---

## 8. Việc còn lại và giới hạn đã biết

**Việc còn lại (theo thứ tự ưu tiên):**

1. Chốt với GVHD: công trình được bay, phạm vi ván khuôn, nguồn lịch.
2. Viết hàm đọc point cloud thật (`.ply`, `.laz`) và **căn thô từ GCP**. Point cloud thật nằm ở toạ độ trắc địa (hàng trăm
   nghìn mét) còn BIM ở toạ độ cục bộ (0 đến 80 m), ICP không bắc cầu được khoảng cách đó. Cần tính phép biến đổi
   ban đầu từ ít nhất 3 điểm tương ứng và trừ offset để không mất độ chính xác số.
3. Thêm giàn giáo và ván khuôn giả lập vào dữ liệu thử, đo mức ảnh hưởng, thử bộ lọc theo hình học cục bộ (đường so với mặt
   phẳng) kết hợp màu RGB.
4. Hiệu chỉnh ngưỡng coverage (hiện `t_built = 0.30`, `t_not = 0.10`) trên dữ liệu thật.
5. Nối lịch thật vào `compare_with_schedule` (ghép tên tầng IFC với lịch).
6. Phân tích độ nhạy: tăng nhiễu, tăng tỉ lệ mất điểm, tăng sai số căn chỉnh để thấy chỗ phương pháp bắt đầu hỏng.
7. Viết báo cáo.

**Giới hạn đã biết:**

- Kết quả 100% trên giả lập là cận trên, không phải hiệu năng thật.
- Drone chỉ thấy lớp ngoài và phần trên cùng. Cột và dầm bên trong bị sàn tầng trên che nên đánh giá chỉ đáng tin
  ở tầng đang thi công và các cấu kiện ngoài biên.
- Chỉ dựa hình học thì khó phân biệt ván khuôn, cốt thép và bê tông đã đổ (cùng nằm gần một bề mặt trong dung sai 10 cm).
- Giàn giáo vừa che cấu kiện đã xây (bỏ sót) vừa đứng sát cấu kiện chưa xây ở tầng đang làm (báo nhầm).
- Bê tông trắng trơn ít texture nên SfM dễ thiếu điểm. Cần chồng lấp ảnh dày và có ảnh nghiêng.
- Nhãn tầng trong IFC không đáng tin, đã gán tầng theo cao độ Z.
- Pipeline chưa được thử trên ảnh thật của công trình.

---

## 9. Phụ lục: số liệu file PLM.ifc

| Mục | Giá trị |
|---|---|
| Định dạng | IFC2X3, xuất từ Revit 2025, khoảng 306.000 dòng, 21,5 MB |
| Dầm / cột / sàn | 1.413 / 995 / 297 (tổng 2.705, đều có hình học sau khi sửa) |
| Phần tử ván khuôn `TS_FormWork` | 6.089 (hiện đang bị loại khỏi so sánh) |
| Lỗ mở | 479 |
| Mức sàn (cao độ, tách theo hình học) | 17 mức, tầng điển hình cách nhau khoảng 3,3 m |
| Kích thước toà nhà | khoảng 57 × 79 m mặt bằng, cao khoảng 55 m |
| Thể tích bê tông kết cấu (tính từ mesh) | 7.852 m³ (dầm 733, cột 1.356, sàn 5.763) |
| Mesh gộp | 53.339 đỉnh, 91.494 tam giác |
| `Pset_QuantityTakeOff` | chỉ chứa tên tiết diện (ví dụ 300x600), không có khối lượng |
| Lỗi gán tầng | 21 dầm gán "TẦNG 1" nhưng nằm ở cao độ 36 đến 48 m |

File `Mô_hình_tiến_độ_Kết_cấu_PALC_Q9.nwd` là định dạng nhị phân của Autodesk, chỉ Navisworks mở được.
Navisworks Freedom chỉ phát lại mô phỏng TimeLiner khi file đã có sẵn dữ liệu, không tạo hay xuất được.

# Đánh giá tiến độ thi công bằng ảnh drone và mô hình BIM

Đồ án: dựng mô hình 3D của công trình từ ảnh drone (WebODM/OpenDroneMap), đăng ký vào mô hình BIM (IFC), rồi
so sánh theo từng cấu kiện để biết cấu kiện nào đã xây, chưa xây hay không kiểm chứng được, và so với lịch thi công.

> **Trạng thái trung thực:** phần đọc IFC, kiểm tra tầng đã chạy trên `PLM.ifc` thật. Phần mô phỏng, đăng ký,
> đánh giá tiến độ, đọc lịch và hợp nhất nhiều lần quét mới được thử trên dữ liệu giả lập (và `PLM.ifc` thật cho
> bước đọc hình học). **Chưa có ảnh drone thật và chưa chạy trên lịch TimeLiner thật.** Mọi con số độ chính xác bên
> dưới là của mô phỏng, số thật sẽ xấu hơn.

---

## 1. Tóm tắt những gì đã làm

| Hạng mục | Nội dung | Trạng thái |
|---|---|---|
| Thông số thiết bị | DJI Dock 3, Matrice 4TD (ghi nhầm "Mavic 4TD" trong PDF), AL1, AS1, D-RTK 3 | Đã đọc, đã dùng để lập kế hoạch bay |
| Kế hoạch bay | 3 chuyến mỗi đợt: lưới nadir, quét mặt đứng, cận cảnh tầng trên cùng; độ phủ, cài đặt camera, GCP, thời điểm, tần suất | Đã đề xuất, đã soạn thư gửi công ty và GVHD |
| Đọc IFC | `bim_loader.py` đọc 2.705 cấu kiện (995 cột, 1.413 dầm, 297 sàn), 0 lỗi | **Đã chạy trên PLM.ifc thật** |
| Kiểm tra tầng | `check_levels.py`: 17 cao độ, cột lệch +1 tầng so với nhãn Revit | **Đã chạy trên dữ liệu thật** |
| Mô phỏng as-built | `simulate_asbuilt.py`: cloud giả từ BIM, có thể thêm lệch thi công, giàn giáo, ván khuôn, che khuất | Chạy được, chỉ dữ liệu giả |
| Đăng ký | `registration.py`: ICP point-to-plane (Open3D, có bản dự phòng numpy), Umeyama để khớp có scale | Chạy được trên dữ liệu giả |
| Đánh giá tiến độ | `progress_evaluator.py`: coverage theo cấu kiện, phân loại, so với lịch | Chạy được trên dữ liệu giả |
| Đọc lịch | `schedule_loader.py`: đọc CSV TimeLiner, gán ngày kế hoạch cho tầng | Thử trên CSV giả, **chưa thử CSV thật** |
| Độ nhìn thấy | `visibility.py`: ray-casting (numpy đã thử, Open3D chưa thử) | Chạy được trên dữ liệu giả |
| Hợp nhất nhiều lần quét | `fusion.py`: trạng thái từng cấu kiện (chưa rõ / chưa xây / đã xây / mâu thuẫn) | Chạy được trên dữ liệu giả |
| Xử lý ảnh thật | Đọc point cloud ODM, khớp thô bằng GCP, chạy toàn bộ cho một đợt bay thật | **Chưa viết** (cần mẫu dữ liệu ODM thật, xem mục 8) |

---

## 2. Cấu trúc thư mục

```
pipeline_v2\
├── PLM.ifc                     <- mô hình kết cấu (IFC2X3, từ Revit)
├── lich.csv                    <- lịch xuất từ TimeLiner (bạn tự xuất, xem 5.3)
├── data\                       <- tạo bởi bim_loader.py
│   ├── plm_elements.json       (metadata + bbox + thể tích từng cấu kiện)
│   └── plm_meshes.npz          (mesh tất cả cấu kiện, đơn vị mét)
├── results\                    <- kết quả demo (json, png)
└── pipeline\
    ├── config.py               đường dẫn, ngưỡng (sửa ở đây, không sửa rải rác)
    ├── bim_loader.py           IFC -> data\plm_elements.json + plm_meshes.npz
    ├── check_levels.py         kiểm tra cao độ tầng, nhãn tầng so với hình học
    ├── mesh_utils.py           đọc dữ liệu BIM, gán tầng theo cao độ thật, lấy mẫu bề mặt
    ├── schedule_loader.py      CSV TimeLiner -> bảng "tầng <-> ngày kế hoạch"
    ├── simulate_asbuilt.py     sinh point cloud giả từ BIM (có đáp án) để kiểm thử
    ├── registration.py         đăng ký point cloud vào hệ tọa độ BIM (ICP, Umeyama)
    ├── progress_evaluator.py   coverage -> đã xây / chưa xây, so với lịch
    ├── visibility.py           độ nhìn thấy từng cấu kiện bằng ray-casting
    ├── fusion.py               hợp nhất nhiều lần quét theo trạng thái cấu kiện
    ├── run_demo.py             demo một lần quét (đăng ký + đánh giá + so lịch)
    ├── run_fusion_demo.py      demo nhiều lần quét (lịch + ray-casting + hợp nhất)
    ├── make_synth.py           tạo tòa nhà giả 10 tầng để thử khi chưa có IFC
    └── lich_timeliner_gia_mau.csv   lịch mẫu (giả) để thử schedule_loader
```

**Lưu ý đường dẫn:** các file `.py` nằm trong thư mục con `pipeline\`, còn `data\`, `results\`, `PLM.ifc` nằm ở
`pipeline_v2\`. Vì vậy trong `pipeline\config.py` dòng `ROOT` phải là:

```python
ROOT = Path(__file__).resolve().parent.parent
```

---

## 3. Flow tổng thể

```
PLM.ifc ──[bim_loader]──► data\plm_elements.json + plm_meshes.npz ──┐
                                                                    │
lich.csv (TimeLiner) ──[schedule_loader]──► bảng tầng <-> ngày ─────┤
                                                                    ▼
Ảnh drone ──[WebODM, theo từng khối]──► point cloud ──[đăng ký: GCP + ICP]──► hệ tọa độ BIM
                                                                    │
                          cho từng cấu kiện BIM: (a) nhìn thấy được bao nhiêu? [visibility]
                                                 (b) phần nhìn thấy có điểm point cloud không? [evidence]
                                                                    ▼
                          trạng thái: đã xây / chưa xây / chưa rõ (bị che) / mâu thuẫn
                                                                    │
                  nhớ trạng thái qua nhiều lần quét [fusion] ──► mô hình hợp nhất + báo cáo theo tầng
                                                                    │
                                              so với lịch kế hoạch (tầng đáng lẽ xong) ──► chậm / đúng / nhanh
```

Các quyết định thiết kế chính:

- **Gắn tầng theo cao độ sàn thật** (`mesh_utils.slab_levels/assign_floors`), không theo nhãn tầng IFC, vì IFC có
  21 dầm bị gắn nhãn sai tầng.
- **So sánh theo cấu kiện BIM** (từ BIM sang point cloud): mỗi cấu kiện đo tỷ lệ bề mặt có điểm point cloud
  trong `tol` (mặc định 10 cm).
- **Không kết luận "chưa xây" khi chưa nhìn thấy:** chỉ khi cấu kiện đủ nhìn thấy (`vis`) mới được coi là "chưa có".
- **Trạng thái nhớ qua các lần quét:** cột đã đổ không tự mất đi; bị tầng trên che ở lần sau thì giữ nguyên trạng thái cũ.
- **Mỗi lần quét dựng ODM riêng**, đăng ký riêng vào BIM, không trộn ảnh của nhiều ngày vào một project.

---

## 4. Cài môi trường Python

Dùng conda, tạo môi trường riêng (không cài vào `base`):

```powershell
conda create -n bim python=3.11 -y
conda activate bim
pip install numpy scipy matplotlib open3d ifcopenshell
```

Nếu `pip install ifcopenshell` báo lỗi: `conda install -c conda-forge ifcopenshell`.
Trong VS Code chọn đúng interpreter: Ctrl+Shift+P, "Python: Select Interpreter", chọn môi trường `bim`.

Mọi lệnh bên dưới chạy từ thư mục `pipeline_v2\` (PowerShell), với môi trường `bim` đang bật.

---

## 5. Chạy với dữ liệu BIM thật (chưa cần ảnh drone)

### 5.1 Đọc IFC (chạy một lần)

```powershell
python pipeline\bim_loader.py
# hoặc chỉ rõ đường dẫn:  python pipeline\bim_loader.py "D:\...\PLM.ifc"
```

Kết quả đã đối chiếu: `Tổng cấu kiện: 2705 | có hình học: 2705 | lỗi: 0`, bbox khoảng 56 × 79 m, cao 0,8 đến 55 m.
Tạo `data\plm_elements.json` và `data\plm_meshes.npz`.

### 5.2 Kiểm tra cao độ tầng

```powershell
python pipeline\check_levels.py
```

Kết quả đã có trên dữ liệu thật:

- 17 cao độ tầng, cách nhau đều 3,3 m từ tầng 2 đến 12.
- Hai cao độ bất thường: tầng hình học 0 (Z = 3,84 m, chỉ 2 sàn, cách tầng kế 1,67 m) và tầng 16 (Z = 54,45 m, 4 sàn, cách 1,60 m).
- **Cột lệch +1 tầng** so với nhãn Revit (944/995 cột): Revit gắn cột theo cao độ chân cột. Dầm và sàn lệch +0.
- 21 dầm gắn nhãn "TẦNG 1" nhưng nằm ở cao độ 13,8 đến 47,6 m (không ảnh hưởng vì gắn tầng theo hình học).

### 5.3 Xuất lịch từ Navisworks và đọc lịch

1. Trong Navisworks: TimeLiner, tab **Tasks**, **Export Schedule**, chọn CSV, lưu thành `lich.csv` ở `pipeline_v2\`.
   (Tên nút có thể khác theo phiên bản.)
2. Chạy:

```powershell
python pipeline\schedule_loader.py lich.csv --date 2026-10-15
```

3. Đối chiếu bảng "tầng, bắt đầu, kết thúc" in ra với TimeLiner. Nếu tên cột trong CSV khác, sửa `COLUMN_ALIASES`
   ở đầu `schedule_loader.py`. Ngày thường là tháng/ngày/năm (tự phát hiện), hãy kiểm tra bằng mắt.

**Cần kiểm tra thêm trong Navisworks:** chọn một task (ví dụ "TẦNG 10") và xem cột được tô sáng nằm dưới hay trên
sàn tầng 10. Nếu lịch nhóm cột theo nhãn Revit (cột nằm trên sàn) thì dùng `--floor-mode label` ở bước 5.5,
ngược lại dùng mặc định `geometry`.

### 5.4 Demo một lần quét (BIM thật + cloud giả)

```powershell
python pipeline\run_demo.py --n-top 8
```

`--n-top 8` nghĩa là giả lập công trình đã xây đến tầng hình học thứ 8 (cao độ 28,59 m). Lệnh này chạy:
đăng ký với sai số định vị kiểu GPS, thí nghiệm độ nhạy theo sai số cao độ, đánh giá tiến độ, so với lịch, và
(trừ khi thêm `--skip-realistic`) một kịch bản khó hơn có lệch thi công, giàn giáo, ván khuôn, che khuất.
Ra `results\demo_results.json` và `results\demo_progress.png`. Mô hình thật có nhiều bề mặt hơn bản giả nên có thể
mất vài phút và dùng nhiều RAM; nếu thiếu bộ nhớ, hạ `density` trong `simulate_cloud`/`element_coverage`.

### 5.5 Demo nhiều lần quét (BIM thật + lịch thật + cloud giả)

```powershell
python pipeline\run_fusion_demo.py --schedule lich.csv --epochs 3,5,7 --floor-mode geometry
```

`--epochs`: tầng đang đổ ở mỗi lần quét giả lập (phải có trong bảng lịch ở 5.3). `--floor-mode label` nếu lịch
nhóm theo nhãn tầng Revit. `--r-present 0.35` để phát hiện nhiều hơn (đổi lại có báo nhầm). Ra `results\fusion_results.json`
và `results\fused_cloud.npz`.

### 5.6 Thử nhanh khi chưa có IFC hoặc muốn kiểm tra nhanh

```powershell
python pipeline\make_synth.py
python pipeline\run_demo.py --data test\clean --out results_synth --skip-realistic
python pipeline\run_fusion_demo.py --data test\clean --schedule pipeline\lich_timeliner_gia_mau.csv --out results_synth
```

---

## 6. WebODM và Docker

### 6.1 Cài đặt

Yêu cầu: Windows 10 (21H2 trở lên) hoặc 11, bật ảo hóa (VT-x) trong BIOS, [Docker Desktop](https://www.docker.com/products/docker-desktop/),
Git. Chạy trong **Git Bash**:

```bash
git clone https://github.com/OpenDroneMap/WebODM --config core.autocrlf=input --depth 1
cd WebODM
./webodm.sh start
```

Mở trình duyệt tại `http://localhost:8000`, tạo tài khoản quản trị lần đầu.

### 6.2 Cấp RAM cho Docker (Windows, WSL2)

Tạo file `C:\Users\<tên>\.wslconfig` (ví dụ máy 32 GB), rồi chạy `wsl --shutdown` trong PowerShell và mở lại Docker Desktop:

```
[wsl2]
memory=24GB
processors=8
swap=32GB
```

Tài liệu WebODM nhắc: nếu `./webodm.sh start` lỗi lặp đi lặp lại với thông báo khác nhau mỗi lần, rất có thể thiếu RAM.

### 6.3 Dời dữ liệu sang ổ khác (tránh đầy ổ C)

```bash
./webodm.sh restart --media-dir /d/webodm_data --db-dir /d/webodm_db
```

(Trong Git Bash, ổ `D:` thường viết là `/d/...`. Nếu lỗi, xem `./webodm.sh --help`.)

### 6.4 Lệnh quản lý và reset

| Việc | Lệnh (Git Bash, trong thư mục `WebODM`) |
|---|---|
| Khởi động | `./webodm.sh start` |
| Dừng | `./webodm.sh stop` |
| Khởi động lại | `./webodm.sh restart` |
| Dừng và gỡ container | `./webodm.sh down` |
| Cập nhật phiên bản | `./webodm.sh update` |
| Quên mật khẩu admin | `./webodm.sh down`, rồi `./webodm.sh start && ./webodm.sh resetadminpassword <mật_khẩu_mới>` |
| Mọi tùy chọn | `./webodm.sh --help` |
| **Reset hẳn khi lỗi không rõ** | Xóa thư mục `WebODM`, `git clone` lại như 6.1 (đây là cách tài liệu gợi ý) |
| Xóa toàn bộ dữ liệu cũ | Trong Docker Desktop, mục Volumes, xóa các volume của WebODM. **Mất mọi project và kết quả đã xử lý.** |

### 6.4b Quy trình xử lý ảnh một đợt bay

1. Tạo project, tải ảnh lên theo **khối** (khoảng 300–400 ảnh mỗi khối, theo từng chuyến hoặc từng mặt đứng; hai khối kề nhau chồng lấn 20–30%). Không trộn ảnh của hai ngày khác nhau.
2. Tải kèm file GCP `gcp_list.txt` (dòng đầu là hệ tọa độ, ví dụ `EPSG:32648` cho UTM 48N khu vực TP.HCM; mỗi dòng sau là `x y z px py tên_ảnh`). Xem mục "GCP file format" trong tài liệu ODM.
3. Chọn thông số (xem tài liệu ODM của từng tùy chọn: `feature-quality`, `pc-quality`, `resize-to`, `pc-filter`, `pc-sample`, `split`, `split-overlap`). Gợi ý khởi điểm: chất lượng `high` thay vì `ultra`; chụp 48MP nhưng cho WebODM xử lý ảnh đã hạ độ phân giải (ngưỡng so sánh ~10 cm nên 12–20MP là đủ).
4. Khi xong, tải point cloud (`.laz`) hoặc "All assets" về máy.

**Ước lượng thô (chưa đo trên máy bạn):** 1.500–2.000 ảnh 48MP khoảng 25–50 GB; mỗi khối 300–400 ảnh mất khoảng 1,5–4 giờ, cả đợt 1–2 đêm máy chạy; thư mục làm việc phình gấp 3–5 lần dung lượng ảnh. Hãy tự đo bằng một bộ 100–150 ảnh mẫu trước.

---

## 7. Kế hoạch bay chụp (tóm tắt)

| Chuyến | Mục đích | Cấu hình |
|---|---|---|
| 1. Lưới nadir | Bối cảnh, sàn đang thi công, điểm khống chế | Camera nhìn xuống, cao 100–120 m (và cao hơn đỉnh cần cẩu 15–20 m), phủ 80/70 |
| 2. Quét mặt đứng | Chi tiết cột, dầm từng tầng | Vòng kín quanh công trình cách mặt đứng 30–40 m, camera 0° đến -15°, khoảng 6 hàng cách ~10 m, hàng cao nhất -20° đến -30°, phủ 85/75, bay hai lần ở hai góc camera |
| 3. Cận cảnh tầng trên | Chi tiết nơi đang thi công | Cách 15–20 m, 2–3 tầng cao nhất, có thể dùng tele 70 mm |

- **Mặt bằng công trình không phải hình chữ nhật** (nêm và nhiều cánh): vòng bay ở chuyến 2 phải bám theo đa giác chân công trình.
- **Camera:** JPEG 48MP, tắt zoom số và HDR, cân bằng trắng cố định, lấy nét vô cực, màn trập từ 1/800, ISO tự động không quá 400, tốc độ 3–4 m/s, chụp theo khoảng cách (6–7 m một ảnh).
- **Georeference:** 5–8 GCP rải quanh công trình (đo RTK hoặc toàn đạc) cộng 2–3 điểm kiểm tra; EXIF lưu trạng thái RTK; D-RTK 3 đặt cố định cùng một vị trí ở mọi đợt.
- **Thời điểm:** sáng 7:30–11:00 (tháng 10 ở TP.HCM hay giông chiều), gió dưới 8 m/s.
- **Tần suất:** hàng tuần là hợp lý (một tầng đổ xong sau 7–10 ngày); với đồ án xin ít nhất 2 đợt cách nhau 2–3 tuần.
- **Cần cẩu:** hỏi chiều cao và vị trí; drone khó thấy dây cáp, và cần cẩu lọt vào ảnh thành vật thể thừa trong mô hình.
- **Giàn giáo:** không cố xóa hoàn toàn. Dùng mask ảnh, lọc point cloud, và quan trọng nhất là chỉ giữ điểm trong vỏ ±10 cm quanh bề mặt BIM.

---

## 8. Việc còn thiếu (đã nói rõ để khỏi hiểu nhầm)

1. **Script xử lý ảnh thật** (chưa viết): đọc point cloud ODM (`laspy`), khớp thô vào BIM bằng GCP (`registration.umeyama`) rồi ICP, tính bằng chứng, cập nhật trạng thái cho từng đợt bay. Cần một mẫu đầu ra thật của ODM (point cloud nhỏ, `shots.geojson`, `coords.txt`, `gcp_list.txt`) để viết cho khớp hệ tọa độ và độ dịch gốc.
2. **Vị trí máy bay thật** cho `visibility.py` (hiện dùng vị trí giả): lấy từ EXIF/log RTK và đưa vào hệ tọa độ BIM.
3. **Kiểm chứng `visibility.py` bằng Open3D** (mới thử bản numpy) và chạy `registration.py` bằng Open3D (mô phỏng dùng bản dự phòng numpy).
4. **Chỉnh ngưỡng** (`tol`, `t_built`, `t_not`, `r_present`, `r_absent`, `v_min`, `v_conflict`) trên ảnh thật.
5. **Xác nhận cách lịch nhóm cấu kiện** (cột theo nhãn Revit hay theo hình học) trong Navisworks.

---

## 9. Kết quả mô phỏng và giới hạn

Trên tòa nhà giả 10 tầng, 3 lần quét, cloud khó (lệch thi công 2 cm, lưới che, ván khuôn, che khuất), so với đáp án lần cuối:

| Cách | Precision | Recall |
|---|---|---|
| Coverage của lần cuối (cách cũ) | ~0,86 | ~0,52 |
| Chỉ lần cuối, có tính độ nhìn thấy | ~1,00 | ~0,45 |
| Hợp nhất 3 lần (`r_present` = 0,5) | ~1,00 | ~0,52 |
| Hợp nhất 3 lần (`r_present` = 0,35) | ~0,91 | ~0,66 |

Số liệu dao động nhẹ giữa các lần chạy (nhiễu ngẫu nhiên), nên chỉ đọc theo xu hướng.

Giới hạn cần ghi vào báo cáo:

- Cloud giả và phần đánh giá dùng cùng một BIM; số liệu thật sẽ xấu hơn.
- Sai số đăng ký trong mô phỏng khoảng 8–10 cm (bản ICP dự phòng); không hứa dưới 10 cm khi chưa đo trên dữ liệu thật.
- Cao độ ban đầu sai từ khoảng 1,65 m trở lên làm ICP khớp nhầm tầng (các tầng lặp lại ~3,3 m): phải khóa cao độ bằng RTK hoặc GCP.
- **Ván khuôn dầm/sàn nằm đúng chỗ cấu kiện sẽ đổ**, nên hình học không phân biệt "đã đổ bê tông" với "mới dựng ván khuôn". Muốn phân biệt phải dùng thêm IFC ván khuôn (6.089 cấu kiện `TS_FormWork` đang bị bỏ qua) hoặc phân loại ảnh.
- Drone chỉ thấy bên ngoài và mặt trên; cấu kiện bên trong sẽ ở trạng thái "chưa rõ". Nên báo cáo ba loại (đã xây, chưa xây, không kiểm chứng được) thay vì một con số phần trăm duy nhất.
- Giàn giáo, cần cẩu và công trình bên cạnh chưa được đưa vào vật che chắn của `visibility.py`, nên độ nhìn thấy là cận trên.

---

## 10. Hướng mở rộng

### 10.1 Nhiều nhà giống hệt nhau trong một khu

Hình học không phân biệt được hai nhà giống nhau, nên xác định nhà bằng vị trí tuyệt đối (RTK/GCP, hệ UTM 48N), không bằng hình dạng.
Cắt point cloud theo đa giác chân móng từng nhà trước khi đăng ký; chặn ICP bằng ngưỡng lệch so với ước lượng ban đầu;
đặt mốc có mã (ArUco/AprilTag) mỗi dãy; chụp biển số nhà. Trong code: khóa trạng thái theo cặp (instance, GlobalId),
tách "kiểu BIM" khỏi "phép biến đổi đặt nhà", mỗi nhà một lịch riêng.

### 10.2 Kết hợp với nhóm dựng 3D bên trong (camera gắn người giám sát, cảm biến trong từng phòng)

Hai nhóm bổ sung cho nhau: drone thấy bên ngoài và mặt trên, nhóm kia thấy bên trong, nên phần "chưa rõ (bị che)" của nhóm mình
có thể được lấp bằng dữ liệu của nhóm kia. Để sau này ghép được, hai nhóm nên thống nhất sớm:

- **Cùng một IFC** (`PLM.ifc`) và cùng khóa cấu kiện là **GlobalId**.
- **Cùng hệ tọa độ**: hệ tọa độ BIM, đơn vị mét (đầu ra của `bim_loader.py`), và dùng chung vài điểm khống chế (giao điểm lưới trục cột) có thể nhìn thấy từ cả trong lẫn ngoài.
- **Cùng định dạng trao đổi:** point cloud đã đăng ký vào hệ tọa độ BIM (`.ply` hoặc `.laz`) kèm vị trí camera (N×3, mét), và bảng trạng thái theo GlobalId (đã xây, chưa xây, chưa rõ, độ tin cậy, thời điểm).
- **Cách ghép trạng thái:** mỗi nguồn là một "lần quan sát" đưa vào `fusion.FusionState.update(...)` (vị trí camera trong nhà đưa vào `visibility.evidence` thành thêm `cams`); cấu kiện nào một nguồn nhìn rõ và thấy thì là "đã xây"; hai nguồn mâu thuẫn thì gắn "cần kiểm tra thủ công".

Mình ghi chú ở đây để thiết kế hiện tại không cản trở việc ghép về sau; việc ghép là phần việc sau.

---

## 11. Xử lý sự cố thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| `ModuleNotFoundError: ifcopenshell` hoặc `open3d` | Chưa bật đúng môi trường `bim` hoặc chưa cài; xem mục 4. Python 3.14 có thể chưa có gói cài sẵn, dùng Python 3.11 |
| `FileNotFoundError: data\plm_elements.json` | Chưa chạy `bim_loader.py`, hoặc `ROOT` trong `config.py` chưa đúng (mục 2) |
| `KeyError` hoặc "Bỏ qua tầng ... không có trong lịch" khi chạy `run_fusion_demo.py` | Giá trị trong `--epochs` không có trong bảng lịch của `schedule_loader.py`; chọn tầng có trong bảng |
| `schedule_loader.py` báo không tìm thấy cột | Tên cột trong CSV khác; sửa `COLUMN_ALIASES` |
| Lịch ngày/tháng bị đảo | Kiểm tra dòng "kiểu ngày" in ra, đối chiếu một ngày cụ thể với TimeLiner |
| `run_demo.py` hết RAM hoặc chạy rất lâu | Giảm `density` trong các hàm lấy mẫu, hoặc thêm `--skip-realistic` |
| ICP khớp nhầm tầng | Sai số cao độ ban đầu quá lớn; khóa cao độ bằng RTK/GCP trước |
| `./webodm.sh start` lỗi, thông báo khác nhau mỗi lần | Thường thiếu RAM cấp cho Docker; chỉnh `.wslconfig` (6.2), khởi động lại máy |
| WebODM hết dung lượng ổ C | Dời dữ liệu bằng `--media-dir`/`--db-dir` (6.3) |