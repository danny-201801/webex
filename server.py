#!/usr/bin/env python3
import http.server, urllib.request, urllib.parse, os, sys, mimetypes
from pathlib import Path

BACKUP_DIR = Path.home() / "Desktop" / "webex_backup"

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass  # 로그 숨김

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.startswith('/api/'):
            self._proxy()
        elif self.path.startswith('/files/'):
            self._serve_local_file()
        elif self.path == '/local-backup.json':
            self._serve_backup_json()
        else:
            fname = 'index.html' if self.path in ('/', '/index.html') else self.path.lstrip('/')
            try:
                with open(fname, 'rb') as f:
                    data = f.read()
                self.send_response(200)
                ct = 'text/html' if fname.endswith('.html') else 'application/octet-stream'
                self.send_header('Content-Type', ct + '; charset=utf-8')
                self.end_headers()
                self.wfile.write(data)
            except FileNotFoundError:
                self.send_error(404)

    def _serve_backup_json(self):
        backup_file = BACKUP_DIR / "backup.json"
        try:
            with open(backup_file, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self._cors()
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(b'null')

    def _serve_local_file(self):
        # /files/<space_id>/<filename> → ~/Desktop/webex_backup/files/<space_id>/<filename>
        rel = urllib.parse.unquote(self.path[1:])  # "files/..."
        file_path = BACKUP_DIR / rel
        # 경로 탈출 방지
        try:
            file_path.resolve().relative_to((BACKUP_DIR / "files").resolve())
        except ValueError:
            self.send_error(403)
            return
        try:
            size = file_path.stat().st_size
            ct, _ = mimetypes.guess_type(str(file_path))
            fname_encoded = urllib.parse.quote(file_path.name)
            self.send_response(200)
            self.send_header('Content-Type', ct or 'application/octet-stream')
            self.send_header('Content-Length', str(size))
            self.send_header('Content-Disposition', f"inline; filename*=UTF-8''{fname_encoded}")
            self._cors()
            self.end_headers()
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(1024 * 1024)  # 1MB씩 스트리밍
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except FileNotFoundError:
            self.send_error(404)
        except Exception:
            pass  # 브라우저가 연결을 끊은 경우 등 무시

    def _proxy(self):
        path = self.path[5:]  # /api/ 제거
        url = 'https://webexapis.com/v1/' + path
        auth = self.headers.get('Authorization', '')
        req = urllib.request.Request(url, headers={'Authorization': auth, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(data)
        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_error(500, str(e))

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')

class ReuseHTTPServer(http.server.HTTPServer):
    allow_reuse_address = True

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    port = 1985
    print(f'✅ 서버 시작: http://localhost:{port}')
    print('종료하려면 Ctrl+C')
    ReuseHTTPServer(('localhost', port), Handler).serve_forever()
