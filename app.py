import os
import time
from datetime import datetime, timedelta
from hashlib import sha256

import RPi.GPIO as GPIO
from cs50 import SQL
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_qrcode import QRcode
from mfrc522 import SimpleMFRC522
from picamera2 import Picamera2
from PIL import Image
from pyzbar import pyzbar

app = Flask(__name__)
app.secret_key = "your_secret_key"
QRcode(app)
key = "example_key"

# Database initialization
db = SQL("sqlite:///users.db")


def init_db():
    # Create users table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            user_type TEXT NOT NULL,
            prof_id TEXT
        )
    """
    )
    # Create attendance table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            professor TEXT NOT NULL,
            timestamp DATETIME NOT NULL
        )
    """
    )

    # Create lectures table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS lectures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            professor TEXT NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME
        )
    """
    )

    # Insert demo users
    db.execute(
        "INSERT OR IGNORE INTO users (username, password, user_type) VALUES ('student1', 'password1', 'student')"
    )
    db.execute(
        "INSERT OR IGNORE INTO users (username, password, user_type) VALUES ('student2', 'password2', 'student')"
    )
    db.execute(
        "INSERT OR IGNORE INTO users (username, password, user_type, prof_id) VALUES ('prof', 'profpassword', 'professor', 'PROF001')"
    )
    # Insert demo attendance records
    db.execute(
        """
        INSERT INTO attendance (username, professor, timestamp) 
        VALUES ('student1', 'Professor Smith', '2023-04-15 09:00:00')
    """
    )
    db.execute(
        """
        INSERT INTO attendance (username, professor, timestamp) 
        VALUES ('student2', 'Professor Smith', '2023-04-15 09:02:00')
    """
    )
    db.execute(
        """
        INSERT INTO attendance (username, professor, timestamp) 
        VALUES ('student1', 'Professor Jones', '2023-04-16 14:00:00')
    """
    )

    # Insert demo lecture records
    db.execute(
        """
        INSERT INTO lectures (professor, start_time, end_time) 
        VALUES ('Professor Smith', '2023-04-15 09:00:00', '2023-04-15 10:30:00')
    """
    )
    db.execute(
        """
        INSERT INTO lectures (professor, start_time, end_time) 
        VALUES ('Professor Jones', '2023-04-16 14:00:00', '2023-04-16 15:30:00')
    """
    )


professor_name = "NoProf"


# Function to check if user is authenticated
def is_authenticated():
    return "username" in session


# Function to get the current time rounded to the nearest 5 minutes
def get_current_time():
    current_time = datetime.now()
    return round_to_nearest_5min(current_time)


# Function to round the given time to the nearest 5 minutes
def round_to_nearest_5min(t):
    return t.replace(second=0, microsecond=0, minute=(t.minute // 5) * 5) + timedelta(
        minutes=(5 if t.minute % 5 >= 3 else 0)
    )


# Function to combine username, current time, and key
def combine_strings(username, current_time):
    return username + current_time + key


# Function to hash the given string using SHA256
def hash_string(string):
    return sha256(string.encode()).hexdigest()


# Function to encode the username
def encode_username(username, current_time):
    combined_string = combine_strings(username, current_time)
    hashed_value = hash_string(combined_string)
    return hashed_value


def verify_encoded_username(username, provided_encoded_username, current_time):
    encoded_username = encode_username(username, current_time)
    if provided_encoded_username == encoded_username:
        return True
    else:
        return False


# Decode QR code route
@app.route("/decode_qr", methods=["POST"])
def decode_qr():
    picam2 = Picamera2()
    picam2.start()
    time.sleep(2)  # Wait for the camera to warm up

    try:
        # Capture image
        temp_filename = "temp_qr_image.jpg"
        picam2.capture_file(temp_filename)

        # Stop the camera immediately after capturing
        picam2.stop()
        picam2.close()

        # Load and process the captured image
        with Image.open(temp_filename) as image:
            gray = image.convert("L")
            barcodes = pyzbar.decode(gray)

        # Remove the temporary image file
        os.remove(temp_filename)

        if barcodes:
            for barcode in barcodes:
                barcode_data = barcode.data.decode("utf-8")
                extracted_username, extracted_hash = barcode_data.split(",")
                my_time = get_current_time().strftime("%Y-%m-%d %H:%M:%S")
                if verify_encoded_username(extracted_username, extracted_hash, my_time):
                    # Log attendance
                    db.execute(
                        "INSERT INTO attendance (username, professor, timestamp) VALUES (:username, :professor, :timestamp)",
                        username=extracted_username,
                        professor=professor_name,
                        timestamp=datetime.now(),
                    )
                    session["username"] = extracted_username
                    return redirect(url_for("student_portal", message=f"Attendance marked for lecture by {professor_name}"))
                else:
                    return redirect(url_for("student_portal", error="QR code does not match any stored user data."))
        else:
            return redirect(url_for("student_portal", error="No QR code found."))
    except Exception as e:
        return redirect(url_for("student_portal", error=f"An error occurred: {str(e)}"))


@app.route("/prof_start", methods=["GET", "POST"])
def prof_start():
    if not is_authenticated() or session["username"] != "prof":
        return redirect(url_for("login"))

    reader = SimpleMFRC522()
    global professor_name
    try:
        print("Please scan your RFID professor card to start the lecture:")
        professor_id, professor_name = reader.read()
        # Log lecture start
        db.execute(
            "INSERT INTO lectures (professor, start_time) VALUES (:professor, :start_time)",
            professor=professor_name,
            start_time=datetime.now(),
        )
        message = f"Lecture started by Professor {professor_name}. Students can now scan their QR codes."
        return render_template("prof_action_result.html", message=message)
    except Exception as e:
        error = f"An error occurred: {str(e)}"
        return render_template("prof_action_result.html", error=error)
    finally:
        GPIO.cleanup()

@app.route("/prof_end", methods=["GET", "POST"])
def prof_end():
    if not is_authenticated() or session["username"] != "prof":
        return redirect(url_for("login"))

    reader = SimpleMFRC522()
    global professor_name
    try:
        print("Please scan your RFID professor card to end the lecture:")
        professor_id, professor_name = reader.read()
        # Log lecture end
        db.execute(
            "UPDATE lectures SET end_time = :end_time WHERE professor = :professor AND end_time IS NULL",
            end_time=datetime.now(),
            professor=professor_name,
        )
        message = f"Lecture ended by Professor {professor_name}."
        return render_template("prof_action_result.html", message=message)
    except Exception as e:
        error = f"An error occurred: {str(e)}"
        return render_template("prof_action_result.html", error=error)
    finally:
        GPIO.cleanup()

# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = db.execute(
            "SELECT * FROM users WHERE username = :username AND password = :password",
            username=username,
            password=password,
        )
        if user:
            session["username"] = username
            if username == "prof":
                return redirect(url_for("prof"))
            else:
                return redirect(url_for("student_portal"))
        else:
            return render_template("login.html", error="Invalid username or password")
    return render_template("login.html")

# Signup route
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user_type = request.form["user_type"]
        
        existing_user = db.execute(
            "SELECT * FROM users WHERE username = :username", username=username
        )
        if existing_user:
            return render_template("signup.html", error="Username already exists")
        
        if user_type == "student":
            db.execute(
                "INSERT INTO users (username, password, user_type) VALUES (:username, :password, :user_type)",
                username=username,
                password=password,
                user_type="student"
            )
            session["username"] = username
            return redirect(url_for("student_portal"))
        elif user_type == "professor":
            session["temp_username"] = username
            session["temp_password"] = password
            return redirect(url_for("prof_signup"))
    
    return render_template("signup.html")

@app.route("/prof_signup", methods=["GET", "POST"])
def prof_signup():
    if "temp_username" not in session or "temp_password" not in session:
        return redirect(url_for("signup"))
    
    if request.method == "POST":
        reader = SimpleMFRC522()
        try:
            print("Please scan your RFID card to write professor data:")
            prof_id = request.form["prof_id"]
            data_to_write = f"{session['temp_username']},{prof_id}"
            reader.write(data_to_write)
            print("Data written successfully. Please scan the card again to verify.")
            
            # Verify the written data
            id, text = reader.read()
            if text.strip() == data_to_write:
                db.execute(
                    "INSERT INTO users (username, password, user_type, prof_id) VALUES (:username, :password, :user_type, :prof_id)",
                    username=session["temp_username"],
                    password=session["temp_password"],
                    user_type="professor",
                    prof_id=prof_id
                )
                session.pop("temp_username")
                session.pop("temp_password")
                session["username"] = session["temp_username"]
                return redirect(url_for("prof"))
            else:
                return render_template("prof_signup.html", error="Verification failed. Please try again.")
        except Exception as e:
            return render_template("prof_signup.html", error=f"An error occurred: {str(e)}")
        finally:
            GPIO.cleanup()
    
    return render_template("prof_signup.html")


# Logout route
@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))


# Generate QR code route
@app.route("/generate_qr")
def generate_qr():
    if not is_authenticated():
        return redirect(url_for("login"))

    username = session["username"]
    current_time = round_to_nearest_5min(datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    encode_data = encode_username(username, current_time)
    img_str = username + "," + encode_data
    return render_template("generate_qr.html", img_str=img_str)


@app.route("/")
def index():
    if is_authenticated():
        if session["username"] == "prof":
            return redirect(url_for("prof"))
        else:
            return redirect(url_for("generate_qr"))
    return redirect(url_for("login"))


# Professor route
@app.route("/prof")
def prof():
    if not is_authenticated() or session["username"] != "prof":
        return redirect(url_for("login"))
    return render_template("prof.html")


# Attendance logs for students
@app.route("/attendance_logs")
def attendance_logs():
    if not is_authenticated():
        return redirect(url_for("login"))

    username = session["username"]
    logs = db.execute(
        "SELECT * FROM attendance WHERE username = :username ORDER BY timestamp DESC",
        username=username,
    )
    return render_template("attendance_logs.html", logs=logs)


# Attendance logs for professors
@app.route("/prof_attendance_logs")
def prof_attendance_logs():
    if not is_authenticated() or session["username"] != "prof":
        return redirect(url_for("login"))

    logs = db.execute("SELECT * FROM attendance ORDER BY timestamp DESC")
    return render_template("prof_attendance_logs.html", logs=logs)


# Lecture logs for professors
@app.route("/lecture_logs")
def lecture_logs():
    if not is_authenticated() or session["username"] != "prof":
        return redirect(url_for("login"))

    logs = db.execute("SELECT * FROM lectures ORDER BY start_time DESC")
    return render_template("lecture_logs.html", logs=logs)

@app.route("/student_portal")
def student_portal():
    if not is_authenticated():
        return redirect(url_for("login"))

    username = session["username"]
    logs = db.execute(
        "SELECT * FROM attendance WHERE username = :username ORDER BY timestamp DESC LIMIT 5",
        username=username,
    )
    
    # Convert timestamp strings to datetime objects
    for log in logs:
        log['timestamp'] = datetime.strptime(log['timestamp'], '%Y-%m-%d %H:%M:%S')
    
    message = request.args.get("message")
    error = request.args.get("error")
    return render_template("student_portal.html", logs=logs, message=message, error=error)
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=80, debug=True)
