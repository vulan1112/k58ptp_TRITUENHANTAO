# test_connection.py - Kiểm tra kết nối SQL Server

import pyodbc
from config import SQL_SERVER_CONFIG

def list_drivers():
    """Liệt kê tất cả ODBC driver có sẵn"""
    print("=" * 60)
    print("DANH SÁCH CÁC ODBC DRIVER CÓ SẴN")
    print("=" * 60)
    drivers = pyodbc.drivers()
    if drivers:
        for i, driver in enumerate(drivers, 1):
            print(f"{i}. {driver}")
    else:
        print("Không tìm thấy driver nào!")
    print()

def test_connection():
    """Test kết nối SQL Server"""
    print("=" * 60)
    print("KIỂM TRA KẾT NỐI SQL SERVER")
    print("=" * 60)
    print(f"Server: {SQL_SERVER_CONFIG['server']}")
    print(f"Database: {SQL_SERVER_CONFIG['database']}")
    print(f"Driver: {SQL_SERVER_CONFIG['driver']}")
    print(f"Trusted Connection: {SQL_SERVER_CONFIG.get('trusted_connection', False)}")
    print("-" * 60)

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
        print("✓ KẾT NỐI THÀNH CÔNG!")
        print()

        # Test truy vấn đơn giản
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()
        print(f"SQL Server Version: {version[0]}")
        print()

        # Kiểm tra các bảng
        print("=" * 60)
        print("KIỂM TRA CÁC BẢNG TRONG DATABASE")
        print("=" * 60)
        cursor.execute("""
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE='BASE TABLE'
            ORDER BY TABLE_NAME
        """)
        tables = cursor.fetchall()
        if tables:
            for i, table in enumerate(tables, 1):
                print(f"{i}. {table[0]}")
                # Lấy số lượng record trong bảng
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                    count = cursor.fetchone()[0]
                    print(f"   → Số bản ghi: {count}")
                except Exception as e:
                    print(f"   → Lỗi đếm: {e}")
        else:
            print("Không tìm thấy bảng nào trong database!")
        print()

        cursor.close()
        conn.close()

    except pyodbc.Error as e:
        print(f"✗ LỖI KẾT NỐI: {e}")
        print()
        print("GIẢI PHÁP:")
        print("1. Kiểm tra tên server (dùng: Get-ComputerName hoặc hostname)")
        print("2. Kiểm tra SQL Server đang chạy (Services → MSSQL...)")
        print("3. Xác nhận tên database tồn tại")
        print("4. Nếu dùng SQL Auth, kiểm tra username/password")
        print("5. Liệt kê ODBC driver: pyodbc.drivers()")
        print()

if __name__ == '__main__':
    list_drivers()
    test_connection()
