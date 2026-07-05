import hashlib
import json
import os
import random
import string
import threading
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
USERS_FILE = DATA_DIR / "users.json"
ENTRIES_FILE = DATA_DIR / "entries.json"
PUBLIC_DIR = BASE_DIR / "public"

SESSIONS = {}


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not USERS_FILE.exists():
        save_json(USERS_FILE, [])
    if not ENTRIES_FILE.exists():
        save_json(ENTRIES_FILE, [])


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, stored_hash: str) -> bool:
    return hash_password(password) == stored_hash


def configure_data_paths(data_dir: Optional[Path] = None) -> None:
    global DATA_DIR, USERS_FILE, ENTRIES_FILE
    DATA_DIR = data_dir or (BASE_DIR / "data")
    USERS_FILE = DATA_DIR / "users.json"
    ENTRIES_FILE = DATA_DIR / "entries.json"
    ensure_data_files()


configure_data_paths()


def get_users() -> list:
    return load_json(USERS_FILE)


def save_users(users: list) -> None:
    save_json(USERS_FILE, users)


def get_entries() -> list:
    return load_json(ENTRIES_FILE)


def save_entries(entries: list) -> None:
    save_json(ENTRIES_FILE, entries)


def register_user(username: str, password: str) -> tuple[bool, str, Optional[dict]]:
    if not username or not password:
        return False, "Username and password are required", None

    users = get_users()
    if any(user["username"] == username for user in users):
        return False, "Username already exists", None

    user = {
        "id": str(random.randint(1000, 999999)),
        "username": username,
        "password": hash_password(password),
    }
    users.append(user)
    save_users(users)
    return True, "User registered successfully", user


def authenticate_user(username: str, password: str) -> Optional[dict]:
    users = get_users()
    user = next((u for u in users if u["username"] == username), None)
    if user and verify_password(password, user["password"]):
        return user
    return None


def create_entry(user_id: str, title: str, content: str) -> dict:
    entries = get_entries()
    new_entry = {
        "id": str(random.randint(100000, 999999)),
        "userId": user_id,
        "title": title,
        "content": content,
        "createdAt": new_entry_timestamp(),
    }
    entries.append(new_entry)
    save_entries(entries)
    return new_entry


def update_entry(entry_id: str, user_id: str, title: str, content: str) -> Optional[dict]:
    entries = get_entries()
    for entry in entries:
        if entry["id"] == entry_id and entry["userId"] == user_id:
            entry["title"] = title
            entry["content"] = content
            entry["updatedAt"] = new_entry_timestamp()
            save_entries(entries)
            return entry
    return None


def delete_entry(entry_id: str, user_id: str) -> bool:
    entries = get_entries()
    filtered = [entry for entry in entries if not (entry["id"] == entry_id and entry["userId"] == user_id)]
    if len(filtered) == len(entries):
        return False
    save_entries(filtered)
    return True


def list_entries(user_id: str) -> list:
    return [entry for entry in get_entries() if entry["userId"] == user_id]


def new_entry_timestamp() -> str:
    return __import__("datetime").datetime.utcnow().isoformat() + "Z"


def make_session() -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=24))


def get_user_from_session(session_id: Optional[str]) -> Optional[dict]:
    if not session_id:
        return None
    user_data = SESSIONS.get(session_id)
    if not user_data:
        return None
    return user_data


class DiaryHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/session":
            user = self._current_user()
            if not user:
                self.send_json({"loggedIn": False})
            else:
                self.send_json({"loggedIn": True, "username": user["username"]})
            return

        if path == "/api/entries":
            user = self._current_user()
            if not user:
                self.send_json({"error": "Please log in first"}, status=HTTPStatus.UNAUTHORIZED)
                return
            self.send_json(list_entries(user["id"]))
            return

        if path in {"/", "/index.html"}:
            self.serve_static("index.html")
            return

        if path.startswith("/public/"):
            self.serve_static(path[len("/public/"):])
            return

        self.send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        payload = self._read_json_body()

        if path == "/api/register":
            username = (payload or {}).get("username", "")
            password = (payload or {}).get("password", "")
            ok, message, user = register_user(username, password)
            if ok:
                self.send_json({"message": message}, status=HTTPStatus.CREATED)
            else:
                self.send_json({"error": message}, status=HTTPStatus.BAD_REQUEST)
            return

        if path == "/api/login":
            username = (payload or {}).get("username", "")
            password = (payload or {}).get("password", "")
            user = authenticate_user(username, password)
            if not user:
                self.send_json({"error": "Invalid credentials"}, status=HTTPStatus.UNAUTHORIZED)
                return

            session_id = make_session()
            SESSIONS[session_id] = user
            self.send_response(HTTPStatus.OK)
            self.send_header("Set-Cookie", f"session_id={session_id}; HttpOnly; Path=/")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Login successful", "username": user["username"]}).encode("utf-8"))
            return

        if path == "/api/logout":
            session_id = self._session_id_from_cookie()
            if session_id:
                SESSIONS.pop(session_id, None)
            self.send_json({"message": "Logout successful"})
            return

        if path == "/api/entries":
            user = self._current_user()
            if not user:
                self.send_json({"error": "Please log in first"}, status=HTTPStatus.UNAUTHORIZED)
                return
            title = (payload or {}).get("title", "")
            content = (payload or {}).get("content", "")
            if not title or not content:
                self.send_json({"error": "Title and content are required"}, status=HTTPStatus.BAD_REQUEST)
                return
            entry = create_entry(user["id"], title, content)
            self.send_json(entry, status=HTTPStatus.CREATED)
            return

        self.send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_PUT(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        parts = parsed.path.split("/")
        if len(parts) >= 4 and parts[1] == "api" and parts[2] == "entries":
            user = self._current_user()
            if not user:
                self.send_json({"error": "Please log in first"}, status=HTTPStatus.UNAUTHORIZED)
                return
            payload = self._read_json_body()
            entry_id = parts[3]
            entry = update_entry(entry_id, user["id"], (payload or {}).get("title", ""), (payload or {}).get("content", ""))
            if not entry:
                self.send_json({"error": "Entry not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self.send_json(entry)
            return
        self.send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        parts = parsed.path.split("/")
        if len(parts) >= 4 and parts[1] == "api" and parts[2] == "entries":
            user = self._current_user()
            if not user:
                self.send_json({"error": "Please log in first"}, status=HTTPStatus.UNAUTHORIZED)
                return
            entry_id = parts[3]
            deleted = delete_entry(entry_id, user["id"])
            if not deleted:
                self.send_json({"error": "Entry not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self.send_json({"message": "Entry deleted successfully"})
            return
        self.send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args) -> None:
        return

    def _read_json_body(self) -> Optional[dict]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(body) if body else {}
        except json.JSONDecodeError:
            return {}

    def _session_id_from_cookie(self) -> Optional[str]:
        cookie_header = self.headers.get("Cookie", "")
        for item in cookie_header.split(";"):
            if item.strip().startswith("session_id="):
                return item.split("=", 1)[1].strip()
        return None

    def _current_user(self) -> Optional[dict]:
        session_id = self._session_id_from_cookie()
        return get_user_from_session(session_id)

    def send_json(self, payload, status: HTTPStatus = HTTPStatus.OK) -> None:
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def serve_static(self, filename: str) -> None:
        file_path = PUBLIC_DIR / filename
        if not file_path.exists() or not file_path.is_file():
            self.send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return
        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", self._mime_type(file_path))
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    @staticmethod
    def _mime_type(path: Path) -> str:
        if path.suffix == ".html":
            return "text/html; charset=utf-8"
        if path.suffix == ".css":
            return "text/css"
        if path.suffix == ".js":
            return "application/javascript"
        return "application/octet-stream"


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    ensure_data_files()
    server = ThreadingHTTPServer((host, port), DiaryHandler)
    print(f"Diary app running on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
