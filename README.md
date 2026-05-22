# 🎓 Hệ thống Điểm Danh AIoT

Hệ thống điểm danh khuôn mặt thời gian thực sử dụng **LBPH (Local Binary Pattern Histogram)**, giao tiếp **MQTT** với ESP32, và web dashboard **Flask**.

---

## 📁 Cấu trúc project

```
CE340/
├── ai_subscriber.py      # Subscriber chính: nhận diện khuôn mặt + MQTT
├── dashboard.py          # Web dashboard realtime (Flask + SocketIO)
├── test_lbph_accuracy.py # Script kiểm tra độ chính xác model
├── convert_att.py        # Convert AT&T dataset → cấu trúc dataset/
├── esp32.zip                   # Firmware ESP32
├── dataset/                    # Dataset khuôn mặt (40 người × 10 ảnh)
│   ├── Nguoi_01/
│   │   ├── 1.jpg
│   │   └── ...
│   └── ...
└── requirements.txt
```

---

## ⚙️ Cài đặt

### 1. Clone repo & cài thư viện

```bash
git clone <repo-url>
cd <tên-repo>
pip install -r requirements.txt
```

### 2. Cấu hình MQTT (HiveMQ Cloud)

Tạo tài khoản tại [HiveMQ Cloud](https://www.hivemq.com/mqtt-cloud-broker/) rồi đặt biến môi trường:

**Windows (PowerShell):**
```powershell
$env:MQTT_USER="your_hivemq_username"
$env:MQTT_PASS="your_hivemq_password"
$env:MQTT_BROKER="<your-broker>.s1.eu.hivemq.cloud"
$env:MQTT_PORT="8883"
```

**Linux / macOS:**
```bash
export MQTT_USER="your_hivemq_username"
export MQTT_PASS="your_hivemq_password"
export MQTT_BROKER="<your-broker>.s1.eu.hivemq.cloud"
export MQTT_PORT="8883"
```

---

## 🚀 Chạy hệ thống

### Chạy AI Subscriber (nhận diện + MQTT)

```bash
python ai_subscriber.py
```

Khi ESP32 gửi `PERSON_DETECTED` lên topic `diemdanh/camera/trigger`, hệ thống sẽ:
1. Lấy ngẫu nhiên 1 ảnh từ `dataset/` (mô phỏng chụp webcam)
2. Nhận diện bằng LBPH
3. Lưu kết quả vào `attendance.db`
4. Publish kết quả và điều khiển relay (`OPEN_DOOR` / `CLOSE_DOOR` / `DENY`)

### Chạy Web Dashboard

```bash
python dashboard.py
```

Mở trình duyệt: [http://localhost:5000](http://localhost:5000)

### Kiểm tra độ chính xác model

```bash
python test_lbph_accuracy.py
```

---

## 🔌 MQTT Topics

| Topic | Mô tả |
|---|---|
| `diemdanh/camera/trigger` | ESP32 gửi `PERSON_DETECTED` để kích hoạt nhận diện |
| `diemdanh/ketqua` | Kết quả: `PRESENT:<tên>` hoặc `UNKNOWN` |
| `diemdanh/relay/control` | Điều khiển relay: `OPEN_DOOR` / `CLOSE_DOOR` / `DENY` |

---

## 📊 Dataset

Sử dụng **AT&T Face Database** (ORL) — 40 người, mỗi người 10 ảnh (~5KB/ảnh).  
Để thêm người mới, tạo thư mục `dataset/Ten_Nguoi/` và đặt ảnh khuôn mặt vào.  
Xóa `lbph_model.yml` và `encodings.json` để model tự train lại.

---

## 📝 Lưu ý

- `lbph_model.yml` và `attendance.db` được sinh ra khi chạy, **không commit** vào Git.
- Credentials MQTT phải đặt qua biến môi trường, **không hardcode** vào code.
- Hàm `recognize_face()` hiện đang **mô phỏng** (lấy ảnh ngẫu nhiên từ dataset) thay vì dùng webcam thật — phù hợp để demo/test.
