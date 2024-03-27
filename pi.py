import io
import picamera
import zbarlight
from PIL import Image


def capture_qr_code():
    with picamera.PiCamera() as camera:
        # Set camera resolution as desired
        camera.resolution = (640, 480)

        # Capture an image
        stream = io.BytesIO()
        camera.capture(stream, format="jpeg")
        stream.seek(0)

        # Decode QR code
        image = Image.open(stream)
        image_data = image.convert("L").tobytes()
        codes = zbarlight.scan_codes(["qrcode"], image)

        # If QR code is detected, return the data
        if codes:
            return codes[0].decode("utf-8")
        else:
            return None


if __name__ == "__main__":
    while True:
        qr_data = capture_qr_code()
        if qr_data:
            print("QR Code Detected:", qr_data)
        else:
            print("No QR Code Detected")
