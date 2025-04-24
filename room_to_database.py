import pandas as pd
import mysql.connector

# Database connection details (change as per your MySQL setup)
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "1234",
    "database": "hms_db"
}

# Connect to MySQL
conn = mysql.connector.connect(**db_config)
cursor = conn.cursor()

# Create table if not exists
create_table_query = """
CREATE TABLE IF NOT EXISTS room (
    room_number VARCHAR(10) PRIMARY KEY,
    hostel_name VARCHAR(5),
    available_space INT
);
"""
cursor.execute(create_table_query)

# Read CSV file
csv_file = "room_data.csv"  # Update with correct path if needed
df = pd.read_csv(csv_file)

# Insert data into MySQL
insert_query = "INSERT INTO room (room_number, hostel_name, available_space) VALUES (%s, %s, %s)"

for _, row in df.iterrows():
    cursor.execute(insert_query, tuple(row))

# Commit and close connection
conn.commit()
cursor.close()
conn.close()

print("Data inserted successfully!")

