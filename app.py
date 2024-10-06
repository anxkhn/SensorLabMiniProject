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
    time.sleep(2)
    picam2.start()
    time.sleep(2)  # Wait for the camera to warm up

    try:
        # Capture image
        temp_filename = "temp_qr_image.jpg"
        picam2.capture_file(temp_filename)

        # Load the captured image
        image = Image.open(temp_filename)

        # Convert the image to grayscale
        gray = image.convert("L")

        # Find QR codes in the image
        barcodes = pyzbar.decode(gray)

        # Check if barcodes are found
        if barcodes:
            # Loop over the detected barcodes
            for barcode in barcodes:
                # Extract barcode data
                barcode_data = barcode.data.decode("utf-8")
                extracted_username, extracted_hash = barcode_data.split(",")
                my_time = get_current_time().strftime("%Y-%m-%d %H:%M:%S")
                if verify_encoded_username(extracted_username, extracted_hash, my_time):
                    # Log attendance
                    db.execute(
                        "INSERT INTO attendance (username, professor, timestamp) VALUES (:username, :professor, :timestamp)",
                        username=extracted_username,
                        professor=professor_name,
                        timestamp=datetime.now()
                    )
                    return jsonify({"message": f"Attendance marked for {extracted_username}, Lecture by {professor_name}"})
                else:
                    return jsonify({"message": "QR code does not match any stored user data."})
        else:
            return jsonify({"message": "No QR code found."})
    finally:
        # Stop the camera and remove the temporary image file
        picam2.stop()
        picam2.close()
        os.remove(temp_filename)  # Remove the temporary image file

@app.route("/prof_start", methods=["GET", "POST"])
def prof_start():
    reader = SimpleMFRC522()
    global professor_name
    print("Please scan your RFID professor card to start the lecture:")
    professor_id, professor_name = reader.read()
    GPIO.cleanup()
    # Log lecture start
    db.execute(
        "INSERT INTO lectures (professor, start_time) VALUES (:professor, :start_time)",
        professor=professor_name,
        start_time=datetime.now()
    )
    return jsonify({"message": f"Lecture started by Professor {professor_name}. Students can now scan their QR codes."})

@app.route("/prof_end", methods=["GET", "POST"])
def prof_end():
    reader = SimpleMFRC522()
    global professor_name
    print("Please scan your RFID professor card to end the lecture:")
    professor_id, professor_name = reader.read()
    GPIO.cleanup()
    # Log lecture end
    db.execute(
        "UPDATE lectures SET end_time = :end_time WHERE professor = :professor AND end_time IS NULL",
        end_time=datetime.now(),
        professor=professor_name
    )
    return jsonify({"message": f"Lecture ended by Professor {professor_name}."})

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
                return redirect(url_for("generate_qr"))
        else:
            return render_template("login.html", error="Invalid username or password")
    return render_template("login.html")

# Signup route
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        existing_user = db.execute(
            "SELECT * FROM users WHERE username = :username", username=username
        )
        if existing_user:
            return render_template("signup.html", error="Username already exists")
        else:
            db.execute(
                "INSERT INTO users (username, password) VALUES (:username, :password)",
                username=username,
                password=password,
            )
            session["username"] = username
            return redirect(url_for("generate_qr"))
    return render_template("signup.html")

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
    logs = db.execute("SELECT * FROM attendance WHERE username = :username ORDER BY timestamp DESC", username=username)
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)