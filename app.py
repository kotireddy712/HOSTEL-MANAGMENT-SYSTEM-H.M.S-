from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
import razorpay
from datetime import datetime
from flask import Response
app = Flask(__name__)

app.secret_key = "mOH4AVjSv9hv8mPGPkj7oIAa" 

razorpay_client = razorpay.Client(auth=("rzp_test_1TN1UFcNAX9H61","mOH4AVjSv9hv8mPGPkj7oIAa"))
print("Razorpay Client Initialized:", razorpay_client)

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="1234",
        database="hms_db"
    )

@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        mail_id = request.form['mail_id']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)  # use DictCursor for key-value pairs
        cursor.execute("SELECT student_id, name FROM student WHERE email_id=%s AND password=%s", (mail_id, password))
        student = cursor.fetchone()

        if student:
            session['student_id'] = student['student_id']  # store student_id (VARCHAR)
            session['student_name'] = student['name']

            cursor.execute(
                "UPDATE student SET first_login_date = NOW() WHERE student_id = %s AND first_login_date IS NULL",
                (student['student_id'],)
            )
            conn.commit()
            conn.close()
            return redirect(url_for('student_dashboard'))
        else:
            conn.close()
            return render_template('failure.html', error="Invalid Email or Password")

    return render_template('student_login.html')

@app.route('/student_dashboard')
def student_dashboard():
    if 'student_id' in session:
        student_id = session['student_id']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = "SELECT fee_status FROM student WHERE student_id = %s"
        cursor.execute(query, (student_id,))
        student = cursor.fetchone()
        cursor.close()
        conn.close()

        fee_status = student['fee_status']
        return render_template('student_dashboard.html', user=session['student_name'], fee_status=fee_status)
    return redirect(url_for('student_login'))

@app.route('/feepayment')
def fee_payment():
    if 'student_id' in session:
        student_id = session['student_id']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT fee_status, 
                   (SELECT payment_date FROM fee_payment WHERE student_id = %s AND payment_status = 'Confirmed' LIMIT 1) AS payment_date,
                   (SELECT amount FROM fee_payment WHERE student_id = %s AND payment_status = 'Confirmed' LIMIT 1) AS amount
            FROM student
            WHERE student_id = %s
        """
        cursor.execute(query, (student_id, student_id, student_id))
        student = cursor.fetchone()
        cursor.close()
        conn.close()

        return render_template('fee_payment.html', student_id=student_id, fee_status=student['fee_status'], payment_date=student['payment_date'], amount=student['amount'])
    return redirect(url_for('student_login'))


from datetime import datetime

@app.route('/payment_success', methods=['GET'])
def payment_success():
    student_id = request.args.get('student_id')
    amount = request.args.get('amount')
    payment_id = request.args.get('payment_id')

    try:
        # verify the payment using Razorpay's API
        payment = razorpay_client.payment.fetch(payment_id)
        if payment['status'] == 'captured':
            # get the Razorpay payment timestamp (created_at)
            razorpay_created_at = payment['created_at']  # Unix timestamp
            payment_date = datetime.fromtimestamp(razorpay_created_at).strftime('%Y-%m-%d %H:%M:%S')

            # update the fee_payment table with the payment ID, status, and Razorpay's payment date
            conn = get_db_connection()
            cursor = conn.cursor()
            query = """
                UPDATE fee_payment
                SET payment_status = %s, payment_id = %s, payment_date = %s
                WHERE student_id = %s AND amount = %s AND payment_status = 'Pending'
            """
            cursor.execute(query, ('Confirmed', payment_id, payment_date, student_id, amount))
            
            query = """
                UPDATE student
                SET fee_status = 'Paid'
                WHERE student_id = %s
            """
            cursor.execute(query, (student_id,))
            conn.commit()
            cursor.close()
            conn.close()

            return render_template('payment_success.html', amount=amount, student_id=student_id)
        else:
            return "Payment verification failed!", 400
    except Exception as e:
        return f"An error occurred: {str(e)}", 500
    

@app.route('/create_order', methods=['POST'])
def create_order():
    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    student_id = session['student_id']
    amount = request.json['amount']

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT * FROM fee_payment
            WHERE student_id = %s AND payment_status = 'Pending'
        """
        cursor.execute(query, (student_id,))
        existing_payment = cursor.fetchone()

        if existing_payment:
            # update the existing 'Pending' entry
            query = """
                UPDATE fee_payment
                SET amount = %s, payment_id = NULL, payment_date = NULL
                WHERE student_id = %s AND payment_status = 'Pending'
            """
            cursor.execute(query, (amount, student_id))
        else:
            # insert a new record if no 'Pending' entry exists
            query = """
                INSERT INTO fee_payment (student_id, amount, payment_status)
                VALUES (%s, %s, %s)
            """
            cursor.execute(query, (student_id, amount, 'Pending'))

        conn.commit()

        # create an order in Razorpay
        order_data = {
            "amount": int(amount) * 100,  # Convert to paise
            "currency": "INR",
            "receipt": f"order_rcpt_{student_id}",
            "payment_capture": 1  # auto-capture payment
        }
        order = razorpay_client.order.create(order_data)

        cursor.close()
        conn.close()

        # Return the order ID to the frontend
        return {"order_id": order['id']}
    except Exception as e:
        return {"error": str(e)}, 500

from flask import Response, redirect, url_for

@app.route('/download_receipt')
def download_receipt():
    if 'student_id' in session:
        student_id = session['student_id']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT student_id, amount, payment_date, payment_id
            FROM fee_payment
            WHERE student_id = %s AND payment_status = 'Confirmed'
            LIMIT 1
        """
        cursor.execute(query, (student_id,))
        payment = cursor.fetchone()
        cursor.close()
        conn.close()

        if payment:
            # Generate a simple receipt as a downloadable text file
            receipt_content = f"""
            Receipt for Fee Payment
            ------------------------
            Student ID: {payment['student_id']}
            Payment ID: {payment['payment_id']}
            Amount Paid: ₹{payment['amount']}
            Payment Date: {payment['payment_date']}
            ------------------------
            Thank you for your payment!
            """
            return Response(
                receipt_content,
                mimetype="text/plain",
                headers={"Content-Disposition": "attachment;filename=receipt.txt"}
            )
        else:
            return "No payment record found.", 404
    return redirect(url_for('student_login'))


@app.route('/room-allocation')
def room_allocation():
    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    student_id = session['student_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Check if already allocated
    cursor.execute("SELECT room FROM student WHERE student_id = %s", (student_id,))
    student_data = cursor.fetchone()

    if student_data and student_data['room']:
        conn.close()
        return render_template('room_allocation.html', message=f"You are already allocated to Room {student_data['room']}", message_type="error")

    # Get gender
    cursor.execute("SELECT gender FROM student WHERE student_id = %s", (student_id,))
    student_info = cursor.fetchone()
    gender = student_info['gender']

    # Define hostel preferences
    male_hostels = ['A', 'B', 'C']
    female_hostel = 'G'

    if gender == 'F':
        hostel_list = [female_hostel]
    else:
        hostel_list = male_hostels

    allocated_room = None
    allocated_hostel = None

    # Try to find a room in one of the hostels
    for hostel in hostel_list:
        cursor.execute(
            "SELECT room_number FROM room WHERE hostel_name = %s AND available_space > 0 ORDER BY room_number ASC LIMIT 1",
            (hostel,)
        )
        room_data = cursor.fetchone()
        if room_data:
            allocated_room = room_data['room_number']
            allocated_hostel = hostel  # Save the hostel where the room was found
            break

    if not allocated_room:
        conn.close()
        return render_template('room_allocation.html', message="No available rooms in your assigned hostel. Please contact admin.", message_type="error")

    # Perform updates
    cursor.execute("UPDATE student SET room = %s, hostel_name = %s WHERE student_id = %s", 
                   (allocated_room, allocated_hostel, student_id))

    cursor.execute("UPDATE room SET available_space = available_space - 1 WHERE room_number = %s", 
                   (allocated_room,))

    cursor.execute("UPDATE hostel SET total_students_present = total_students_present + 1 WHERE hostel_name = %s", 
                   (allocated_hostel,))

    conn.commit()
    conn.close()

    return render_template('room_allocation.html', message=f"Room {allocated_room} allocated successfully in Hostel {allocated_hostel}!", message_type="success")


@app.route('/maintenance-request', methods=['GET', 'POST'])
def maintenance_request():
    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    if request.method == 'POST':
        description = request.form['description']
        student_id = session['student_id']  # Fetch student_id from session

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT room FROM student WHERE student_id = %s", (student_id,))
        student_data = cursor.fetchone()

        if student_data:
            room_number = student_data[0]  # extract `room` value
        else:
            room_number = None  # handle case where student doesn't exist

        cursor.execute("""
            INSERT INTO maintenance_request (student_id, room_number, description, request_date) 
            VALUES (%s, %s, %s, NOW())
        """, (student_id, room_number, description))

        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for('student_dashboard'))  # Redirect after submission

    return render_template('maintenance_request.html')


@app.route('/apply-leave', methods=['GET', 'POST'])
def apply_leave():
    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    if request.method == 'POST':
        description = request.form['description']
        return_date = request.form['return_date']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO student_leave (student_id, reason, start_date, return_date) VALUES (%s, %s, NOW(), %s)",
                       (session['student_id'], description, return_date))
        conn.commit()
        conn.close()

        return redirect(url_for('student_dashboard'))
    return render_template('apply_leave.html')

@app.route('/rules')
def rules():
    if 'student_id' in session:
        return render_template('rules.html')
    return redirect(url_for('student_login'))

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email_id = request.form['email_id']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT staff_id, name FROM staff WHERE email_id=%s AND password=%s", (email_id, password))
        admin = cursor.fetchone()
        conn.close()

        if admin:
            session['admin_id'] = admin['staff_id']
            session['admin_name'] = admin['name']
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('failure.html', error="Invalid Admin Credentials")

    return render_template('admin_login.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin_id' in session:
        return render_template('admin_dashboard.html', user=session['admin_name'])
    return redirect(url_for('admin_login'))

# 🔹 Admin Dashboard Pages (Under Construction)
@app.route('/manage_students')
def manage_students():
    return render_template('manage_students.html')

@app.route('/view_students', methods=['GET', 'POST'])
def view_students():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get search query
    search_query = request.form.get('search_query', '')

    # Pagination Logic
    page = int(request.args.get('page', 1))  # Get current page, default to 1
    students_per_page = 50
    offset = (page - 1) * students_per_page  # Calculate OFFSET

    if search_query:
        cursor.execute("""
            SELECT student_id, name, date_of_birth, contact_number, email_id, gender, room, first_login_date
            FROM student 
            WHERE student_id LIKE %s OR name LIKE %s OR hostel_name LIKE %s
            LIMIT %s OFFSET %s
        """, (f"%{search_query}%", f"%{search_query}%", f"%{search_query}" , students_per_page, offset))
    else:
        cursor.execute("""
            SELECT student_id, name, date_of_birth, contact_number, email_id, gender, room, first_login_date
            FROM student 
            LIMIT %s OFFSET %s
        """, (students_per_page, offset))

    students = cursor.fetchall()
    conn.close()

    return render_template('view_students.html', students=students, search_query=search_query, page=page)

@app.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        student_id = request.form['student_id']
        name = request.form['name']
        email_id = request.form['email_id']
        password = request.form['password']
        date_of_birth = request.form['date_of_birth']
        contact_number = request.form['contact_number']
        gender = request.form['gender']

        conn = get_db_connection()
        cursor = conn.cursor()

        # 🔹 Check if student_id already exists
        cursor.execute("SELECT * FROM student WHERE student_id = %s", (student_id,))
        existing_student = cursor.fetchone()

        # 🔹 Check if email_id already exists
        cursor.execute("SELECT * FROM student WHERE email_id = %s", (email_id,))
        existing_email = cursor.fetchone()

        if existing_student:
            flash("Student ID already exists!", "error")
            conn.close()
            return redirect(url_for('add_student'))  # Reload the form with error message

        if existing_email:
            flash("Email ID already exists!", "error")
            conn.close()
            return redirect(url_for('add_student'))  # Reload the form with error message

        # 🔹 Insert new student record
        cursor.execute("""
            INSERT INTO student (student_id, name, email_id, password, date_of_birth, contact_number, gender)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (student_id, name, email_id, password, date_of_birth, contact_number, gender))
        
        conn.commit()
        conn.close()
        flash("Student added successfully!", "success")
        return redirect(url_for('admin_dashboard'))  # Redirect to admin_dashboard

    return render_template('add_student.html')  # Show form on GET request

@app.route('/edit_student')
def edit_student():
    return "<h2>✏️ Edit Student Details - Page Under Construction</h2>"

@app.route('/delete_student', methods=['GET', 'POST'])
def delete_student():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    search_query = request.form.get('search_query', '')

    if search_query:
        cursor.execute("""
            SELECT student_id, name, email_id, room
            FROM student
            WHERE student_id LIKE %s OR name LIKE %s
        """, (f"%{search_query}%", f"%{search_query}%"))
    else:
        cursor.execute("SELECT student_id, name, email_id, room FROM student")

    students = cursor.fetchall()

    if request.method == 'POST' and 'delete_selected' in request.form:
        selected_students = request.form.getlist('selected_students')

        if selected_students:
            # Fetch rooms and hostels of selected students
            query = """
                SELECT s.room, r.hostel_name 
                FROM student s 
                JOIN room r ON s.room = r.room_number 
                WHERE s.student_id IN ({})
            """.format(','.join(['%s'] * len(selected_students)))
            cursor.execute(query, tuple(selected_students))
            room_hostel_info = cursor.fetchall()

            # Count how many students are being deleted per hostel
            hostel_decrement = {}
            for room, hostel in room_hostel_info:
                if room:
                    cursor.execute("UPDATE room SET available_space = available_space + 1 WHERE room_number = %s", (room,))
                if hostel:
                    hostel_decrement[hostel] = hostel_decrement.get(hostel, 0) + 1

            # Update total_students_present in each affected hostel
            for hostel, count in hostel_decrement.items():
                cursor.execute("""
                    UPDATE hostel 
                    SET total_students_present = total_students_present - %s 
                    WHERE hostel_name = %s
                """, (count, hostel))

            # Delete the student records
            cursor.executemany("DELETE FROM student WHERE student_id = %s", [(sid,) for sid in selected_students])
            conn.commit()

            flash("Selected students have been deleted and rooms + hostel info updated!", "success")
            return redirect(url_for('delete_student'))

    conn.close()
    return render_template('delete_student.html', students=students, search_query=search_query)

@app.route('/manage_rooms')
def manage_rooms():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch total students present in each hostel
    cursor.execute("""
        SELECT h.hostel_name, 200 - COALESCE(SUM(r.available_space), 0) AS total_students_present
        FROM hostel h
        LEFT JOIN room r ON h.hostel_name = r.hostel_name
        GROUP BY h.hostel_name
    """)
    hostels = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("manage_rooms.html", hostels=hostels)

@app.route('/manage_rooms/<hostel>')
def manage_hostel(hostel):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Check if the hostel exists
    cursor.execute("SELECT * FROM hostel WHERE hostel_name = %s", (hostel,))
    hostel_data = cursor.fetchone()
    if not hostel_data:
        cursor.close()
        conn.close()
        return f"Hostel {hostel} not found!", 404

    # Recalculate total_students_present from student table
    cursor.execute("""
        SELECT COUNT(*) AS total_students_present
        FROM student
        WHERE hostel_name = %s
    """, (hostel,))
    total_students = cursor.fetchone()['total_students_present']

    # Update total_students_present in hostel table
    cursor.execute("""
        UPDATE hostel 
        SET total_students_present = %s 
        WHERE hostel_name = %s
    """, (total_students, hostel))
    conn.commit()

    # Fetch students in that hostel directly from student table
    cursor.execute("""
        SELECT student_id, name, email_id, contact_number, room
        FROM student
        WHERE hostel_name = %s
    """, (hostel,))
    students = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("hostel_details.html", hostel=hostel, total_students=total_students, students=students)


@app.route('/complaints', methods=['GET', 'POST'])
def view_complaints():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))  # Restrict access if not logged in

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Handle POST requests
    if request.method == 'POST':
        # Check if the request is for deleting complaints
        selected_ids = request.form.getlist('selected_complaints')
        if selected_ids:
            query = "DELETE FROM maintenance_request WHERE request_id IN (%s)" % ','.join(['%s'] * len(selected_ids))
            cursor.execute(query, tuple(selected_ids))
            conn.commit()
            flash(f"{len(selected_ids)} complaints deleted successfully!", "success")
            return redirect(url_for('view_complaints'))  # Redirect after deletion

        # Check if the request is for updating the status
        request_id = request.form.get('request_id')
        new_status = request.form.get('status')

        if request_id and new_status:
            cursor.execute("UPDATE maintenance_request SET status = %s WHERE request_id = %s", (new_status, request_id))
            conn.commit()
            flash("Complaint status updated successfully!", "success")
            return redirect(url_for('view_complaints'))  # Redirect after update

    # if GET request, display complaints
    status_filter = request.args.get('status', '')

    if status_filter:
        query = "SELECT * FROM maintenance_request WHERE status = %s"
        cursor.execute(query, (status_filter,))
    else:
        query = "SELECT * FROM maintenance_request"
        cursor.execute(query)

    complaints = cursor.fetchall()
    
    cursor.close()
    conn.close()

    return render_template("complaints.html", complaints=complaints, status_filter=status_filter)

@app.route('/update_status', methods=['POST'])
def update_status():
    request_id = request.form['request_id']
    new_status = request.form['status']

    # Connect to database and update status
    conn = get_db_connection()  # Replace with your actual database name
    cursor = conn.cursor()
    cursor.execute("UPDATE maintenance_request SET status = %s WHERE request_id = %s", (new_status, request_id))
    conn.commit()
    conn.close()

    return redirect(url_for('view_complaints'))  # Redirect back to the complaints page

@app.route('/staff_management')
def staff_management():
    return render_template('manage_staff.html')


@app.route('/add_staff', methods=['GET', 'POST'])
def add_staff():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        staff_id = request.form['staff_id']
        name = request.form['name']
        email_id = request.form['email_id']
        contact_number = request.form['contact_number']
        hostel_name = request.form['hostel_name']
        designation = request.form['designation']
        gender = request.form['gender']

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if staff_id already exists
        cursor.execute("SELECT * FROM staff WHERE staff_id = %s", (staff_id,))
        existing_staff = cursor.fetchone()

        if existing_staff:
            flash("Staff ID already exists!", "error")
            conn.close()
            return redirect(url_for('add_staff'))

        # Insert new staff record
        cursor.execute("""
            INSERT INTO staff (staff_id, name, email_id, contact_number, hostel_name, designation, gender)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (staff_id, name, email_id, contact_number, hostel_name, designation, gender))
        
        conn.commit()
        conn.close()
        flash("Staff added successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('add_staff.html')  # Show form on GET request

@app.route('/view_staff', methods=['GET'])
def view_staff():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get search query
    search_query = request.args.get('search_query', '')

    # Pagination Logic
    page = int(request.args.get('page', 1))  # Get current page, default to 1
    staff_per_page = 50
    offset = (page - 1) * staff_per_page  # Calculate OFFSET

    if search_query:
        cursor.execute("""
            SELECT staff_id, name, email_id, contact_number, hostel_name, designation, gender
            FROM staff 
            WHERE staff_id LIKE %s OR name LIKE %s 
            LIMIT %s OFFSET %s
        """, (f"%{search_query}%", f"%{search_query}%", staff_per_page, offset))
    else:
        cursor.execute("""
            SELECT staff_id, name, email_id, contact_number, hostel_name, designation, gender
            FROM staff 
            LIMIT %s OFFSET %s
        """, (staff_per_page, offset))

    staff_members = cursor.fetchall()
    conn.close()

    return render_template('view_staff.html', staff_list=staff_members, search_query=search_query, page=page)

@app.route('/edit_staff')
def edit_staff():
    return "<h2>✏️ Edit Staff Details - Page Under Construction</h2>"

@app.route('/delete_staff', methods=['GET', 'POST'])
def delete_staff():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    search_query = request.form.get('search_query', '')

    # Fetch staff members based on search query
    if search_query:
        cursor.execute("""
            SELECT staff_id, name, email_id, designation
            FROM staff
            WHERE staff_id LIKE %s OR name LIKE %s
        """, (f"%{search_query}%", f"%{search_query}%"))
    else:
        cursor.execute("""
            SELECT staff_id, name, email_id, designation
            FROM staff
        """)

    staff_members = cursor.fetchall()

    # Handle staff deletion
    if request.method == 'POST' and 'delete_selected' in request.form:
        selected_staff = request.form.getlist('selected_staff')
        if selected_staff:
            cursor.executemany("DELETE FROM staff WHERE staff_id = %s", [(sid,) for sid in selected_staff])
            conn.commit()
            flash("Selected staff members have been deleted!", "success")
            return redirect(url_for('delete_staff'))  # Refresh the page after deletion

    conn.close()
    return render_template('delete_staff.html', staff=staff_members, search_query=search_query)



@app.route('/leave_requests', methods=['GET', 'POST'])
def leave_requests():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Handle DELETE request (Bulk Deletion of leave requests)
    if request.method == 'POST':
        selected_leaves = request.form.getlist('selected_leaves')
        if selected_leaves:
            delete_query = "DELETE FROM student_leave WHERE leave_id IN (" + ",".join(["%s"] * len(selected_leaves)) + ")"
            cursor.execute(delete_query, selected_leaves)
            conn.commit()

        # Handle status update request
        leave_id = request.form.get('leave_id')
        new_status = request.form.get('status')
        if leave_id and new_status in ["On leave", "Returned"]:
            update_query = "UPDATE student_leave SET status = %s WHERE leave_id = %s"
            cursor.execute(update_query, (new_status, leave_id))
            conn.commit()

    # Get the filter value from the request (default to showing all)
    status_filter = request.args.get('status')

    # Base query to fetch leave requests
    query = '''
        SELECT sl.*, s.name, s.contact_number
        FROM student_leave sl
        JOIN student s ON sl.student_id = s.student_id
    '''
    
    # Apply filtering if a status is provided
    if status_filter in ["On leave", "Returned"]:
        query += " WHERE sl.status = %s"
        cursor.execute(query, (status_filter,))
    else:
        cursor.execute(query)

    leaves = cursor.fetchall()

    # Query to count only "On leave" students
    count_query = '''
        SELECT COUNT(*) AS on_leave_count
        FROM student_leave
        WHERE status = 'On leave'
    '''
    cursor.execute(count_query)
    on_leave_count = cursor.fetchone()['on_leave_count']

    cursor.close()
    conn.close()

    return render_template(
        "manage_leaves.html", 
        leaves=leaves, 
        status_filter=status_filter,
        on_leave_count=on_leave_count
    )

@app.route('/update_leave_status', methods=['POST'])
def update_leave_status():
    leave_id = request.form['leave_id']
    new_status = request.form['status']

    # Connect to database and update status
    conn = get_db_connection()  # Replace with your actual database name
    cursor = conn.cursor()
    cursor.execute("UPDATE student_leave SET status = %s WHERE leave_id = %s", (new_status, leave_id))
    conn.commit()
    conn.close()

    return redirect(url_for('leave_requests'))  # Redirect back to the complaints page

@app.route('/view_payments', methods=['GET', 'POST'])
def view_payments():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get search query
    search_query = request.form.get('search_query', '')

    # Pagination Logic
    page = int(request.args.get('page', 1))  # Get current page, default to 1
    payments_per_page = 50
    offset = (page - 1) * payments_per_page  # Calculate OFFSET

    if search_query:
        cursor.execute("""
            SELECT fp.payment_id, fp.student_id, s.name, fp.amount, fp.payment_status, fp.payment_date
            FROM fee_payment fp
            JOIN student s ON fp.student_id = s.student_id
            WHERE fp.payment_id LIKE %s OR fp.student_id LIKE %s OR s.name LIKE %s
            LIMIT %s OFFSET %s
        """, (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%", payments_per_page, offset))
    else:
        cursor.execute("""
            SELECT fp.payment_id, fp.student_id, s.name, fp.amount, fp.payment_status, fp.payment_date
            FROM fee_payment fp
            JOIN student s ON fp.student_id = s.student_id
            LIMIT %s OFFSET %s
        """, (payments_per_page, offset))

    payments = cursor.fetchall()
    conn.close()

    return render_template('view_payments.html', payments=payments, search_query=search_query, page=page)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('welcome'))

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
