from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Required for session handling

# Database Connection
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",  # Replace with your MySQL root password
    database="student_db"
)
cursor = conn.cursor()

# 🔹 Main Dashboard (Before Login)
@app.route('/')
def welcome():
    return render_template('welcome.html')

# 🔹 Student Login Page
@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        mail_id = request.form['mail_id']
        password = request.form['password']

        # Query to check login details
        cursor.execute("SELECT name FROM student WHERE mail_id=%s AND password=%s", (mail_id, password))
        student = cursor.fetchone()

        if student:
            session['student_name'] = student[0]  # Store student name in session
            return redirect(url_for('student_dashboard'))  # ✅ Redirect to student_dashboard route
        else:
            return render_template('failure.html', error="Invalid Email or Password")  # ❌ Show failure page

    return render_template('student_login.html')

# 🔹 Student Dashboard Page (New Route)
@app.route('/student_dashboard')
def student_dashboard():
    if 'student_name' in session:
        return render_template('student_dashboard.html', user=session['student_name'])
    else:
        return redirect(url_for('student_login'))  # Redirect if not logged in

# 🔹 Route for Hostel Rules
@app.route('/rules')
def rules():
    if 'student_name' in session:
        return render_template('rules.html')
    else:
        return redirect(url_for('student_login'))  # Redirect to login if session is not active

# 🔹 Admin Login Page
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        user_id = request.form['user_id']
        password = request.form['password']

        # Query to check admin credentials
        cursor.execute("SELECT name FROM admin WHERE user_id=%s AND password=%s", (user_id, password))
        admin = cursor.fetchone()

        if admin:
            session['admin_name'] = admin[0]  # Store admin name in session
            return redirect(url_for('admin_dashboard'))  # ✅ Redirect to admin_dashboard
        else:
            return render_template('failure.html', error="Invalid Admin Credentials")  # ❌ Show failure page

    return render_template('admin_login.html')

# 🔹 Admin Dashboard Page (New Route)
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin_name' in session:
        return render_template('admin_dashboard.html', user=session['admin_name'])
    else:
        return redirect(url_for('admin_login'))  # Redirect if not logged in

# 🔹 Logout Route
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('welcome'))  # Back to welcome.html after logout

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)  # Accessible on network
