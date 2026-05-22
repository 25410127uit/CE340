import os
import re
from pathlib import Path
import cv2
import numpy as np
from sklearn.metrics import confusion_matrix

# =========================
# CONFIG
# =========================
DATASET_DIR = os.getenv("DATASET_DIR", str(Path(__file__).resolve().parent / "dataset"))

THRESHOLD = 80
IMAGE_SIZE = (100, 100)

TRAIN_PER_PERSON = 7
TEST_PER_PERSON = 3

VALID_EXTENSIONS = (".pgm", ".jpg", ".jpeg", ".png", ".bmp")


def natural_key(value):
    """Sort đúng thứ tự 1,2,...,10 thay vì 1,10,2."""
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", value)]


# =========================
# CHECK DATASET
# =========================
print("Loading dataset...")
print("DATASET_DIR =", DATASET_DIR)

if not os.path.exists(DATASET_DIR):
    raise FileNotFoundError(f"Không tìm thấy thư mục dataset: {DATASET_DIR}")

person_folders = sorted([
    f for f in os.listdir(DATASET_DIR)
    if os.path.isdir(os.path.join(DATASET_DIR, f))
], key=natural_key)

print("Số thư mục người tìm thấy:", len(person_folders))
print("Ví dụ thư mục:", person_folders[:5])

if len(person_folders) == 0:
    raise RuntimeError("Không tìm thấy thư mục người nào trong dataset.")


# =========================
# LOAD TRAIN / TEST
# =========================
train_images = []
train_labels = []

test_images = []
test_labels = []

label_to_name = {}
label_id = 0

for person_name in person_folders:
    person_dir = os.path.join(DATASET_DIR, person_name)

    files = sorted([
        f for f in os.listdir(person_dir)
        if f.lower().endswith(VALID_EXTENSIONS)
    ], key=natural_key)

    if len(files) < TRAIN_PER_PERSON + TEST_PER_PERSON:
        print(f"Bỏ qua {person_name}: chỉ có {len(files)} ảnh")
        continue

    label_to_name[label_id] = person_name

    train_files = files[:TRAIN_PER_PERSON]
    test_files = files[TRAIN_PER_PERSON:TRAIN_PER_PERSON + TEST_PER_PERSON]

    for img_file in train_files:
        img_path = os.path.join(person_dir, img_file)
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)

        if img is None:
            print("Không đọc được ảnh:", img_path)
            continue

        img = cv2.resize(img, IMAGE_SIZE)

        train_images.append(img)
        train_labels.append(label_id)

    for img_file in test_files:
        img_path = os.path.join(person_dir, img_file)
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)

        if img is None:
            print("Không đọc được ảnh:", img_path)
            continue

        img = cv2.resize(img, IMAGE_SIZE)

        test_images.append(img)
        test_labels.append(label_id)

    label_id += 1


print("\nLoaded train images:", len(train_images))
print("Loaded test images :", len(test_images))
print("Số người hợp lệ    :", len(label_to_name))

if len(train_images) == 0:
    raise RuntimeError("Không có ảnh train. Kiểm tra lại DATASET_DIR hoặc đuôi file ảnh.")

if len(set(train_labels)) < 2:
    raise RuntimeError("Cần ít nhất 2 người để train LBPH.")


# =========================
# TRAIN LBPH
# =========================
print("\nTraining LBPH model...")

recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.train(train_images, np.array(train_labels))

print("Training complete.")


# =========================
# TEST PRESENT
# =========================
print("\nTesting PRESENT faces...")

y_true = []
y_pred = []

correct_person = 0
wrong_person = 0
unknown_count = 0

for img, true_label in zip(test_images, test_labels):
    pred_label, confidence = recognizer.predict(img)

    true_name = label_to_name[true_label]

    if confidence < THRESHOLD:
        pred_name = label_to_name.get(pred_label, "UNKNOWN")

        if pred_label == true_label:
            result = "CORRECT"
            correct_person += 1
            y_pred.append("PRESENT")
        else:
            result = "WRONG_PERSON"
            wrong_person += 1
            y_pred.append("PRESENT")
    else:
        pred_name = "UNKNOWN"
        result = "UNKNOWN"
        unknown_count += 1
        y_pred.append("UNKNOWN")

    y_true.append("PRESENT")

    print(
        f"REAL={true_name:<10} | "
        f"PRED={pred_name:<10} | "
        f"CONF={confidence:>6.2f} | "
        f"{result}"
    )


# =========================
# TEST UNKNOWN GIẢ LẬP
# =========================
# Tạo ảnh noise ngẫu nhiên để mô phỏng người lạ.
# Nếu bạn có folder unknown thật, nên thay phần này bằng ảnh unknown thật.

print("\nTesting UNKNOWN samples...")

UNKNOWN_TESTS = 40

unknown_correct = 0
unknown_false_present = 0

for i in range(UNKNOWN_TESTS):
    noise_img = np.random.randint(0, 255, IMAGE_SIZE, dtype=np.uint8)

    pred_label, confidence = recognizer.predict(noise_img)

    y_true.append("UNKNOWN")

    if confidence < THRESHOLD:
        y_pred.append("PRESENT")
        unknown_false_present += 1
        result = "FALSE_PRESENT"
    else:
        y_pred.append("UNKNOWN")
        unknown_correct += 1
        result = "CORRECT_UNKNOWN"

    print(
        f"UNKNOWN_{i+1:02d} | "
        f"CONF={confidence:>6.2f} | "
        f"{result}"
    )


# =========================
# CONFUSION MATRIX
# =========================
labels = ["PRESENT", "UNKNOWN"]
cm = confusion_matrix(y_true, y_pred, labels=labels)

TP = cm[0][0]
FN = cm[0][1]
FP = cm[1][0]
TN = cm[1][1]

precision = TP / (TP + FP) if (TP + FP) > 0 else 0
recall = TP / (TP + FN) if (TP + FN) > 0 else 0
accuracy = (TP + TN) / np.sum(cm) if np.sum(cm) > 0 else 0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0


print("\n==============================")
print("CONFUSION MATRIX")
print("==============================")
print("Labels:", labels)
print(cm)

print("\nÝ nghĩa:")
print(f"TP - PRESENT nhận đúng        : {TP}")
print(f"FN - PRESENT bị báo UNKNOWN   : {FN}")
print(f"FP - UNKNOWN bị nhận nhầm     : {FP}")
print(f"TN - UNKNOWN bị từ chối đúng  : {TN}")

print("\n==============================")
print("METRICS")
print("==============================")
print(f"Precision : {precision * 100:.2f}%")
print(f"Recall    : {recall * 100:.2f}%")
print(f"Accuracy  : {accuracy * 100:.2f}%")
print(f"F1-score  : {f1 * 100:.2f}%")

print("\n==============================")
print("DETAIL")
print("==============================")
print(f"Nhận đúng người quen          : {correct_person}")
print(f"Nhận sai sang người khác      : {wrong_person}")
print(f"Người quen bị báo UNKNOWN     : {unknown_count}")
print(f"UNKNOWN bị từ chối đúng       : {unknown_correct}")
print(f"UNKNOWN bị nhận nhầm PRESENT  : {unknown_false_present}")


# =========================
# SAVE MODEL
# =========================
recognizer.save("lbph_model.yml")

print("\nĐã lưu model: lbph_model.yml")