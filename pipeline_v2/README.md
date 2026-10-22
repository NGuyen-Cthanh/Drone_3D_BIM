# Đánh giá tiến độ thi công bằng ảnh drone và mô hình BIM

Đồ án: dựng mô hình 3D của công trình từ ảnh drone (WebODM/OpenDroneMap), đăng ký vào mô hình BIM (IFC), so sánh theo
từng cấu kiện để biết cấu kiện nào đã xây, chưa xây hay không kiểm chứng được, rồi so với lịch thi công (Navisworks TimeLiner).

Cập nhật lần cuối: 22/10/2026.

> **Trạng thái trung thực.** Phần đọc IFC, kiểm tra tầng và đọc lịch đã chạy trên **dữ liệu thật** (`PLM.ifc`, `lich.csv`,
> và quy ước gán tầng đã đối chiếu bằng Navisworks). Phần mô phỏng, đăng ký, đánh giá, hợp nhất nhiều lần quét mới chạy trên
> **point cloud giả lập** sinh từ chính BIM. **Chưa có ảnh drone thật của công trình.** Mọi con số độ chính xác bên dưới
> là của mô phỏng; số thật sẽ xấu hơn.

## Mục lục

1. [Những gì đã làm](#1-những-gì-đã-làm)
2. [Luồng chạy](#2-luồng-chạy)
3. [Cấu trúc thư mục và vai trò từng file](#3-cấu-trúc-thư-mục-và-vai-trò-từng-file)
4. [Cài môi trường Python](#4-cài-môi-trường-python)
5. [Chạy với dữ liệu BIM và lịch thật](#5-chạy-với-dữ-liệu-bim-và-lịch-thật)
6. [Quy ước gán lịch vào cấu kiện (đã xác nhận)](#6-quy-ước-gán-lịch-vào-cấu-kiện-đã-xác-nhận)
7. [WebODM và Docker](#7-webodm-và-docker)
8. [Kế hoạch bay chụp](#8-kế-hoạch-bay-chụp)
9. [Kết quả mô phỏng và giới hạn](#9-kết-quả-mô-phỏng-và-giới-hạn)
10. [Việc còn lại](#10-việc-còn-lại)
11. [Câu hỏi còn mở cho GVHD và công ty](#11-câu-hỏi-còn-mở-cho-gvhd-và-công-ty)
12. [Hướng mở rộng](#12-hướng-mở-rộng)
13. [Xử lý sự cố](#13-xử-lý-sự-cố)
14. [Phụ lục: số liệu `PLM.ifc` và cấu trúc file `.nwd`](#14-phụ-lục-số-liệu-plmifc-và-cấu-trúc-file-nwd)

---

## 1. Những gì đã làm

| Hạng mục | Nội dung | Trạng thái |
|---|---|---|
| Phân công công cụ | Công ty bay (DJI Dock 3 + Matrice 4TD + D-RTK 3); WebODM dựng 3D; Python (IfcOpenShell, Open3D, SciPy) đọc BIM, căn chỉnh, đánh giá; Revit và Navisworks để xem mô hình và lịch 4D | Đã thống nhất |
| Kế hoạch bay | 3 chuyến mỗi đợt, độ phủ, camera, GCP, thời điểm, tần suất (mục 8) | Đã đề xuất |
| Đọc IFC | `bim_loader.py` đọc 2.705 cấu kiện (995 cột, 1.413 dầm, 297 sàn), 0 lỗi | **Chạy trên `PLM.ifc` thật** |
| Kiểm tra tầng | `check_levels.py`: 17 cao độ tầng, cột lệch +1 tầng so với nhãn Revit | **Chạy trên dữ liệu thật** |
| Đọc lịch | `schedule_loader.py` đọc `lich.csv` (CSV TimeLiner thật), gán task vào tầng/vai trò | **Chạy trên CSV thật, quy ước đã xác nhận bằng Navisworks** (mục 6) |
| Mô phỏng as-built | `simulate_asbuilt.py`: cloud giả từ BIM, tùy chọn lệch thi công, giàn giáo, ván khuôn, che khuất | Chạy được, chỉ dữ liệu giả |
| Đăng ký | `registration.py`: ICP point-to-plane (Open3D, có bản dự phòng numpy), Umeyama khớp có scale | Chạy được trên dữ liệu giả (chỉ bản numpy đã thử) |
| Đánh giá tiến độ | `progress_evaluator.py`: coverage theo cấu kiện, phân loại, so với lịch (`compare_with_plan`) | Chạy được trên dữ liệu giả |
| Độ nhìn thấy | `visibility.py`: ray-casting (numpy đã thử, Open3D chưa thử) | Chạy được trên dữ liệu giả |
| Hợp nhất nhiều lần quét | `fusion.py`: trạng thái từng cấu kiện (chưa rõ / chưa xây / đã xây / mâu thuẫn) | Chạy được trên dữ liệu giả |
| WebODM | Cài và chạy thử bộ ảnh mẫu banana: 15/16 ảnh dùng, 15.823 điểm thưa, 1.158.107 điểm dày, 12 phút | Đã chạy |
| Xử lý ảnh drone thật | Đọc point cloud ODM, căn thô bằng GCP, chạy cho một đợt bay thật | **Chưa viết** (chờ dữ liệu, mục 10) |

---

## 2. Luồng chạy

```
PLM.ifc ──[bim_loader]──► data\plm_elements.json + plm_meshes.npz ──┐
                                                                    │
lich.csv (TimeLiner) ──[schedule_loader]──► bảng tầng ↔ ngày ───────┤
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
                           so với lịch tại ngày báo cáo [compare_with_plan] ──► chậm / đúng / nhanh / chưa kiểm chứng
```

Các quyết định thiết kế chính:

- **Gán tầng theo cao độ sàn thật** (`mesh_utils.slab_levels/assign_floors`) khi đánh giá, không theo nhãn tầng IFC, vì IFC có
  21 dầm bị gắn nhãn sai tầng.
- **Gán task lịch vào cấu kiện theo nhãn Revit** (`--floor-mode label`, mặc định), vì lịch nhóm cấu kiện theo nhãn (mục 6).
- **So sánh theo cấu kiện BIM** (từ BIM sang point cloud): mỗi cấu kiện đo tỷ lệ bề mặt có điểm point cloud trong `tol` (10 cm).
- **Không kết luận "chưa xây" khi chưa nhìn thấy:** chỉ khi cấu kiện đủ nhìn thấy (`vis`) mới được coi là "chưa có".
- **Trạng thái nhớ qua các lần quét:** cột đã đổ không tự mất đi; bị tầng trên che ở lần sau thì giữ nguyên trạng thái cũ.
- **Mỗi lần quét dựng ODM riêng**, đăng ký riêng vào BIM, không trộn ảnh nhiều ngày vào một project.
- **"Bị che" không phải "trễ":** `compare_with_plan` tách riêng *trễ* (nhìn rõ mà không thấy), *chưa kiểm chứng* (bị che), *vượt*.

---

## 3. Cấu trúc thư mục và vai trò từng file

```
pipeline_v2\
├── PLM.ifc                     mô hình kết cấu (IFC2X3, từ Revit)
├── lich.csv                    lịch xuất từ TimeLiner (CSV thật, 61 task)
├── README.md
├── data\                       tạo bởi bim_loader.py
│   ├── plm_elements.json       metadata + bbox + thể tích từng cấu kiện
│   └── plm_meshes.npz          mesh tất cả cấu kiện (đơn vị mét)
├── results\                    kết quả demo (json, png, npz)
└── pipeline\
    ├── config.py               đường dẫn và ngưỡng (sửa ở đây, không sửa rải rác)
    ├── bim_loader.py           IFC → data\plm_elements.json + plm_meshes.npz
    ├── check_levels.py         kiểm tra cao độ tầng, so nhãn tầng IFC với tầng hình học
    ├── mesh_utils.py           đọc dữ liệu BIM, gán tầng theo cao độ, lấy mẫu bề mặt, sửa chiều mesh
    ├── schedule_loader.py      CSV TimeLiner → bảng "tầng ↔ ngày"; mặt nạ "kế hoạch cho là đã xây"
    ├── simulate_asbuilt.py     sinh point cloud giả từ BIM (có đáp án) để kiểm thử
    ├── registration.py         đăng ký point cloud vào hệ tọa độ BIM (ICP, FPFH+RANSAC, Umeyama)
    ├── progress_evaluator.py   coverage → đã xây / chưa xây; tổng hợp theo tầng; so với lịch
    ├── visibility.py           độ nhìn thấy từng cấu kiện bằng ray-casting
    ├── fusion.py               hợp nhất nhiều lần quét theo trạng thái cấu kiện
    ├── run_demo.py             demo một lần quét (đăng ký + đánh giá), thí nghiệm độ nhạy
    ├── run_fusion_demo.py      demo nhiều lần quét (lịch + ray-casting + hợp nhất + so với lịch)
    ├── make_synth.py           tạo tòa nhà giả 10 tầng để thử khi chưa có IFC
    └── lich_timeliner_gia_mau.csv   lịch mẫu GIẢ (cột tiếng Anh, task "Cột TẦNG n- KC") để thử schedule_loader
```

**Lưu ý đường dẫn:** các file `.py` nằm trong `pipeline\`, còn `data\`, `results\`, `PLM.ifc` nằm ở `pipeline_v2\`, nên
`config.py` dùng `ROOT = Path(__file__).resolve().parent.parent`.

Ghi chú về file trong thư mục tải lên: `PLM_1.ifc` giống `PLM.ifc` từng byte, có thể xóa.

---

## 4. Cài môi trường Python

Dùng conda, tạo môi trường riêng (không cài vào `base`):

```powershell
conda create -n bim python=3.11 -y
conda activate bim
pip install numpy scipy matplotlib open3d ifcopenshell
```

Nếu `pip install ifcopenshell` lỗi: `conda install -c conda-forge ifcopenshell`. Đọc point cloud `.laz` của ODM cần thêm
`pip install laspy[lazrs]`. Trong VS Code chọn interpreter: Ctrl+Shift+P → "Python: Select Interpreter" → môi trường `bim`.
Python 3.14 có thể chưa có gói cài sẵn, dùng 3.11.

Mọi lệnh bên dưới chạy từ `pipeline_v2\` (PowerShell) với môi trường `bim` đang bật. Không có `open3d` thì code tự dùng ICP
numpy (chậm hơn, đủ để kiểm thử).

---

## 5. Chạy với dữ liệu BIM và lịch thật

### 5.1 Đọc IFC (chạy một lần)

```powershell
python pipeline\bim_loader.py
# hoặc:  python pipeline\bim_loader.py "D:\...\PLM.ifc" --out data
```

Kết quả đã đối chiếu: `Tổng cấu kiện: 2705 | có hình học: 2705 | lỗi: 0`, bbox khoảng 56 × 79 m, cao 0,8 đến 55 m.
Tạo `data\plm_elements.json` và `data\plm_meshes.npz` (cần cả hai file ở các bước sau).

### 5.2 Kiểm tra cao độ tầng

```powershell
python pipeline\check_levels.py
```

Kết quả trên dữ liệu thật:

- 17 cao độ tầng, cách nhau đều ~3,3 m từ tầng 2 đến 12.
- Hai cao độ bất thường: chỉ số 0 (Z = 3,84 m, 2 sàn, cách tầng kế 1,67 m) và chỉ số 16 (Z = 54,45 m, 4 sàn, cách 1,60 m).
- **Cột lệch +1 tầng** so với nhãn Revit (944/995 cột): Revit gắn cột theo cao độ **chân** cột. Dầm và sàn lệch +0.
- 21 dầm gắn nhãn "TẦNG 1" nhưng nằm ở cao độ 13,8 đến 47,6 m (không ảnh hưởng đánh giá vì gán tầng theo hình học).

### 5.3 Đọc lịch

Xuất lịch: TimeLiner → tab **Tasks** → **Export Schedule** → CSV, lưu thành `lich.csv`. Sau đó:

```powershell
python pipeline\schedule_loader.py lich.csv --date 2026-12-20
# tùy chọn:  --ds-shift 0   --map map.json   --write-template task_chua_gan.json
```

In ra bảng "tầng, cột-vách (CV), dầm-sàn (DS), ngày kế hoạch" và danh sách task chưa gán được (kèm lý do). Kết quả với
`lich.csv`: ngày đọc đúng kiểu tháng/ngày/năm; 16 tầng có kế hoạch; 32 task bỏ qua (móng/hầm/tầng 1 của `PLM.nwc`, dòng gốc;
mục 6).

### 5.4 Demo một lần quét (BIM thật + cloud giả)

```powershell
python pipeline\run_demo.py --n-top 8
```

`--n-top 8` = giả lập công trình xây đến tầng hình học thứ 8. Chạy: đăng ký với sai số kiểu GPS, độ nhạy theo sai số cao độ,
đánh giá tiến độ, kịch bản khó (lệch thi công, giàn giáo, ván khuôn, che khuất; bỏ bằng `--skip-realistic`).
Ra `results\demo_results.json` và `results\demo_progress.png`. Hết RAM thì giảm `density` trong `simulate_cloud` và
`element_coverage`. **Lưu ý:** `run_demo.py` vẫn dùng `compare_with_schedule` cũ (so theo chỉ số tầng hình học, `N_TOP+1` giả định);
phần so với lịch thật nằm ở `run_fusion_demo.py`.

### 5.5 Demo nhiều lần quét (BIM thật + lịch thật + cloud giả)

```powershell
python pipeline\run_fusion_demo.py --schedule lich.csv --epochs 3,5,7
```

| Tham số | Ý nghĩa |
|---|---|
| `--epochs 3,5,7` | tầng hình học đang đổ ở mỗi lần quét giả lập (phải có trong bảng lịch) |
| `--floor-mode label` | (mặc định, **đã xác nhận**) gán lịch theo nhãn tầng Revit; `geometry` lệch 1 tầng với cột, chỉ để đối chiếu |
| `--ds-shift 0` | (mặc định, **đã xác nhận**) `DS<n>F` = dầm sàn nhãn "TẦNG n" |
| `--map map.json` | gán tay task → tầng/vai trò (chỉ cần với task bất thường; **không dùng cho `Z*-S1`**, xem mục 6) |
| `--report-date 2027-02-01` | ngày so với lịch (mặc định: ngày của lần quét cuối) |
| `--assume-up-to N` | giả định mọi cấu kiện ở tầng ≤ N đã xây (làm vật che và điểm neo, loại khỏi số liệu đánh giá) |
| `--r-present 0.35` | phát hiện nhiều hơn (đổi lại có báo nhầm) |
| `--hpr-voxel 0.5` | voxel che khuất khi mô phỏng; tăng lên nếu chậm hoặc hết RAM |

Ra `results\fusion_results.json` và `results\fused_cloud.npz`. Chạy khoảng 2 phút trên `PLM.ifc` thật.
Dòng cuối "Kiểm tra thứ tự" in độ khớp giữa mặt nạ kế hoạch và đáp án hình học (hiện 100%); nếu thấp thì quy ước gán tầng sai.

### 5.6 Thử nhanh khi chưa có IFC

```powershell
python pipeline\make_synth.py
python pipeline\run_demo.py --data test\clean --out results_synth --skip-realistic
python pipeline\run_fusion_demo.py --data test\clean --schedule pipeline\lich_timeliner_gia_mau.csv --out results_synth
```

---

## 6. Quy ước gán lịch vào cấu kiện (đã xác nhận)

File lịch thật (`lich.csv`, dự án PALC Q9): task đặt tên bằng mã viết tắt. Đã chọn từng task trong TimeLiner với
*Auto Select Attached Items* và đối chiếu Selection Tree (tầng trệt = tầng 1):

| Task | Gắn với | Cách code gán |
|---|---|---|
| `CV<n>F` (n = 1..14) | **cột** nhãn "TẦNG n- KC", đứng **trên sàn tầng n** (`CV1F` đứng trên nền tầng trệt) | vai trò `CV`, tầng nhãn n |
| `DS<n>F` (n = 2..14) | **dầm + sàn** nhãn "TẦNG n- KC". `DS3F` = 133 cấu kiện = 100 dầm + 31 sàn của nhãn TẦNG 3 + 2 dầm 200x300 bị gán nhãn sai "TẦNG 1" | vai trò `DS`, tầng nhãn n (`DS_SHIFT = 0`) |
| `CVRF` | cột mái: nhãn MÁI không có cột nào, 126 cột nằm ở nhãn TUM | vai trò `CV`, tầng TUM |
| `DSRF` | dầm sàn mái | vai trò `DS`, tầng MÁI |
| `Z1..Z5.3-S1` (7 task) | xem bên dưới | **bỏ qua** (không có trong `PLM.ifc`) |
| `Z*-M`, `Z*-DS`, `Z*-CV`, `Z5.1-DHP`, `Z5.1-VHP`, `CKN` | móng, đài cọc, cọc, hầm (xem trong Navisworks) | **bỏ qua** (không có trong `PLM.ifc`) |

**Các task `Z*-S1`:** mỗi task gắn 27 đến 112 cấu kiện (Z2: 27, Z5.1: 61, Z5.2: 99, Z3: 99, Z4: 76, Z5.3: 102, Z1: 112).
Chúng nằm trong model **`PLM.nwc`** (không phải `PLM-TH.nwc`): TẦNG HẦM- KC (sàn, cột, tường), VỈA HÈ (cote 0.0) (sàn, cột),
ĐỈNH BỒN HOA (sàn), `<No level>` (Generic Models, dầm) và "TẦNG 1- KC" của `PLM.nwc` (Floor, dầm, Basic Wall). `PLM.ifc`
khớp `PLM-TH.nwc` (có TẦNG 1 đến MÁI, cột ở TẦNG 1, không có TẦNG HẦM), nên các task này không có cấu kiện tương ứng trong
IFC. Đây là suy luận từ cấu trúc cây, chưa so GlobalId. Vì vậy **không** gán `Z*-S1` vào tầng 1 của IFC.

Cấu kiện của `PLM.ifc` **không thuộc task nào** (bị loại khỏi so sánh với lịch): **84/2.705** = 74 dầm + sàn nhãn TUM
(không có `DS` cho TUM), 9 dầm/sàn nhãn TẦNG 1 (không có `DS1F`), 1 dầm nhãn VỈA HÈ.

Điều cần biết về file lịch:

- **Thứ tự `CV<n>F` rồi `DS<n>F`** là đúng thứ tự thi công: đổ cột trước, rồi đổ dầm sàn.
- **`CV1F` và `CV2F` có cùng ngày** (2/12 đến 8/12/2026) và không có `DS1F`. Nên hỏi người lập lịch.
- **Cột "Actual Start/End" trùng hệt "Planned"** (Actual Dates Enabled = 1): đó là bản sao, không phải tiến độ thực tế. Không dùng.
- Lịch gốc (root) kéo dài 10/8/2026 đến 15/4/2027.

---

## 7. WebODM và Docker

### 7.1 Cài đặt

Yêu cầu: Windows 10 (21H2 trở lên) hoặc 11, bật ảo hóa (VT-x) trong BIOS, WSL2, Docker Desktop, Git for Windows.
Chạy trong **Git Bash** (không dùng PowerShell vì `webodm.sh` là bash script):

```bash
git clone https://github.com/OpenDroneMap/WebODM --config core.autocrlf=input --depth 1
cd WebODM
./webodm.sh start
```

Lần đầu mất 15 đến 30 phút tải image; đừng để máy sleep. Khi thấy `WebODM should be up and running!`, mở
`http://localhost:8000`, tạo tài khoản admin, vào **Processing Nodes** và kiểm tra `node-odx-1` online. Cảnh báo vàng
`the attribute version is obsolete` là vô hại. Đường dẫn có dấu cách phải để trong ngoặc kép, ổ đĩa viết dạng `/d/`.

### 7.2 Cấp RAM cho Docker (WSL2)

Tạo `C:\Users\<tên>\.wslconfig` (ví dụ máy 32 GB), rồi chạy `wsl --shutdown` và mở lại Docker Desktop:

```ini
[wsl2]
memory=24GB
processors=8
swap=32GB
```

Nếu `./webodm.sh start` lỗi lặp đi lặp lại với thông báo khác nhau mỗi lần, rất có thể thiếu RAM.
Dời dữ liệu sang ổ khác: `./webodm.sh restart --media-dir /d/webodm_data --db-dir /d/webodm_db`.

### 7.3 Quy trình xử lý ảnh một đợt bay

1. Tạo project, tải ảnh lên theo **khối** (khoảng 300 đến 400 ảnh mỗi khối, theo chuyến hoặc mặt đứng; hai khối kề nhau chồng
   lấn 20 đến 30%). Không trộn ảnh của hai ngày khác nhau.
2. Tải kèm `gcp_list.txt` (dòng đầu là hệ tọa độ, ví dụ `EPSG:32648` UTM 48N cho TP.HCM; mỗi dòng sau là
   `x y z px py tên_ảnh`).
3. Thông số khởi điểm: `high` thay vì `ultra`; chụp 48 MP nhưng cho WebODM xử lý ảnh đã hạ độ phân giải (ngưỡng so sánh 10 cm
   nên 12 đến 20 MP là đủ). Các tùy chọn cần thử: `feature-quality`, `pc-quality`, `resize-to`, `pc-filter`, `pc-sample`,
   `split`, `split-overlap`.
4. Xong thì tải point cloud (`.laz`) hoặc "All assets" về máy.

**Quality gate trước khi dùng:** tỉ lệ ảnh được dùng ≥ 90% (xem **Task Output → On**, nút **Report**); không có lỗ lớn trên
mái và mặt sàn trên cùng (lỗ ở mặt dưới hoặc chỗ khuất là bình thường). Không đạt thì bay lại, không cố sửa bằng thuật toán.

**Ước lượng thô, chưa đo trên máy bạn:** 1.500 đến 2.000 ảnh 48 MP khoảng 25 đến 50 GB; mỗi khối 300 đến 400 ảnh mất khoảng
1,5 đến 4 giờ; thư mục làm việc phình gấp 3 đến 5 lần dung lượng ảnh. Hãy đo bằng bộ 100 đến 150 ảnh mẫu trước.

### 7.4 Lệnh quản lý

| Việc | Lệnh (Git Bash, trong thư mục `WebODM`) |
|---|---|
| Khởi động / dừng / khởi động lại | `./webodm.sh start` / `stop` / `restart` |
| Dừng và gỡ container (giữ project) | `./webodm.sh down` |
| Cập nhật | `./webodm.sh update` |
| Quên mật khẩu admin | `./webodm.sh resetadminpassword "mat_khau_moi"` |
| Máy sleep khi đang tải/xử lý | `./webodm.sh down` rồi `./webodm.sh start` |
| Reset hẳn khi lỗi không rõ | xóa thư mục `WebODM`, `git clone` lại |
| Xóa toàn bộ dữ liệu cũ | Docker Desktop → Volumes → xóa volume `webodm_*`. **Mất mọi project.** |

Point cloud nhìn như lưới chấm thưa chỉ là cách hiển thị (LOD): zoom gần, tăng Point Budget và Point Size, hoặc bấm
Textured Model. Cảnh báo `GPS position not available` nghĩa là ảnh không có geotag (như bộ banana); ảnh công trình thật phải có.

---

## 8. Kế hoạch bay chụp

Thiết bị: DJI Dock 3, Matrice 4TD (tiêu đề file thông số ghi nhầm "Mavic 4TD"), D-RTK 3, camera góc rộng 48 MP, 1/1.3 inch,
tương đương 24 mm. **Các con số dưới đây là ước tính**; công ty cần xác nhận cảm biến và tiêu cự thật (đọc từ EXIF ảnh mẫu).

| Chuyến | Mục đích | Cấu hình |
|---|---|---|
| 1. Lưới nadir | Bối cảnh, sàn đang thi công, điểm khống chế | Camera nhìn xuống, cao hơn đỉnh cần cẩu 15 đến 30 m, phủ 80/70 |
| 2. Quét mặt đứng | Chi tiết cột, dầm từng tầng | Vòng kín quanh công trình cách mặt đứng 30 đến 40 m, camera 0° đến −15°, khoảng 6 hàng cách ~10 m, hàng cao nhất −20° đến −30°, phủ 85/75, bay hai lần ở hai góc camera |
| 3. Cận cảnh tầng trên | Chi tiết nơi đang thi công | Cách 15 đến 20 m, 2 đến 3 tầng cao nhất, có thể dùng tele 70 mm |

- GSD dưới 2 cm là đủ vì ngưỡng so sánh là 10 cm (ước tính ~0,9 cm ở 50 m, ~1,4 cm ở 80 m).
- Mặt bằng công trình không phải hình chữ nhật (nêm, nhiều cánh): vòng bay ở chuyến 2 phải bám theo đa giác chân công trình.
- **Camera:** JPEG 48 MP, tắt zoom số và HDR, cân bằng trắng cố định, lấy nét vô cực, màn trập từ 1/800, ISO tự động ≤ 400,
  tốc độ 3 đến 4 m/s, chụp theo khoảng cách (6 đến 7 m một ảnh).
- **Georeference:** 5 đến 8 GCP quanh công trình (đo RTK hoặc toàn đạc) cộng 2 đến 3 điểm kiểm tra; EXIF lưu trạng thái RTK;
  D-RTK 3 đặt cố định cùng một vị trí ở mọi đợt.
- **Thời điểm:** sáng 7:30 đến 11:00 (tháng 10 ở TP.HCM hay giông chiều), trời mây nhẹ, gió dưới 8 m/s; các đợt sau cùng khung giờ.
- **Tần suất:** hàng tuần, và thêm một đợt sau mỗi lần đổ xong một sàn; với đồ án xin ít nhất 2 đợt cách nhau 2 đến 3 tuần.
- **Cần cẩu:** hỏi chiều cao và vị trí; drone khó thấy dây cáp và cần cẩu lọt vào ảnh thành vật thể thừa.
- **Giàn giáo:** không cố xóa hoàn toàn; dùng mask ảnh, lọc point cloud, và quan trọng nhất là chỉ giữ điểm trong vỏ ±10 cm quanh bề mặt BIM.
- **Giao nộp mỗi đợt:** ảnh JPEG gốc (không nén lại, giữ EXIF/XMP gồm GPS và cờ RTK), file nhiệm vụ và log bay, tọa độ trạm
  D-RTK 3 và hệ tọa độ (WGS84 hay VN-2000), tọa độ GCP, ngày giờ, thời tiết, công việc thi công hôm đó; mỗi đợt một thư mục riêng.

---

## 9. Kết quả mô phỏng và giới hạn

### 9.1 Thí nghiệm một lần quét (`run_demo.py`, số ghi từ lần chạy trước)

Giả lập "xây đến tầng 8" (nhiễu 3 cm, bỏ mặt dưới, rơi 30% điểm, outlier, làm lệch tọa độ).

| Thí nghiệm | Kết quả |
|---|---|
| Lệch 4,6 m và quay 4° (kiểu sai số GPS) | ICP kéo về sai khoảng 0,3 cm |
| Sai cao độ ban đầu ≤ 1,0 m | Căn đúng |
| Sai cao độ ban đầu ≥ 1,65 m | **Căn nhầm sang tầng khác** (sai 3,07 đến 3,30 m) |
| Bỏ qua bước căn chỉnh | Chỉ đúng khoảng 51% |

### 9.2 Thí nghiệm nhiều lần quét (`run_fusion_demo.py`, chạy 22/10/2026 trên `PLM.ifc` thật + `lich.csv` thật)

3 lần quét giả lập (tầng đang đổ 3, 5, 7), cloud khó (lệch thi công 2 cm, lưới che, ván khuôn, che khuất HPR), sai số đăng ký
0,4 đến 1,5 cm (ICP numpy). So với đáp án của lần quét cuối:

| Cách | Precision | Recall |
|---|---|---|
| (1) Coverage của lần cuối (cách cũ) | 0,86 | 0,51 |
| (2) Có tính độ nhìn thấy, chỉ lần cuối | 0,90 | 0,31 |
| (3) Hợp nhất 3 lần | 0,94 | 0,49 |
| Coverage của mô hình hợp nhất (so với lần cuối: 0,51) | | 0,56 |

Số liệu dao động nhẹ giữa các lần chạy (nhiễu ngẫu nhiên), nên chỉ đọc theo xu hướng. Hợp nhất giúp biết thêm 203 cấu kiện
"đã xây" mà lần quét cuối bị che; 81% cấu kiện được lần quét đầu tiên thấy trùng với lần quét xây thật.

**So với lịch tại ngày quét cuối (6/2/2027):** kế hoạch đã xong 1.138 cấu kiện; xác nhận đã xây 595; "trễ" (nhìn rõ mà không
thấy) 331; chưa kiểm chứng (bị che) 251; vượt kế hoạch 39. Mặt nạ kế hoạch khớp đáp án hình học 100% (kiểm tra quy ước gán tầng).

**Phải đọc kỹ:** trong mô phỏng, công trình xây *đúng* lịch, vậy mà vẫn có 331 cấu kiện bị báo "trễ". Đó là lỗi của phương pháp
(recall thấp, độ nhìn thấy mô phỏng khác độ nhìn thấy khi đánh giá), không phải trễ thật. **Không dùng số "trễ" theo từng cấu
kiện làm kết luận;** báo cáo theo tầng, kèm số "chưa kiểm chứng", và hiệu chỉnh ngưỡng trên ảnh thật.

### 9.3 Giới hạn cần ghi vào báo cáo

- Cloud giả và phần đánh giá dùng cùng một BIM; số liệu thật sẽ xấu hơn. Sai số đăng ký 8 đến 10 cm của bản ICP dự phòng
  trong một số kịch bản; không hứa dưới 10 cm khi chưa đo trên dữ liệu thật.
- **Cao độ ban đầu sai từ ~1,65 m trở lên làm ICP khớp nhầm tầng** (các tầng lặp lại ~3,3 m): phải khóa cao độ bằng RTK hoặc GCP.
- **Ván khuôn dầm/sàn nằm đúng chỗ cấu kiện sẽ đổ**, nên hình học không phân biệt "đã đổ bê tông" với "mới dựng ván khuôn".
  Muốn phân biệt phải dùng thêm IFC ván khuôn (6.089 phần tử `TS_FormWork` đang bị bỏ qua) hoặc phân loại ảnh.
- Drone chỉ thấy bên ngoài và mặt trên; cấu kiện bên trong ở trạng thái "chưa rõ". Báo cáo ba loại (đã xây, chưa xây, không
  kiểm chứng được) thay vì một con số phần trăm duy nhất.
- Giàn giáo vừa che cấu kiện đã xây (bỏ sót) vừa đứng sát cấu kiện chưa xây ở tầng đang làm (báo nhầm).
- Giàn giáo, cần cẩu, công trình bên cạnh chưa được đưa vào vật che của `visibility.py`, nên độ nhìn thấy là cận trên.
- Bê tông trắng ít texture nên SfM dễ thiếu điểm; cần chồng lấp dày và ảnh nghiêng.
- `visibility.py` bản Open3D và `registration.py` bản Open3D chưa được chạy thử (mới thử numpy).
- Pipeline chưa được thử trên ảnh thật.

---

## 10. Việc còn lại

1. **Dữ liệu ảnh thật** (đang chờ công ty bay hoặc GVHD chốt công trình). Có ảnh thì chạy ODM rồi mới hiệu chỉnh được ngưỡng.
2. **Đọc point cloud ODM (`.laz`) và căn thô bằng GCP** (`registration.umeyama` rồi ICP): point cloud thật nằm ở tọa độ trắc địa
   (hàng trăm nghìn mét) còn BIM ở tọa độ cục bộ (0 đến 80 m), ICP không bắc cầu được; cần phép biến đổi ban đầu từ ≥ 3 điểm
   tương ứng và trừ offset để không mất độ chính xác số. **Chưa viết** vì cần mẫu đầu ra ODM thật để khớp hệ tọa độ và độ dịch
   gốc: `odm_georeferencing/odm_georeferenced_model.laz`, `coords.txt`, `shots.geojson`, `gcp_list.txt`. Mẫu có thể từ bất kỳ
   lần chạy ODM nào có geotag (bộ banana không có GPS nên chưa đủ); ảnh công trình thật mới dùng để kiểm chứng.
3. **Vị trí máy bay thật** cho `visibility.py` (hiện dùng vị trí giả): lấy từ EXIF/log RTK/`shots.geojson`, đưa vào hệ tọa độ BIM.
4. Kiểm chứng `visibility.py` và `registration.py` bằng Open3D.
5. Hiệu chỉnh ngưỡng (`tol`, `t_built`, `t_not`, `r_present`, `r_absent`, `v_min`, `v_conflict`) trên ảnh thật.
6. Báo cáo theo tầng thay cho cờ "trễ" từng cấu kiện (mục 9.2); phân tích độ nhạy (tăng nhiễu, tỉ lệ mất điểm, sai số đăng ký).
7. Hỏi người lập lịch về `CV1F` trùng `CV2F` và các `Z*` (mục 11); nếu cần kiểm tra thêm thì so GlobalId giữa `PLM.nwc` và `PLM.ifc`.
8. Viết báo cáo.

---

## 11. Câu hỏi còn mở cho GVHD và công ty

**GVHD**

1. Đợt bay sẽ là công trình nào, đã có BIM chưa? (`PLM.ifc` là cao ốc 17 tầng; video demo là nhà phố thấp tầng.) Nếu không bay
   PLM thì phần so sánh với BIM kiểm chứng bằng cách nào?
2. Phạm vi so sánh: có tính ván khuôn (6.089 `TS_FormWork`) không? Mức đánh giá mong muốn: "tầng đã đổ chưa", từng cấu kiện, hay
   từng giai đoạn (ván khuôn, cốt thép, bê tông)?
3. Có xin được `PLM.nwc` (hầm, móng, tầng 1) dạng IFC để đủ phần dưới của công trình không?
4. Giàn giáo có bắt buộc lọc không, ở mức độ nào? Tiêu chí thành công (sai số bao nhiêu cm, lịch chi tiết đến ngày/tuần/tầng)?
5. Quyền sử dụng file BIM và ảnh dự án thật trong báo cáo; có cần báo người làm mô hình về 21 dầm gán nhãn sai tầng không?
6. Báo cáo giữa kỳ có chấp nhận kết quả trên dữ liệu giả lập không, yêu cầu nội dung và mốc thời gian là gì?
7. Dữ liệu cuối cùng dùng ảnh drone của công ty hay drone nhóm tự làm?

**Công ty bay**

1. Công trình bay là công trình nào, độ cao điểm cao nhất kể cả cần cẩu, ai xin phép bay, có giới hạn độ cao không?
2. Có bật D-RTK 3 không? Đo được 4 đến 6 GCP bằng GNSS RTK hoặc máy toàn đạc không? Tọa độ trạm D-RTK 3 và hệ tọa độ?
   (Lý do: sai cao độ ban đầu trên ~1,0 đến 1,65 m làm bước căn chỉnh khớp nhầm tầng.)
3. Dữ liệu giao là ảnh tĩnh JPEG 48 MP gốc, giữ nguyên EXIF/XMP, kèm file nhiệm vụ và log bay của từng đợt.
4. FlightHub 2 trên Dock 3 có chạy được lưới nadir, chụp nghiêng 5 hướng, Smart 3D Capture không? Có lưu và bay lại đúng
   đường bay giữa các đợt không? Xác nhận đúng máy là Matrice 4TD.
5. Thông số đề xuất: chồng lấp 80% dọc, 70% ngang (chụp nghiêng 80% cả hai chiều), GSD ≤ 2 cm, tốc độ ≤ 5 m/s, chụp theo khoảng cách.
6. Đợt thử: lưới nadir và chụp nghiêng, thêm quỹ đạo 3 độ cao nếu còn pin, bay lặp hai lần trong cùng ngày.
7. Tần suất, chi phí mỗi đợt, hạn giao dữ liệu đợt đầu; kèm ngày giờ, thời tiết, công việc thi công hôm đó.
8. Dữ liệu có được dùng trong đồ án và báo cáo không?

**Người lập lịch (nếu liên hệ được):** `CV1F` và `CV2F` cùng ngày, không có `DS1F`: có chủ ý không? Các task `Z*` do ai quản lý?

---

## 12. Hướng mở rộng

### 12.1 Nhiều nhà giống hệt nhau trong một khu

Hình học không phân biệt được hai nhà giống nhau, nên xác định nhà bằng vị trí tuyệt đối (RTK/GCP, hệ UTM 48N), không bằng
hình dạng. Cắt point cloud theo đa giác chân móng từng nhà trước khi đăng ký; chặn ICP bằng ngưỡng lệch so với ước lượng ban
đầu; đặt mốc có mã (ArUco/AprilTag) mỗi dãy. Trong code: khóa trạng thái theo cặp (instance, GlobalId), tách "kiểu BIM" khỏi
"phép biến đổi đặt nhà", mỗi nhà một lịch riêng.

### 12.2 Kết hợp với nhóm dựng 3D bên trong

Drone thấy bên ngoài và mặt trên, nhóm kia thấy bên trong, nên phần "chưa rõ (bị che)" có thể được lấp bằng dữ liệu của nhóm
kia. Hai nhóm nên thống nhất sớm: cùng IFC (`PLM.ifc`) và cùng khóa **GlobalId**; cùng hệ tọa độ BIM (mét) và vài điểm khống
chế chung (giao điểm lưới trục cột) nhìn được từ cả trong lẫn ngoài; cùng định dạng trao đổi (point cloud đã đăng ký `.ply`/`.laz`
kèm vị trí camera N×3, và bảng trạng thái theo GlobalId: đã xây, chưa xây, chưa rõ, độ tin cậy, thời điểm). Mỗi nguồn là một
"lần quan sát" đưa vào `fusion.FusionState.update(...)` (vị trí camera trong nhà đưa vào `visibility.evidence` thành thêm
`cams`); hai nguồn mâu thuẫn thì gắn "cần kiểm tra thủ công".

---

## 13. Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| `ModuleNotFoundError: ifcopenshell` hoặc `open3d` | Chưa bật đúng môi trường `bim` hoặc chưa cài (mục 4) |
| `FileNotFoundError: data\plm_elements.json` | Chưa chạy `bim_loader.py`, hoặc `ROOT` trong `config.py` chưa đúng (mục 3) |
| `schedule_loader.py` báo không tìm thấy cột | Tên cột trong CSV khác; sửa `COLUMN_ALIASES` |
| Ngày tháng bị đảo | Xem dòng "kiểu ngày" in ra, đối chiếu một ngày cụ thể với TimeLiner |
| `Bỏ qua tầng ... không có trong lịch` khi chạy `run_fusion_demo.py` | Giá trị trong `--epochs` không có trong bảng lịch; chọn tầng có trong bảng (2 đến 14) |
| Mặt nạ kế hoạch khớp đáp án thấp | Quy ước gán tầng sai: kiểm tra `--floor-mode` và `--ds-shift` (mục 6) |
| `run_demo.py` hết RAM hoặc chạy rất lâu | Giảm `density`, hoặc thêm `--skip-realistic`; `--hpr-voxel` lớn hơn cho `run_fusion_demo.py` |
| ICP khớp nhầm tầng | Sai số cao độ ban đầu quá lớn; khóa cao độ bằng RTK/GCP |
| `./webodm.sh : The term is not recognized` | Dùng Git Bash, không dùng PowerShell |
| `./webodm.sh start` lỗi, thông báo khác nhau mỗi lần | Thường thiếu RAM cấp cho Docker (mục 7.2) |
| Task WebODM báo `out of memory`/`killed` | Tăng RAM Docker, giảm kích thước ảnh, hoặc giảm `pc-quality` |
| Không mở được `localhost:8000` | Docker Desktop chưa Running, hoặc `start` chưa chạy xong |
| WebODM hết dung lượng ổ C | Dời dữ liệu bằng `--media-dir`/`--db-dir` (mục 7.2) |

---

## 14. Phụ lục: số liệu `PLM.ifc` và cấu trúc file `.nwd`

| Mục | Giá trị |
|---|---|
| Định dạng | IFC2X3, xuất từ Revit 2025, ~306.000 dòng, 21,5 MB |
| Dầm / cột / sàn | 1.413 / 995 / 297 (tổng 2.705, đều có hình học sau khi sửa) |
| Phần tử ván khuôn `TS_FormWork` | 6.089 (đang bị loại khỏi so sánh) |
| Lỗ mở | 479 |
| Mức sàn (cao độ, tách theo hình học) | 17 mức, tầng điển hình cách nhau ~3,3 m |
| Kích thước tòa nhà | ~57 × 79 m mặt bằng, cao ~55 m |
| Thể tích bê tông kết cấu (từ mesh) | 7.852 m³ (dầm 733, cột 1.356, sàn 5.763) |
| Mesh gộp | 53.339 đỉnh, 91.494 tam giác |
| `Pset_QuantityTakeOff` | chỉ chứa tên tiết diện (ví dụ 300x600), không có khối lượng |
| Nhãn tầng IFC | TẦNG 1 đến 14, TUM, MÁI, VỈA HÈ (cote 0.0); không có TẦNG HẦM |
| Lỗi gán tầng | 21 dầm gán "TẦNG 1" nhưng nằm ở cao độ 13,8 đến 47,6 m (nhiều cặp dầm 200x300 lặp ở mọi tầng) |

**Cấu trúc file `Mô_hình_tiến_độ_Kết_cấu_PALC_Q9.nwd`** (từ Selection Tree):

- `PLM-TH.nwc`: VỈA HÈ, TẦNG 1 đến 14, TUM, MÁI. Khớp với `PLM.ifc`.
- `PLM.nwc`: `<No level>`, TẦNG HẦM, VỈA HÈ, ĐỈNH BỒN HOA, TẦNG 1 (Floor, dầm, Basic Wall). Gồm móng, hầm và phần tầng 1 mà
  các task `Z*` gắn vào; chưa có trong `PLM.ifc`.

Navisworks Freedom chỉ phát lại mô phỏng TimeLiner khi file đã có dữ liệu, không tạo hay xuất được; bản có TimeLiner đầy đủ
(panel **Tools → TimeLiner**) mới xuất được CSV.