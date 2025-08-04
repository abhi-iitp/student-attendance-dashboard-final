from flask import Flask, render_template, request, redirect, url_for, send_file, make_response, session, flash
from collections import Counter
from xhtml2pdf import pisa
import sqlite3
import pandas as pd
import io, os
import openpyxl

app = Flask(__name__)
app.secret_key = "my_secure_secret"

# 📌 Database utility functions
def connect_db():
    return sqlite3.connect("attendance.db")

def init_db():
    conn = connect_db()
    cursor = conn.cursor()

    # ✅ Attendance table
    cursor.execute('''CREATE TABLE IF NOT EXISTS attendance (
        StudentID TEXT PRIMARY KEY,
        Name TEXT NOT NULL,
        TotalClasses INTEGER NOT NULL,
        ClassesAttended INTEGER NOT NULL
    )''')

    # ✅ Admin table
    cursor.execute('''CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL
    )''')

    # ✅ Insert default admin if not exists
    cursor.execute("SELECT * FROM admin WHERE username='admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO admin (username, password) VALUES (?, ?)", ('admin', 'admin123'))

    conn.commit()
    conn.close()

def insert_sample_data():
    conn = connect_db()
    cursor = conn.cursor()
    sample = [
        ("S001", "Ananya", 40, 36),
        ("S002", "Ravi", 42, 30),
        ("S003", "Simran", 38, 34),
        ("S004", "Aditya", 40, 20)
    ]
    for s in sample:
        cursor.execute("INSERT OR IGNORE INTO attendance VALUES (?, ?, ?, ?)", s)
    conn.commit()
    conn.close()

def get_all_students():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM attendance")
    rows = cursor.fetchall()
    conn.close()
    return rows

# 🔧 Initialize database tables and data
init_db()
insert_sample_data()

@app.route('/', methods=['GET', 'POST'])
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM attendance")
    data = cursor.fetchall()
    conn.close()

    table_data = []
    names, percentages, categories = [], [], []

    for sid, name, total, attended in data:
        percent = round((attended / total) * 100, 2) if total else 0
        if percent >= 90:
            category = "Excellent"
        elif percent >= 75:
            category = "Good"
        elif percent >= 50:
            category = "Average"
        else:
            category = "Low Performer"

        table_data.append({
            "StudentID": sid,
            "Name": name,
            "TotalClasses": total,
            "ClassesAttended": attended,
            "Attendance%": percent,
            "Category": category
        })

    # 🟦 Apply Filters
    if request.method == 'POST':
        name_filter = request.form.get('name', '').lower()
        min_percent = request.form.get('min_percent')
        max_percent = request.form.get('max_percent')
        category = request.form.get('category')
        sort_by = request.form.get('sort_by')

        if name_filter:
            table_data = [row for row in table_data if name_filter in row['Name'].lower()]
        if min_percent:
            table_data = [row for row in table_data if row['Attendance%'] >= float(min_percent)]
        if max_percent:
            table_data = [row for row in table_data if row['Attendance%'] <= float(max_percent)]
        if category:
            table_data = [row for row in table_data if row['Category'] == category]

        if sort_by == "name_asc":
            table_data.sort(key=lambda x: x['Name'])
        elif sort_by == "name_desc":
            table_data.sort(key=lambda x: x['Name'], reverse=True)
        elif sort_by == "percent_asc":
            table_data.sort(key=lambda x: x['Attendance%'])
        elif sort_by == "percent_desc":
            table_data.sort(key=lambda x: x['Attendance%'], reverse=True)
        elif sort_by == "category_asc":
            table_data.sort(key=lambda x: x['Category'])
        elif sort_by == "category_desc":
            table_data.sort(key=lambda x: x['Category'], reverse=True)

    for row in table_data:
        names.append(row['Name'])
        percentages.append(row['Attendance%'])
        categories.append(row['Category'])

    pie_counter = Counter(categories)

        # 🧮 Pagination
    page = int(request.args.get('page', 1))
    per_page = 5
    total_students = len(table_data)
    total_pages = (total_students + per_page - 1) // per_page

    start = (page - 1) * per_page
    end = start + per_page
    table_data_paginated = table_data[start:end]

    return render_template("index.html", students=table_data_paginated,
                           bar_data={"names": names, "percentages": percentages},
                           pie_data={"labels": list(pie_counter.keys()), "data": list(pie_counter.values())},
                           page=page, total_pages=total_pages)


@app.route("/edit/<student_id>", methods=["GET", "POST"])
def edit_attendance(student_id):
    conn = connect_db()
    cursor = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        total_classes = int(request.form["total_classes"])
        classes_attended = int(request.form["classes_attended"])

        cursor.execute("""
            UPDATE attendance
            SET Name = ?, TotalClasses = ?, ClassesAttended = ?
            WHERE StudentID = ?
        """, (name, total_classes, classes_attended, student_id))
        
        conn.commit()
        conn.close()
        flash("Attendance record updated successfully!", "success")
        return redirect(url_for("index"))

    else:
        cursor.execute("SELECT * FROM attendance WHERE StudentID = ?", (student_id,))
        student = cursor.fetchone()
        conn.close()
        return render_template("edit.html", student=student)


@app.route('/delete/<student_id>')
def delete_attendance(student_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM attendance WHERE StudentID=?", (student_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/export/excel')
def export_excel():
    students = get_all_students()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Attendance Report"
    ws.append(["StudentID", "Name", "TotalClasses", "ClassesAttended", "Attendance %"])

    for s in students:
        sid, name, total, attended = s
        percent = round((attended / total) * 100, 2) if total else 0
        ws.append([sid, name, total, attended, percent])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="attendance_report.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route('/export/pdf')
def export_pdf():
    students = get_all_students()
    table_data = []

    for sid, name, total, attended in students:
        percent = round((attended / total) * 100, 2) if total else 0
        table_data.append({
            "StudentID": sid,
            "Name": name,
            "TotalClasses": total,
            "ClassesAttended": attended,
            "Attendance%": percent
        })

    rendered = render_template("pdf_template.html", students=table_data)
    result = io.BytesIO()
    pisa_status = pisa.CreatePDF(rendered, dest=result)

    if pisa_status.err:
        return "PDF generation error"
    
    response = make_response(result.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=attendance_report.pdf'
    response.mimetype = 'application/pdf'
    return response

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admin WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password")
    
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/add', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        student_id = request.form['student_id']
        name = request.form['name']
        total_classes = int(request.form['total_classes'])
        attended = int(request.form['attended'])

        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO attendance VALUES (?, ?, ?, ?)",
                       (student_id, name, total_classes, attended))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    return render_template("add.html")

if __name__ == "__main__":
    app.run(debug=True)
