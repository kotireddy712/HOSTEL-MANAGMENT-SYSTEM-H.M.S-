import mysql.connector
import csv

# Connect to MySQL
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="1234",
    database="hms_db"
)
cursor = conn.cursor()

# Open CSV file
with open("students_list1.csv", "r") as file:
    csv_reader = csv.DictReader(file)  # Reads using column names

    sql = """INSERT INTO student 
             (student_id, room, name, gender, email_id, contact_number, password, date_of_birth, hostel_name, first_login_date) 
             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

    for row in csv_reader:
        values = (
            row["student_id"],
            None,  # Room number is NULL
            row["name"],
            row["gender"],
            row["email_id"],
            row["contact_number"],  # Added contact number
            row["password"],
            row["date_of_birth"],  # Added date of birth
            None,
            None  # first_login_date is NULL initially
        )
        cursor.execute(sql, values)

conn.commit()
cursor.close()
conn.close()

print("CSV data successfully inserted into MySQL!")
