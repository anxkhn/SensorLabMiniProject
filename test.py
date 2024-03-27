import hashlib
from datetime import datetime, timedelta


def get_current_time():
    """Returns the current time rounded to the nearest 5 minutes."""
    current_time = datetime.now()
    return round_to_nearest_5min(current_time)


def round_to_nearest_5min(t):
    """Rounds the given time to the nearest 5 minutes."""
    return t.replace(second=0, microsecond=0, minute=(t.minute // 5) * 5) + timedelta(
        minutes=(5 if t.minute % 5 >= 3 else 0)
    )


def combine_strings(username, current_time, key):
    """Combines username, current time, and key."""
    return username + current_time + key


def hash_string(string):
    """Hashes the given string using SHA256."""
    return hashlib.sha256(string.encode()).hexdigest()


def encode_username(current_time, key):
    """Encodes the username."""
    username = input("Enter username: ")
    combined_string = combine_strings(username, current_time, key)
    hashed_value = hash_string(combined_string)
    return hashed_value


def verify_encoded_username(current_time, key):
    """Verifies if the provided encoded username matches the calculated one."""
    provided_encoded_username = input("Enter the provided encoded username: ")
    encoded_username = encode_username(current_time, key)
    if provided_encoded_username == encoded_username:
        return True
    else:
        return False


if __name__ == "__main__":
    key = "example_key"
    current_time = get_current_time().strftime("%Y-%m-%d %H:%M:%S")

    encoded = encode_username(current_time, key)
    print("Encoded:", encoded)

    # Verify if the provided encoded username matches the calculated one
    if verify_encoded_username(current_time, key):
        print("Hash is correct.")
    else:
        print("Hash is incorrect.")
