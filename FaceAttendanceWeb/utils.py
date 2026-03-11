# utils.py - Xử lý nhận dạng khuôn mặt

import face_recognition
import cv2
import numpy as np
import os


def encode_image_file(image_path):
    """Encode một file ảnh thành bytes để lưu DB"""
    if not os.path.exists(image_path):
        return None
    try:
        image = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(image)
        if len(encodings) > 0:
            return encodings[0].tobytes()
        return None
    except Exception as e:
        print(f"Lỗi encode ảnh {image_path}: {e}")
        return None