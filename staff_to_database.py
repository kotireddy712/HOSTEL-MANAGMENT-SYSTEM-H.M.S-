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
with open("staff_list.csv", "r") as file:
    csv_reader = csv.DictReader(file)  # Reads using column names

    sql = """INSERT INTO staff 
             (staff_id, name, email_id, contact_number, hostel_name, designation, gender, password) 
             VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""

    for row in csv_reader:
        values = (
            row["staff_id"],
            row["name"],
            row["email_id"],
            row["contact_number"],
            row["hostel_name"],
            row["designation"],
            row["gender"],
            row["password"] if row["password"] else None  # Set NULL if password is empty
        )
        cursor.execute(sql, values)

conn.commit()
cursor.close()
conn.close()

print("CSV data successfully inserted into MySQL!")
 
