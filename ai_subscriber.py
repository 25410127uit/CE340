"""
ai_subscriber.py 
─────────────────────────────────────────────────────────────
Cài đặt:
    pip install opencv-contrib-python paho-mqtt numpy

Chạy:
    python ai_subscriber.py
"""

import paho.mqtt.client as mqtt
import cv2
import numpy as np
import sqlite3
import threading
import time
import os
import json
import random
import ssl
from datetime import datetime

# ══════════════════════════════════════════════════════════════
# CẤU HÌNH
# ══════════════════════════════════════════════════════════════
MQTT_BROKER   = os.getenv("MQTT_BROKER", "44664d8119b54fadaf9870a37274af6b.s1.eu.hivemq.cloud")
MQTT_PORT     = int(os.getenv("MQTT_PORT", "8883"))
MQTT_USER     = os.getenv("MQTT_USER", "").strip()     # đặt bằng biến môi trường
MQTT_PASS     = os.getenv("MQTT_PASS", "").strip()     # đặt bằng biến môi trường

TOPIC_TRIGGER = "diemdanh/camera/trigger"
TOPIC_RESULT  = "diemdanh/ketqua"
TOPIC_RELAY   = "diemdanh/relay/control"

DATASET_DIR    = "dataset"
ENCODINGS_FILE = "encodings.json"
DB_FILE        = "attendance.db"
COOLDOWN_SEC   = 5

# ══════════════════════════════════════════════════════════════
# BƯỚC 1 — Database
# ══════════════════════════════════════════════════════════════
def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT    NOT NULL,
            timestamp TEXT    NOT NULL,
            confident REAL
        )
    """)
    conn.commit()
    conn.close()
    print("[DB] Database sẵn sàng:", DB_FILE)


def save_attendance(name, confidence):
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "INSERT INTO records (name, timestamp, confident) VALUES (?, ?, ?)",
        (name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), round(confidence, 4))
    )
    conn.commit()
    conn.close()
    print(f"[DB] Đã lưu: {name} lúc {datetime.now().strftime('%H:%M:%S')}")


# ══════════════════════════════════════════════════════════════
# BƯỚC 2 — Build / Load model LBPH
# ══════════════════════════════════════════════════════════════
def build_encodings():
    print("[AI] Đang build model từ dataset/ ...")

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    images    = []
    labels    = []
    label_map = {}
    label_idx = 0

    if not os.path.isdir(DATASET_DIR):
        print(f"[LỖI] Không tìm thấy thư mục {DATASET_DIR}/")
        return None, {}

    for person_name in sorted(os.listdir(DATASET_DIR)):
        person_dir = os.path.join(DATASET_DIR, person_name)
        if not os.path.isdir(person_dir):
            continue

        label_map[label_idx] = person_name
        count = 0

        for img_file in os.listdir(person_dir):
            if not img_file.lower().endswith((".jpg", ".jpeg", ".png", ".pgm")):
                continue

            img_path = os.path.join(person_dir, img_file)
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue

            faces = face_cascade.detectMultiScale(img, 1.1, 5, minSize=(30, 30))
            if len(faces) == 0:
                img_resized = cv2.resize(img, (100, 100))
                images.append(img_resized)
            else:
                x, y, w, h = faces[0]
                face_img = cv2.resize(img[y:y+h, x:x+w], (100, 100))
                images.append(face_img)

            labels.append(label_idx)
            count += 1

        print(f"  ✓ {person_name}: {count} ảnh (label={label_idx})")
        label_idx += 1

    if not images:
        print("[LỖI] Không có ảnh nào trong dataset/")
        return None, {}

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(images, np.array(labels))
    recognizer.save("lbph_model.yml")

    with open(ENCODINGS_FILE, "w") as f:
        json.dump({str(k): v for k, v in label_map.items()}, f, ensure_ascii=False)

    print(f"[AI] Đã train {len(label_map)} người → lbph_model.yml")
    return recognizer, label_map


def load_encodings():
    if os.path.exists("lbph_model.yml") and os.path.exists(ENCODINGS_FILE):
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read("lbph_model.yml")
        with open(ENCODINGS_FILE) as f:
            raw = json.load(f)
        label_map = {int(k): v for k, v in raw.items()}
        print(f"[AI] Đã load model: {len(label_map)} người")
        return recognizer, label_map
    else:
        return build_encodings()


# ══════════════════════════════════════════════════════════════
# BƯỚC 3 — Nhận diện từ dataset 
# ══════════════════════════════════════════════════════════════
def recognize_face(recognizer, label_map):
    """
    Mô phỏng hoàn toàn:
    Thay vì chụp webcam → lấy ngẫu nhiên 1 ảnh từ dataset để nhận diện.
    Giả lập đúng luồng thực tế: trigger → chụp ảnh → nhận diện → kết quả.
    """
    if recognizer is None:
        return "NO_MODEL"

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    # Lấy ngẫu nhiên 1 người từ dataset
    if not os.path.isdir(DATASET_DIR):
        return "NO_FACE"

    people = [p for p in os.listdir(DATASET_DIR)
              if os.path.isdir(os.path.join(DATASET_DIR, p))]
    if not people:
        return "NO_FACE"

    person = random.choice(people)
    person_dir = os.path.join(DATASET_DIR, person)
    imgs = [f for f in os.listdir(person_dir)
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".pgm"))]
    if not imgs:
        return "NO_FACE"

    # Lấy ngẫu nhiên 1 ảnh
    img_path = os.path.join(person_dir, random.choice(imgs))
    print(f"[AI] Đang nhận diện ảnh: {person}/{os.path.basename(img_path)}")

    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return "NO_FACE"

    # Detect khuôn mặt
    faces = face_cascade.detectMultiScale(img, 1.1, 5, minSize=(30, 30))
    if len(faces) == 0:
        test_img = cv2.resize(img, (100, 100))
    else:
        x, y, w, h = faces[0]
        test_img = cv2.resize(img[y:y+h, x:x+w], (100, 100))

    # Nhận diện
    label, confidence = recognizer.predict(test_img)
    name = label_map.get(label, "UNKNOWN")
    print(f"[AI] Kết quả: label={label} ({name}), confidence={confidence:.1f}")

    # confidence < 80 = nhận ra (LBPH: thấp = giống nhau)
    if confidence < 80:
        real_conf = round(1 - confidence / 100, 4)
        save_attendance(name, real_conf)
        return f"PRESENT:{name}"
    else:
        return "UNKNOWN"


# ══════════════════════════════════════════════════════════════
# BƯỚC 4 — MQTT callbacks
# ══════════════════════════════════════════════════════════════
last_trigger_time = 0

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[MQTT] Kết nối thành công!")
        client.subscribe(TOPIC_TRIGGER)
        print(f"[MQTT] Đang lắng nghe: {TOPIC_TRIGGER}")
    else:
        print(f"[MQTT] Kết nối thất bại rc={rc}")


def on_message(client, userdata, msg):
    global last_trigger_time
    payload = msg.payload.decode("utf-8").strip()
    print(f"\n[MQTT] Nhận: '{payload}' từ '{msg.topic}'")

    if payload != "PERSON_DETECTED":
        return

    # Cooldown
    now = time.time()
    if now - last_trigger_time < COOLDOWN_SEC:
        remaining = COOLDOWN_SEC - (now - last_trigger_time)
        print(f"[AI] Cooldown ({remaining:.1f}s còn lại), bỏ qua")
        return
    last_trigger_time = now

    recognizer, label_map = userdata
    thread = threading.Thread(
        target=run_recognition,
        args=(client, recognizer, label_map),
        daemon=True
    )
    thread.start()


def run_recognition(client, recognizer, label_map):
    print("[AI] Đang xử lý nhận diện...")
    ts     = time.time()
    result = recognize_face(recognizer, label_map)
    latency = round((time.time() - ts) * 1000)

    print(f"[AI] Kết quả: {result}  (latency: {latency}ms)")
    client.publish(TOPIC_RESULT, result)

    if result.startswith("PRESENT:"):
        name = result.split(":", 1)[1]
        print(f"[AI] ✓ {name} → publish OPEN_DOOR")
        client.publish(TOPIC_RELAY, "OPEN_DOOR")
        time.sleep(5)
        client.publish(TOPIC_RELAY, "CLOSE_DOOR")
        print(f"[AI] Relay đóng lại")
    elif result == "UNKNOWN":
        print("[AI] ✗ Khuôn mặt lạ → DENY")
        client.publish(TOPIC_RELAY, "DENY")
    else:
        print(f"[AI] ✗ {result}")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
def main():
    print("=" * 55)
    print("  HỆ THỐNG ĐIỂM DANH AIoT")
    print("   Dùng dataset có sẵn")
    print("=" * 55)

    # Kiểm tra opencv-contrib
    try:
        _ = cv2.face.LBPHFaceRecognizer_create()
    except AttributeError:
        print("[LỖI] Cần cài opencv-contrib:")
        print("      pip install opencv-contrib-python")
        return

    init_db()
    recognizer, label_map = load_encodings()

    if not label_map:
        print("[LỖI] Không có dữ liệu. Kiểm tra thư mục dataset/")
        return

    print(f"\n[SYS] Đã load {len(label_map)} người từ dataset")
    print(f"[SYS] Mỗi khi ESP32 gửi PERSON_DETECTED →")
    print(f"      lấy ngẫu nhiên 1 ảnh từ dataset → nhận diện\n")

    # Kiểm tra MQTT credentials từ biến môi trường
    if not MQTT_USER or not MQTT_PASS:
        print("[LỖI] Chưa cấu hình MQTT_USER/MQTT_PASS.")
        print("      PowerShell ví dụ:")
        print("      $env:MQTT_USER='your_user'")
        print("      $env:MQTT_PASS='your_password'")
        return

    # Kết nối MQTT
    client = mqtt.Client(userdata=(recognizer, label_map))
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"[MQTT] Đang kết nối {MQTT_BROKER}:{MQTT_PORT} ...")
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

    print("[SYS] Sẵn sàng. Nhấn Ctrl+C để thoát.\n")
    client.loop_forever()


if __name__ == "__main__":
    main()
