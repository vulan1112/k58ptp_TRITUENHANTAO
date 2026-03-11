# db.py - Xử lý kết nối và truy vấn SQL Server

import pyodbc
import numpy as np
import datetime
from config import SQL_SERVER_CONFIG

def get_connection():
    conn_str = (
        f"DRIVER={{{SQL_SERVER_CONFIG['driver']}}};"
        f"SERVER={SQL_SERVER_CONFIG['server']};"
        f"DATABASE={SQL_SERVER_CONFIG['database']};"
    )
    if SQL_SERVER_CONFIG.get('trusted_connection'):
        conn_str += "Trusted_Connection=yes;"
    else:
        conn_str += f"UID={SQL_SERVER_CONFIG['username']};PWD={SQL_SERVER_CONFIG['password']};"

    try:
        conn = pyodbc.connect(conn_str)
        return conn
    except pyodbc.Error as e:
        print(f"Lỗi kết nối SQL Server: {e}")
        return None


def save_user(username, full_name, encoding_bytes, role='student'):
    conn = get_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM Users WHERE Username = ?)
                INSERT INTO Users (Username, FullName, Encoding, Role)
                VALUES (?, ?, ?, ?)
        """, (username, username, full_name, encoding_bytes, role))
        conn.commit()
        return cursor.rowcount > 0 or cursor.rowcount == -1  # -1 nếu đã tồn tại nhưng không lỗi
    except Exception as e:
        print(f"Lỗi khi lưu user: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def load_all_encodings():
    conn = get_connection()
    if not conn:
        return [], [], []
    cursor = conn.cursor()
    cursor.execute("SELECT Id, Username, Encoding FROM Users WHERE Encoding IS NOT NULL")
    rows = cursor.fetchall()

    known_ids = []
    known_names = []
    known_encodings = []

    for row in rows:
        if row.Encoding:
            encoding_array = np.frombuffer(row.Encoding, dtype=np.float64)
            known_ids.append(row.Id)
            known_names.append(row.Username)
            known_encodings.append(encoding_array)

    cursor.close()
    conn.close()
    return known_encodings, known_names, known_ids


def log_attendance(user_id):
    conn = get_connection()
    if not conn:
        return
    cursor = conn.cursor()
    try:
        # LUÔN insert, không check tồn tại trong ngày nữa
        cursor.execute("""
            INSERT INTO Attendance (UserId, CheckInTime)
            VALUES (?, GETDATE())
        """, (user_id,))
        conn.commit()
        print(f"[LOG] ✓ Điểm danh thành công - UserID {user_id} lúc {datetime.datetime.now().strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"Lỗi ghi điểm danh: {e}")
    finally:
        cursor.close()
        conn.close()


def get_today_attendance():
    conn = get_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            u.Username, 
            u.FullName, 
            a.CheckInTime
        FROM Attendance a
        INNER JOIN Users u ON a.UserId = u.Id
        WHERE CAST(a.CheckInTime AS DATE) = CAST(GETDATE() AS DATE)
        ORDER BY a.CheckInTime DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [{"username": r[0], "full_name": r[1], "time": r[2]} for r in rows]