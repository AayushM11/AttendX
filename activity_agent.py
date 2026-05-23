import argparse
import platform
import sys
import threading
import time
from datetime import datetime

import psutil
import requests
from pynput import keyboard, mouse

# python activity_agent.py --server http://192.168.29.20:8000 --employee EMP0001 


#  Detect OS first — import Mac libs ONLY on Mac 
OS = platform.system()   # "Windows" or "Darwin"

if OS == "Darwin":
    try:
        from AppKit import NSWorkspace
        _MAC_APPKIT_OK = True
    except ImportError:
        _MAC_APPKIT_OK = False
        print("[Agent] Warning: pyobjc not installed. Run: pip3 install pyobjc-framework-AppKit")
else:
    _MAC_APPKIT_OK = False

#  Config 
HEARTBEAT_INTERVAL = 30
IDLE_THRESHOLD     = 120
AGENT_VERSION      = "1.0.1"

#  State (thread-safe via lock) 
_lock              = threading.Lock()
_last_input_time   = time.time()
_mouse_moves       = 0
_key_presses       = 0
_app_times: dict   = {}
_current_app       = None
_current_app_start = time.time()
_session_start     = datetime.now()
_server_url        = ""
_employee_id       = ""


def get_active_window_name() -> str:
    try:
        if OS == "Windows":
            import ctypes
            import ctypes.wintypes as wt
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            pid  = ctypes.wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            try:
                proc = psutil.Process(pid.value)
                return proc.name().replace(".exe", "")
            except Exception:
                buf = ctypes.create_unicode_buffer(256)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
                return buf.value or "Unknown"
        elif OS == "Darwin" and _MAC_APPKIT_OK:
            app = NSWorkspace.sharedWorkspace().activeApplication()
            return app.get("NSApplicationName", "Unknown") if app else "Unknown"
    except Exception:
        pass
    return "Unknown"


def _on_move(x, y):
    global _last_input_time, _mouse_moves
    with _lock:
        _last_input_time = time.time()
        _mouse_moves += 1


def _on_click(x, y, button, pressed):
    global _last_input_time
    if pressed:
        with _lock:
            _last_input_time = time.time()


def _on_key_press(key):
    global _last_input_time, _key_presses
    with _lock:
        _last_input_time = time.time()
        _key_presses += 1


def _app_tracker_loop():
    global _current_app, _current_app_start
    while True:
        try:
            win = get_active_window_name()
            now = time.time()
            with _lock:
                if win != _current_app:
                    if _current_app:
                        elapsed = now - _current_app_start
                        _app_times[_current_app] = _app_times.get(_current_app, 0) + elapsed
                    _current_app       = win
                    _current_app_start = now
        except Exception:
            pass
        time.sleep(2)


def _send_heartbeat():
    global _mouse_moves, _key_presses, _app_times, _current_app_start
    with _lock:
        now       = time.time()
        idle_secs = now - _last_input_time
        is_idle   = idle_secs >= IDLE_THRESHOLD
        snapshot_apps = dict(_app_times)
        if _current_app:
            elapsed = now - _current_app_start
            snapshot_apps[_current_app] = snapshot_apps.get(_current_app, 0) + elapsed
            _current_app_start = now
        payload = {
            "employee_id":   _employee_id,
            "timestamp":     datetime.now().isoformat(),
            "is_idle":       is_idle,
            "idle_seconds":  round(idle_secs, 1),
            "mouse_moves":   _mouse_moves,
            "key_presses":   _key_presses,
            "app_times":     {k: round(v) for k, v in snapshot_apps.items() if v > 1},
            "active_app":    _current_app or "Unknown",
            "os":            OS,
            "agent_version": AGENT_VERSION,
        }
        _mouse_moves = 0
        _key_presses = 0
        _app_times   = {}

    status = "IDLE" if payload["is_idle"] else "ACTIVE"
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Heartbeat — {status} | App: {payload['active_app']}")
    try:
        res = requests.post(f"{_server_url}/api/activity/heartbeat", json=payload, timeout=10)
        print(f"  {'OK' if res.status_code == 200 else 'ERR ' + str(res.status_code)}")
    except requests.exceptions.ConnectionError:
        print(f"  Cannot reach {_server_url} — will retry")
    except Exception as e:
        print(f"  Error: {e}")


def _heartbeat_loop():
    while True:
        time.sleep(HEARTBEAT_INTERVAL)
        _send_heartbeat()


def _send_eod_summary():
    try:
        requests.post(
            f"{_server_url}/api/activity/session-end",
            json={
                "employee_id":   _employee_id,
                "session_start": _session_start.isoformat(),
                "session_end":   datetime.now().isoformat(),
            },
            timeout=5,
        )
        print("\n[Agent] EOD summary sent.")
    except Exception as e:
        print(f"\n[Agent] Could not send EOD summary: {e}")


def main():
    global _server_url, _employee_id

    parser = argparse.ArgumentParser(description="AttendX Activity Agent")
    parser.add_argument("--server",   required=True)
    parser.add_argument("--employee", required=True)
    args = parser.parse_args()

    _server_url  = args.server.rstrip("/")
    _employee_id = args.employee.strip().upper()

    print("=" * 55)
    print(f"  AttendX Activity Agent v{AGENT_VERSION}")
    print(f"  Employee : {_employee_id}")
    print(f"  Server   : {_server_url}")
    print(f"  OS       : {OS}")
    print("=" * 55 + "\n")

    threading.Thread(target=_app_tracker_loop, daemon=True).start()
    threading.Thread(target=_heartbeat_loop,   daemon=True).start()

    mouse.Listener(on_move=_on_move, on_click=_on_click).start()
    keyboard.Listener(on_press=_on_key_press).start()

    _send_heartbeat()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        _send_eod_summary()
        print("[Agent] Stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()