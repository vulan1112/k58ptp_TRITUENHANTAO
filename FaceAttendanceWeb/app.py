from flask import Flask, render_template, request, redirect, url_for, Response, session, flash, make_response, jsonify
from functools import wraps
import cv2
import time
import face_recognition
import numpy as np
import os
import csv
from io import StringIO, BytesIO
import base64
from PIL import Image
from db import get_connection, load_all_encodings, log_attendance, save_user, get_today_attendance
from utils import encode_image_file

app = Flask(__name__)
app.secret_key = 'super_secret_key_change_me_2026'

# Load encodings
known_encodings, known_names, known_ids = load_all_encodings()

last_attendance_time = {}   # {user_id: thời gian lần cuối điểm danh}

# ==================== ƯU TIÊN WEBCAM NGOÀI (INDEX 1) ====================
video_capture = None

def open_camera():
    global video_capture
    if video_capture is not None and video_capture.isOpened():
        return True

    print("=== Mở webcam - ƯU TIÊN EXTERNAL (index 1) ===")
    
    # Thứ tự ưu tiên: 1 (external) → 0 (laptop) → các index khác
    for idx in [1, 0, 2, 3, 4]:
        print(f"Thử mở camera index = {idx} với CAP_MSMF...")
        cap = cv2.VideoCapture(idx, cv2.CAP_MSMF)
        
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            
            video_capture = cap
            print(f"→ THÀNH CÔNG! Sử dụng camera index {idx} (External nếu là 1)")
            return True
        else:
            cap.release()

    print("Không mở được camera nào!")
    return False

def close_camera():
    global video_capture
    if video_capture is not None and video_capture.isOpened():
        video_capture.release()
        video_capture = None
        print("[INFO] Camera đã release thành công")


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Bạn cần đăng nhập với quyền admin để truy cập trang này', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def generate_video_frames():
    if not open_camera():
        # Trả frame đen nếu lỗi
        black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        _, buffer = cv2.imencode('.jpg', black_frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' +
               buffer.tobytes() + b'\r\n')
        return

    try:
        while True:
            success, frame = video_capture.read()
            if not success or frame is None:
                print("[WARN] Không đọc được frame từ camera")
                break

            # Kiểm tra frame hợp lệ: phải là numpy uint8, shape (H,W,3)
            if (not isinstance(frame, np.ndarray) or
                frame.dtype != np.uint8 or
                len(frame.shape) != 3 or
                frame.shape[2] != 3):
                print(f"[STREAM] Frame không hợp lệ (shape={frame.shape if frame is not None else None}, dtype={frame.dtype if frame is not None else None}) → bỏ qua xử lý")
                _, buf = cv2.imencode('.jpg', frame)
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')
                # time.sleep(0.01) # Optional if you want to delay on bad frames too
                continue

            # Copy frame để vẽ lên (tránh thay đổi frame gốc)
            display_frame = frame.copy()

            # --- FIX TRIỆT ĐỂ LỖI UNSUPPORTED IMAGE TYPE BẰNG PIL ---
            face_locations = []
            face_encodings = []
            
            try:
                # 1. Chuyển BGR sang RGB
                rgb_cv = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # 2. CHÌA KHÓA: Chuyển qua PIL Image rồi convert ngược lại numpy.
                # Hành động này ép buộc Python tạo ra một bản copy bộ nhớ clean hoàn toàn mới,
                # loại bỏ mọi flag lạ từ OpenCV/Camera Driver gây lỗi cho dlib.
                pil_image = Image.fromarray(rgb_cv)
                rgb_frame = np.array(pil_image)

                # 3. Nhận diện trên frame sạch
                face_locations = face_recognition.face_locations(rgb_frame, model='hog')
                
                if len(face_locations) > 0:
                     face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            except Exception as e:
                # print(f"[STREAM] Lỗi xử lý khuôn mặt: {e}")
                pass

            # Vẽ kết quả lên display_frame
            try:
                for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                    if len(known_encodings) == 0:
                        continue

                    distances = face_recognition.face_distance(known_encodings, face_encoding)
                    best_match_index = np.argmin(distances)

                    name = "Unknown"
                    if distances[best_match_index] < 0.50:
                        user_id = known_ids[best_match_index]
                        name = known_names[best_match_index]

                        # === THROTTLE: chỉ ghi điểm danh mỗi 30 giây/lần ===
                        now = time.time()
                        if user_id not in last_attendance_time or (now - last_attendance_time[user_id]) > 30:
                            log_attendance(user_id)
                            last_attendance_time[user_id] = now
                            print(f"[ATTENDANCE] {name} (ID: {user_id}) đã được điểm danh lúc {time.strftime('%H:%M:%S')}")

                    cv2.rectangle(display_frame, (left, top), (right, bottom), (0, 255, 0), 2)
                    cv2.putText(display_frame, name, (left, top - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

            except Exception as e:
                print(f"[STREAM] Lỗi vẽ/xử lý khuôn mặt: {e}")

            # Encode frame để gửi
            ret, buffer = cv2.imencode('.jpg', display_frame)
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            else:
                print("[STREAM] Lỗi encode frame → trả frame đen")
                black = np.zeros((480, 640, 3), dtype=np.uint8)
                _, buf = cv2.imencode('.jpg', black)
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')
            
            time.sleep(0.01)
    finally:
        # Không release ở đây để giữ cho các request khác dùng được
        pass


# Các route khác giữ nguyên như code của bạn
@app.route('/')
def home():
    return redirect(url_for('attend'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT Id, Username, Role, FullName 
                FROM Users 
                WHERE Username = ? AND PasswordHash = ?
            """, (username, password))
            user = cur.fetchone()
            cur.close()
            conn.close()

            if user:
                session['user_id']   = user[0]
                session['user']      = user[1]
                session['role']      = user[2]
                session['full_name'] = user[3] or user[1]
                flash(f'Đăng nhập thành công! Xin chào {session["full_name"]}', 'success')

                if user[2] == 'admin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('attend'))
            else:
                flash('Tên đăng nhập hoặc mật khẩu không đúng', 'danger')

    return render_template('login.html')


@app.route('/attend')
def attend():
    return render_template('attend.html')


@app.route('/test_camera')
def test_camera():
    return render_template('test_camera.html')


@app.route('/video_feed')
def video_feed():
    return Response(generate_video_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/register', methods=['GET', 'POST'])
@admin_required
def register():
    if request.method == 'POST':
        method = request.form.get('method')  # 'upload' hoặc 'capture'
        username = request.form.get('username')
        full_name = request.form.get('full_name')

        if not username or not full_name:
            flash('Thiếu thông tin bắt buộc (mã SV và họ tên)', 'danger')
            return redirect(url_for('register'))

        filepath = None
        encoding_bytes = None

        if method == 'upload':
            file = request.files.get('photo')
            if file and file.filename:
                os.makedirs('uploads', exist_ok=True)
                filepath = os.path.join('uploads', file.filename)
                file.save(filepath)
                encoding_bytes = encode_image_file(filepath)

        elif method == 'capture':
            photo_data = request.form.get('photo_data')
            if photo_data and photo_data.startswith('data:image/jpeg;base64,'):
                try:
                    img_data = base64.b64decode(photo_data.split(',')[1])
                    img = Image.open(BytesIO(img_data))
                    filepath = os.path.join('uploads', f'{username}_capture.jpg')
                    img.save(filepath, 'JPEG')
                    encoding_bytes = encode_image_file(filepath)
                except Exception as e:
                    print(f"Lỗi xử lý ảnh base64: {e}")
                    flash('Lỗi xử lý ảnh chụp từ webcam', 'danger')

        if encoding_bytes:
            if save_user(username, full_name, encoding_bytes):
                global known_encodings, known_names, known_ids
                known_encodings, known_names, known_ids = load_all_encodings()
                flash('Đăng ký khuôn mặt thành công!', 'success')
                if filepath and os.path.exists(filepath):
                    os.remove(filepath)
                return redirect(url_for('attend'))
            else:
                flash('Lỗi: Username đã tồn tại hoặc lỗi lưu dữ liệu', 'danger')
        else:
            flash('Không phát hiện khuôn mặt rõ ràng trong ảnh. Hãy thử ảnh chính diện, ánh sáng tốt.', 'danger')

        if filepath and os.path.exists(filepath):
            os.remove(filepath)

    return render_template('register.html')


# Route mới dành cho sinh viên đăng ký khuôn mặt (trả JSON cho AJAX)
@app.route('/student/register_face', methods=['GET', 'POST'])
def student_register_face():
    if request.method == 'GET':
        # Nếu gọi GET thì render trang đăng ký (giống route cũ)
        return render_template('register.html')

    # Xử lý POST (đăng ký khuôn mặt)
    method = request.form.get('method')
    username = request.form.get('username')
    full_name = request.form.get('full_name')

    if not username or not full_name:
        return jsonify({
            "status": "error",
            "message": "Thiếu thông tin bắt buộc (mã SV và họ tên)"
        }), 400

    filepath = None
    encoding_bytes = None

    try:
        if method == 'upload' and 'photo' in request.files:
            photo = request.files['photo']
            if photo.filename == '':
                return jsonify({"status": "error", "message": "Chưa chọn file ảnh"}), 400
            filepath = os.path.join('uploads', photo.filename)
            photo.save(filepath)
            encoding_bytes = encode_image_file(filepath)

        elif method == 'capture':
            photo_data = request.form.get('photo_data')
            if not photo_data:
                return jsonify({"status": "error", "message": "Không có dữ liệu ảnh chụp"}), 400
            # Chuyển base64 thành file tạm
            img_data = base64.b64decode(photo_data.split(',')[1])
            img = Image.open(BytesIO(img_data))
            filepath = os.path.join('uploads', f"capture_{username}.jpg")
            img.save(filepath)
            encoding_bytes = encode_image_file(filepath)

        if encoding_bytes:
            if save_user(username, full_name, encoding_bytes):
                # Reload encodings toàn cục
                global known_encodings, known_names, known_ids
                known_encodings, known_names, known_ids = load_all_encodings()
                if filepath and os.path.exists(filepath):
                    os.remove(filepath)
                return jsonify({
                    "status": "success",
                    "message": "Đăng ký khuôn mặt thành công!"
                }), 200
            else:
                return jsonify({
                    "status": "error",
                    "message": "Username đã tồn tại hoặc lỗi lưu dữ liệu"
                }), 400
        else:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({
                "status": "error",
                "message": "Không phát hiện khuôn mặt rõ ràng. Hãy thử ảnh chính diện, ánh sáng tốt."
            }), 400

    except Exception as e:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({
            "status": "error",
            "message": f"Lỗi hệ thống: {str(e)}"
        }), 500


# Các route admin giữ nguyên như cũ...
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    today_records = get_today_attendance()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT Id, Username, FullName, Role, CreatedAt 
        FROM Users 
        ORDER BY Id
    """)
    users = [dict(zip(['id', 'username', 'full_name', 'role', 'created_at'], row)) for row in cur.fetchall()]
    cur.close()
    conn.close()

    return render_template('admin_dashboard.html', records=today_records, users=users)


@app.route('/admin/export')
@admin_required
def export_attendance():
    conn = get_connection()
    if not conn:
        flash('Không kết nối được cơ sở dữ liệu', 'danger')
        return redirect(url_for('admin_dashboard'))

    cur = conn.cursor()
    cur.execute("""
        SELECT 
            u.Username, 
            u.FullName, 
            a.CheckInTime,
            CAST(a.CheckInTime AS DATE) AS Ngay
        FROM Attendance a
        JOIN Users u ON a.UserId = u.Id
        ORDER BY a.CheckInTime DESC
    """)
    data = cur.fetchall()
    cur.close()
    conn.close()

    if not data:
        flash('Chưa có dữ liệu điểm danh để xuất', 'info')
        return redirect(url_for('admin_dashboard'))

    output = StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(['Mã/Tên đăng nhập', 'Họ tên', 'Thời gian điểm danh', 'Ngày'])

    for row in data:
        writer.writerow([
            row[0],
            row[1] or 'Chưa cập nhật',
            row[2].strftime('%Y-%m-%d %H:%M:%S'),
            row[3].strftime('%Y-%m-%d')
        ])

    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=diem_danh_toan_bo.csv'
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    return response


@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    if user_id == session.get('user_id'):
        flash('Bạn không thể tự xóa tài khoản của chính mình', 'warning')
        return redirect(url_for('admin_dashboard'))

    conn = get_connection()
    if not conn:
        flash('Lỗi kết nối cơ sở dữ liệu', 'danger')
        return redirect(url_for('admin_dashboard'))

    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM Attendance WHERE UserId = ?", (user_id,))
        cur.execute("DELETE FROM Users WHERE Id = ?", (user_id,))
        conn.commit()
        flash('Đã xóa tài khoản thành công', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Lỗi khi xóa: {str(e)}', 'danger')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('admin_dashboard'))


@app.route('/logout')
def logout():
    session.clear()
    flash('Đã đăng xuất thành công', 'info')
    return redirect(url_for('login'))


if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    finally:
        close_camera()  # Đảm bảo release khi tắt server 