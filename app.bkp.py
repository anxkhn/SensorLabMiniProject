from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime, timedelta
from hashlib import sha256
from flask_qrcode import QRcode
from cs50 import SQL

app = Flask(__name__)
app.secret_key = "your_secret_key"
QRcode(app)
key = "example_key"

# Database initialization
db = SQL("sqlite:///users.db")


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
def combine_strings(username, current_time, key):
    return username + current_time + key


# Function to hash the given string using SHA256
def hash_string(string):
    return sha256(string.encode()).hexdigest()


# Function to encode the username
def encode_username(username, current_time, key):
    combined_string = combine_strings(username, current_time, key)
    hashed_value = hash_string(combined_string)
    return hashed_value


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
    encode_data = encode_username(username, current_time, key)
    img_str = username + "," + encode_data
    return render_template("generate_qr.html", img_str=img_str)


# Main route
@app.route("/")
def index():
    if not is_authenticated():
        return redirect(url_for("login"))
    return redirect(url_for("generate_qr"))


if __name__ == "__main__":
    app.run(debug=True)
