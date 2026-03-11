import cv2
import numpy as np
import face_recognition
import os
from PIL import Image

print("=== BẮT ĐẦU KIỂM TRA CAMERA (INDEX 1, 2, 0, 3, 4) VỚI CAP_MSMF ===")

# Thứ tự ưu tiên giống app.py
camera_indices = [1, 2, 0, 3, 4]

for index in camera_indices:
    print(f"\n--- Đang thử webcam index = {index} (Backend: CAP_MSMF) ---")
    cap = cv2.VideoCapture(index, cv2.CAP_MSMF)

    if not cap.isOpened():
        print(f"→ Không mở được webcam tại index {index}")
        cap.release()
        continue

    print(f"→ Webcam mở thành công tại index {index}!")

    # Cấu hình giống app.py
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

    success, frame = cap.read()
    if success:
        print(f"Frame info: shape={frame.shape}, dtype={frame.dtype}")
        
        print(">> Test xử lý khuôn mặt (PIL Fix)...")

        # Phương pháp PIL (Cách Khuyên dùng cho App)
        try:
            # BGR -> RGB -> PIL -> Numpy (Quy trình làm sạch buffer chuẩn nhất)
            rgb_cv = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_cv)
            rgb_clean = np.array(pil_image)

            faces = face_recognition.face_locations(rgb_clean, model='hog')
            print(f"       ✓ PIL FIX: THÀNH CÔNG! Tìm thấy {len(faces)} mặt.")

            # Vẽ hình chữ nhật quanh mặt nếu tìm thấy
            for (top, right, bottom, left) in faces:
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)

        except Exception as e:
            print(f"       ✗ PIL FIX: THẤT BẠI ({e})")

        cv2.imshow(f'Test Webcam index {index}', frame)
        print("Đang hiển thị hình ảnh trong 3 giây...")
        cv2.waitKey(3000)
    else:
        print("Không đọc được frame đầu tiên")

    cap.release()
    try:
        cv2.destroyWindow(f'Test Webcam index {index}')
    except:
        pass

print("\nKết thúc test.")
cv2.destroyAllWindows()