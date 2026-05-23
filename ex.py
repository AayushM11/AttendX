# from fastapi import FastAPI
# import requests

# app = FastAPI()
# items = [
#     {"id": 1, "name":"Laptop"},
#     {"id": 2, "name": "Phone"},
# ]

# @app.get("/")
# def root ():
#     return {"message": "welcome"}

# @app.get("/items")
# def get_items():
#     return {"items": items}

# @app.post("/items")
# def create_items(item: dict):
#     items.append(item)
#     return {"message:": "Item added","item":item}


from http.server import BaseHTTPRequestHandler, HTTPServer
import json

items = [
    {"id": 1, "name": "Laptop"},
    {"id": 2, "name": "Phone"},
]

class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        response = {"items": items}
        self.wfile.write(json.dumps(response).encode())

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length"))
        post_data = self.rfile.read(content_length).decode()
        new_item = json.loads(post_data)

        new_id = len(items) + 1 
        new_item["id"] = new_id
        items.append(new_item)

        self.send_response(201)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"message": "Item added", "item": new_item}).encode())

if __name__ == "__main__":
    server = HTTPServer(('localhost', 8000), APIHandler)
    print("Server running on http://localhost:8000")
    server.serve_forever()