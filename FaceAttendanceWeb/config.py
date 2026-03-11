# config.py - Cấu hình kết nối SQL Server

SQL_SERVER_CONFIG = {
    'server': r'DESKTOP-UGLT6J3\SQLEXPRESS',   # thay bằng tên server của bạn nếu khác
    'database': 'AttendanceDB',
    'driver': 'ODBC Driver 17 for SQL Server',  # kiểm tra bằng pyodbc.drivers()
    'trusted_connection': True,                 # True = Windows Authentication
    # Nếu dùng SQL Authentication thì thêm:
    # 'username': 'sa',
    # 'password': 'your_password',
}