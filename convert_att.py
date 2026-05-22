"""
convert_att.py
─────────────────────────────────────────────────────────────
Convert AT&T Face Database → cấu trúc dataset/ cho ai_subscriber.py

Cách dùng:
    1. Tải AT&T dataset từ Kaggle:
       https://www.kaggle.com/datasets/kasikrit/att-database-of-faces
    2. Giải nén → có thư mục "att_faces/" hoặc "orl_faces/"
    3. Đặt script này cùng cấp với thư mục đó
    4. Chạy: python convert_att.py
    5. Kết quả: thư mục dataset/ sẵn sàng dùng với ai_subscriber.py

Cấu trúc AT&T gốc:         Cấu trúc sau convert:
  att_faces/                  dataset/
    s1/                         Nguoi_01/
      1.pgm                       1.jpg
      2.pgm                       2.jpg
      ...                         ...
    s2/                         Nguoi_02/
      1.pgm                       1.jpg
      ...                         ...
"""

import os
import shutil
import cv2
import numpy as np

# ══════════════════════════════════════════════════════════════
# CẤU HÌNH
# ══════════════════════════════════════════════════════════════

# Thư mục AT&T gốc — thử cả 2 tên phổ biến
ATT_DIRS = ["att_faces", "orl_faces", "ATT", "ORL"]

# Thư mục output
OUTPUT_DIR = "dataset"

# Tiền tố tên người — đổi thành tên thật nếu muốn
# VD: NAMES = ["Nguyen_Van_A", "Tran_Thi_B", ...] (đúng 40 phần tử)
# Để None → tự đặt tên Nguoi_01, Nguoi_02, ...
NAMES = None

# Số ảnh tối đa mỗi người (AT&T có 10 ảnh/người)
# Để None → lấy hết
MAX_IMAGES = 10

# ══════════════════════════════════════════════════════════════
# TÌM THƯ MỤC AT&T
# ══════════════════════════════════════════════════════════════
def find_att_dir():
    # Thử các tên thư mục phổ biến
    for name in ATT_DIRS:
        if os.path.isdir(name):
            return name

    # Tìm thư mục có chứa s1/, s2/, ...
    for entry in os.listdir("."):
        if os.path.isdir(entry):
            sub = os.listdir(entry)
            if any(s.startswith("s") and s[1:].isdigit() for s in sub):
                return entry

    return None


# ══════════════════════════════════════════════════════════════
# KIỂM TRA KHUÔN MẶT TRONG ẢNH
# ══════════════════════════════════════════════════════════════
def check_face(img_path):
    """Trả về True nếu ảnh có ít nhất 1 khuôn mặt."""
    try:
        import face_recognition
        img = face_recognition.load_image_file(img_path)
        locs = face_recognition.face_locations(img)
        return len(locs) > 0
    except Exception:
        # Nếu chưa cài face_recognition thì bỏ qua bước check
        return True


# ══════════════════════════════════════════════════════════════
# CONVERT CHÍNH
# ══════════════════════════════════════════════════════════════
def convert(att_dir):
    # Lấy danh sách thư mục s1, s2, ... theo thứ tự số
    subjects = sorted(
        [d for d in os.listdir(att_dir)
         if os.path.isdir(os.path.join(att_dir, d)) and d.startswith("s")],
        key=lambda x: int(x[1:])
    )

    if not subjects:
        print(f"[LỖI] Không tìm thấy thư mục s1, s2,... trong '{att_dir}'")
        return

    print(f"[INFO] Tìm thấy {len(subjects)} người trong '{att_dir}'")
    print(f"[INFO] Output → '{OUTPUT_DIR}/'")
    print("-" * 50)

    total_copied  = 0
    total_skipped = 0

    for i, subject in enumerate(subjects):
        # Tên người
        if NAMES and i < len(NAMES):
            person_name = NAMES[i]
        else:
            person_name = f"Nguoi_{str(i+1).zfill(2)}"

        src_dir = os.path.join(att_dir, subject)
        dst_dir = os.path.join(OUTPUT_DIR, person_name)
        os.makedirs(dst_dir, exist_ok=True)

        # Lấy tất cả file ảnh (.pgm hoặc .jpg)
        img_files = sorted([
            f for f in os.listdir(src_dir)
            if f.lower().endswith((".pgm", ".jpg", ".jpeg", ".png"))
        ])

        if MAX_IMAGES:
            img_files = img_files[:MAX_IMAGES]

        count = 0
        for img_file in img_files:
            src_path = os.path.join(src_dir, img_file)
            dst_path = os.path.join(dst_dir, f"{count+1}.jpg")

            # Đọc ảnh (cv2 đọc được .pgm)
            img = cv2.imread(src_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                print(f"  ✗ Không đọc được: {src_path}")
                total_skipped += 1
                continue

            # Resize nếu quá nhỏ (AT&T gốc 92x112 — đủ dùng)
            h, w = img.shape
            if w < 60 or h < 60:
                img = cv2.resize(img, (92, 112))

            # Chuyển grayscale → BGR để lưu .jpg
            img_bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            cv2.imwrite(dst_path, img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])

            count += 1
            total_copied += 1

        print(f"  ✓ {subject} → {person_name}/ ({count} ảnh)")

    print("-" * 50)
    print(f"[XONG] Đã convert {total_copied} ảnh, bỏ qua {total_skipped} ảnh lỗi")
    print(f"[XONG] Cấu trúc dataset/ đã sẵn sàng!")


# ══════════════════════════════════════════════════════════════
# VERIFY — kiểm tra dataset sau khi convert
# ══════════════════════════════════════════════════════════════
def verify():
    print("\n[VERIFY] Kiểm tra dataset...")
    if not os.path.isdir(OUTPUT_DIR):
        print("[LỖI] Thư mục dataset/ không tồn tại")
        return

    people = sorted(os.listdir(OUTPUT_DIR))
    ok_count   = 0
    warn_count = 0

    for person in people:
        person_dir = os.path.join(OUTPUT_DIR, person)
        if not os.path.isdir(person_dir):
            continue
        imgs = [f for f in os.listdir(person_dir) if f.lower().endswith((".pgm", ".jpg", ".jpeg", ".png", ".bmp"))]
        if len(imgs) >= 5:
            print(f"  ✓ {person}: {len(imgs)} ảnh")
            ok_count += 1
        else:
            print(f"  ⚠ {person}: chỉ có {len(imgs)} ảnh (nên có ≥5)")
            warn_count += 1

    print(f"\n[VERIFY] {ok_count} người đủ ảnh, {warn_count} người thiếu ảnh")
    print("[VERIFY] Chạy ai_subscriber.py để build encodings.json")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
def main():
    print("=" * 50)
    print("  CONVERT AT&T DATASET → dataset/")
    print("=" * 50)

    # Tìm thư mục AT&T
    att_dir = find_att_dir()
    if not att_dir:
        print("[LỖI] Không tìm thấy thư mục AT&T!")
        print("\nHướng dẫn:")
        print("  1. Tải từ: https://www.kaggle.com/datasets/kasikrit/att-database-of-faces")
        print("  2. Giải nén vào cùng thư mục với script này")
        print("  3. Chạy lại script")
        return

    print(f"[INFO] Tìm thấy AT&T dataset tại: '{att_dir}/'")

    # Xoá dataset cũ nếu có
    if os.path.isdir(OUTPUT_DIR):
        confirm = input(f"\nThư mục '{OUTPUT_DIR}/' đã tồn tại. Xoá và tạo lại? (y/n): ")
        if confirm.lower() == 'y':
            shutil.rmtree(OUTPUT_DIR)
            print(f"[INFO] Đã xoá '{OUTPUT_DIR}/'")
        else:
            print("[INFO] Giữ nguyên dataset cũ, thoát.")
            return

    # Convert
    convert(att_dir)

    # Verify
    verify()


if __name__ == "__main__":
    main()
