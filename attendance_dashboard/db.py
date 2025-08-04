import sqlite3

def connect_db():
    return sqlite3.connect('attendance.db')

def init_db():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            StudentID TEXT PRIMARY KEY,
            Name TEXT,
            TotalClasses INTEGER,
            ClassesAttended INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def insert_sample_data():
    conn = connect_db()
    cursor = conn.cursor()
    data = [
        ('S001', 'Aditya', 40, 38),
        ('S002', 'Ravi', 40, 35),
        ('S003', 'Neha', 40, 20),
        ('S004', 'Amit', 40, 10)
    ]
    cursor.executemany("INSERT OR IGNORE INTO attendance VALUES (?, ?, ?, ?)", data)
    conn.commit()
    conn.close()

def get_all_students():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM attendance")
    data = cursor.fetchall()
    conn.close()
    return data
