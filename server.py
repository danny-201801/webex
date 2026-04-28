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
            with open(file_path, 'rb') as f:
                data = f.read()
            ct, _ = mimetypes.guess_type(str(file_path))
            self.send_response(200)
            self.send_header('Content-Type', ct or 'application/octet-stream')
            self.send_header('Content-Disposition', f'inline; filename="{file_path.name}"')
            self._cors()
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_error(404)

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

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    port = 8080
    print(f'✅ 서버 시작: http://localhost:{port}')
    print('종료하려면 Ctrl+C')
    http.server.HTTPServer(('localhost', port), Handler).serve_forever()
