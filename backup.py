#!/usr/bin/env python3
"""
Webex 대화 백업 - 핵심 로직
백업 위치: ~/Desktop/webex_backup/backup.json
"""
import json, os, sys, time, hashlib, base64, secrets, webbrowser
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

# ── OAuth 설정 (Integration 등록 후 채워넣기) ──────────────────────
CLIENT_ID     = "Cd4487bf7672af986eba5ea41653f415b2f7addc435d5b5f944cb65a9084484eb"
CLIENT_SECRET = "d41e3d7db6acefe75b9ee5c73c29d3fc2bc50fff9f9d4e8e2ac685b0e7971916"
REDIRECT_URI  = "http://localhost:8765/callback"
AUTH_URL      = "https://webexapis.com/v1/authorize"
TOKEN_URL     = "https://webexapis.com/v1/access_token"
API_BASE      = "https://webexapis.com/v1"

# ── 경로 ──────────────────────────────────────────────────────────
DESKTOP     = Path.home() / "Desktop"
BACKUP_DIR  = DESKTOP / "webex_backup"
CREDS_FILE  = BACKUP_DIR / ".credentials.json"
BACKUP_FILE = BACKUP_DIR / "backup.json"
LOG_FILE    = BACKUP_DIR / "backup.log"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass

# ── PKCE ──────────────────────────────────────────────────────────
def gen_pkce():
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge

# ── OAuth 로컬 콜백 서버 ──────────────────────────────────────────
_auth_code = None

class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        params = parse_qs(urlparse(self.path).query)
        _auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("""
        <html><body style="font-family:sans-serif;text-align:center;padding:60px;background:#0f1117;color:#e1e4e8">
        <h2 style="color:#3fb950">✅ 인증 완료!</h2>
        <p>이 창을 닫고 터미널로 돌아가세요.</p>
        </body></html>""".encode())
    def log_message(self, *a): pass

def do_oauth():
    global _auth_code
    _auth_code = None
    verifier, challenge = gen_pkce()

    params = urlencode({
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "spark:all",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": secrets.token_hex(8),
    })
    log("🌐 브라우저에서 Webex 로그인을 완료해주세요...")
    webbrowser.open(f"{AUTH_URL}?{params}")

    server = HTTPServer(("localhost", 8765), _CallbackHandler)
    server.timeout = 180
    server.handle_request()

    if not _auth_code:
        log("❌ 인증 실패 - 3분 내에 로그인하지 않았습니다.")
        sys.exit(1)

    data = urlencode({
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": _auth_code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    }).encode()
    req = Request(TOKEN_URL, data=data,
                  headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(req) as resp:
        tokens = json.loads(resp.read())

    _save_creds(tokens)
    log("✅ 인증 완료 - 토큰 저장됨")
    return tokens["access_token"]

def _save_creds(tokens):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    creds = {
        "access_token":  tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "expires_at":    time.time() + tokens.get("expires_in", 43200) - 300,
    }
    with open(CREDS_FILE, "w") as f:
        json.dump(creds, f)

def load_token():
    if not CREDS_FILE.exists():
        return do_oauth()
    with open(CREDS_FILE) as f:
        creds = json.load(f)
    if time.time() < creds.get("expires_at", 0):
        return creds["access_token"]
    refresh = creds.get("refresh_token")
    if not refresh:
        return do_oauth()
    try:
        data = urlencode({
            "grant_type":    "refresh_token",
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": refresh,
        }).encode()
        req = Request(TOKEN_URL, data=data,
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urlopen(req) as resp:
            tokens = json.loads(resp.read())
        _save_creds(tokens)
        log("🔄 토큰 자동 갱신 완료")
        return tokens["access_token"]
    except Exception as e:
        log(f"⚠️  토큰 갱신 실패 ({e}), 재로그인...")
        return do_oauth()

# ── Webex API ─────────────────────────────────────────────────────
def api_get(token, endpoint, params={}):
    qs = urlencode(params)
    url = f"{API_BASE}/{endpoint}{'?' + qs if qs else ''}"
    while True:
        req = Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except HTTPError as e:
            if e.code == 429:
                wait = int(e.headers.get("Retry-After", "5"))
                log(f"  ⏳ Rate limit, {wait}초 대기...")
                time.sleep(wait)
            else:
                raise

def get_all_messages(token, room_id, since=None):
    msgs, params, page = [], {"roomId": room_id, "max": 500}, 1
    while len(msgs) < 10000:
        data = api_get(token, "messages", params)
        items = data.get("items", [])
        if not items:
            break
        if since:
            new_items = [m for m in items if m.get("created", "") > since]
            msgs.extend(new_items)
            if len(new_items) < len(items):
                break
        else:
            msgs.extend(items)
        if len(items) < 500:
            break
        params["beforeMessage"] = items[-1]["id"]
        page += 1
    return sorted(msgs, key=lambda m: m.get("created", ""))

# ── 메인 백업 ─────────────────────────────────────────────────────
def run_backup():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    log("=" * 50)
    log("🚀 Webex 백업 시작")

    token = load_token()
    me = api_get(token, "people/me")
    my_id, my_name = me["id"], me.get("displayName", "")
    log(f"👤 {my_name} ({me.get('emails', [''])[0]})")

    # 기존 백업 로드
    backup = None
    if BACKUP_FILE.exists():
        with open(BACKUP_FILE, encoding="utf-8") as f:
            backup = json.load(f)
        log(f"📂 기존 백업: {len(backup.get('spaces', []))}개 스페이스")

    if not backup:
        backup = {
            "version": 2,
            "me": {"id": my_id, "displayName": my_name},
            "people": {my_id: my_name},
            "spaces": [],
            "lastBackup": None,
        }

    last_backup   = backup.get("lastBackup")
    spaces_map    = {s["id"]: s for s in backup.get("spaces", [])}

    # 스페이스 목록
    log("📋 스페이스 목록 조회 중...")
    data       = api_get(token, "rooms", {"max": 1000, "sortBy": "lastactivity"})
    all_spaces = data.get("items", [])
    log(f"  → {len(all_spaces)}개 스페이스")

    new_msg_total = 0
    for i, space in enumerate(all_spaces):
        sid          = space["id"]
        title        = space.get("title", "Untitled")
        last_activity = space.get("lastActivity", "")

        # 변경 없으면 스킵
        if last_backup and last_activity and last_activity <= last_backup and sid in spaces_map:
            continue

        try:
            since = None
            if sid in spaces_map and spaces_map[sid].get("messages"):
                msgs = spaces_map[sid]["messages"]
                if msgs:
                    since = max(m.get("created", "") for m in msgs)

            new_msgs = get_all_messages(token, sid, since)

            if sid in spaces_map:
                if new_msgs:
                    existing_ids = {m["id"] for m in spaces_map[sid]["messages"]}
                    added = [m for m in new_msgs if m["id"] not in existing_ids]
                    spaces_map[sid]["messages"].extend(added)
                    spaces_map[sid]["messages"].sort(key=lambda m: m.get("created", ""))
                    new_msg_total += len(added)
                    log(f"  [{i+1}/{len(all_spaces)}] 📥 {title} (+{len(added)})")
                spaces_map[sid].update({
                    "title": title, "type": space.get("type"), "lastActivity": last_activity
                })
            else:
                spaces_map[sid] = {
                    "id": sid, "title": title,
                    "type": space.get("type"), "lastActivity": last_activity,
                    "messages": new_msgs,
                }
                new_msg_total += len(new_msgs)
                log(f"  [{i+1}/{len(all_spaces)}] 🆕 {title} ({len(new_msgs)}개)")

        except Exception as e:
            log(f"  [{i+1}/{len(all_spaces)}] ❌ {title}: {e}")

    # 저장
    backup["spaces"]     = list(spaces_map.values())
    backup["lastBackup"] = datetime.now(timezone.utc).isoformat()
    backup["me"]         = {"id": my_id, "displayName": my_name}

    tmp = BACKUP_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False)
    tmp.replace(BACKUP_FILE)

    total_msgs = sum(len(s.get("messages", [])) for s in backup["spaces"])
    size_mb    = BACKUP_FILE.stat().st_size / 1024 / 1024
    log(f"✅ 백업 완료! 스페이스 {len(backup['spaces'])}개 | 메시지 {total_msgs:,}개 | {size_mb:.1f}MB")
    log(f"   저장 위치: {BACKUP_FILE}")

if __name__ == "__main__":
    run_backup()
