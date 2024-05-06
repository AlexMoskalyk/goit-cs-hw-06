import mimetypes
import json
import socket
import logging
from pathlib import Path
from urllib.parse import urlparse, unquote_plus, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
from multiprocessing import Process
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime

HTTP_PORT = 8000
SOCKET_PORT = 8001
HTTP_HOST = "0.0.0.0"
SOCKET_HOST = "0.0.0.0"

URI_DB = "mongodb://mongodb:27017"
BASE_DIR = Path(__file__).parent

from jinja2 import Environment, FileSystemLoader
jinja_env = Environment(loader=FileSystemLoader(BASE_DIR / 'templates'))

class SimpleWebServer(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/':
            self.send_html('index.html')
        elif path == '/message':
            self.send_html('message.html')
        else:
            self.send_static(path)

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        self.handle_post_data(post_data.decode())
        self.send_response(302)
        self.send_header('Location', '/')
        self.end_headers()

    def send_html(self, filename, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        file_path = BASE_DIR / filename
        if file_path.exists():
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, 'File not found')

    def send_static(self, path, status=200):
        filepath = BASE_DIR / path.lstrip('/')
        if filepath.exists():
            self.send_response(status)
            mimetype, _ = mimetypes.guess_type(filepath)
            self.send_header('Content-type', mimetype or 'application/octet-stream')
            self.end_headers()
            with open(filepath, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, 'File not found')

    def handle_post_data(self, data):
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client_socket.sendto(data.encode(), (SOCKET_HOST, SOCKET_PORT))
            client_socket.close()
        except socket.error as e:
            logging.error("Failed to send data: " + str(e))

def run_http_server():
    server = HTTPServer((HTTP_HOST, HTTP_PORT), SimpleWebServer)
    logging.info(f'Starting HTTP Server on {HTTP_HOST}:{HTTP_PORT}')
    server.serve_forever()

def run_socket_server():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
        server_socket.bind((SOCKET_HOST, SOCKET_PORT))
        logging.info(f"Socket Server Listening on {SOCKET_HOST}:{SOCKET_PORT}")
        while True:
            data, addr = server_socket.recvfrom(1024)
            logging.info(f"Received from {addr}: {data.decode()}")
            save_to_db(data.decode())

def save_to_db(data):
    client = MongoClient(URI_DB)
    db = client.homework
    data_dict = parse_qs(data)
    data_dict = {k: v[0] for k, v in data_dict.items()}
    data_dict['date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    db.messages.insert_one(data_dict)
    logging.info(f"Data saved to MongoDB: {data_dict}")
    client.close()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    process_http = Process(target=run_http_server)
    process_socket = Process(target=run_socket_server)
    process_http.start()
    process_socket.start()
    process_http.join()
    process_socket.join()
