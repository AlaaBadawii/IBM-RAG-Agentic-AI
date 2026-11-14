import socket

from app.config import PORT


def test_port(port=PORT):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            print(f"Port {PORT} is not avilaible")
        except OSError:
            print(f"Port {PORT} is avilaible")