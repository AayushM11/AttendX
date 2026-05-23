import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import socket
import uvicorn

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

local_ip = get_local_ip()

print("\n" + "="*55)
print("  AttendX Server Starting...")
print("="*55)
print(f"\n  Local:    http://127.0.0.1:8000")
print(f"  Network:  http://{local_ip}:8000")
print(f"\n  Use this in your Flutter app:")
print(f"  http://{local_ip}:8000")
print("\n  Press CTRL+C to stop")
print("="*55 + "\n")

uvicorn.run(
    "main:app",
    host="0.0.0.0",
    port=8000,
    reload=False,
    log_level="info"
)
