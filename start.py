#!/usr/bin/env python3
"""
webex_backup_시작 - 첫 실행 or 일배치 실행
  인자 없이 실행: OAuth 인증 + 전체 백업 + 일배치/서버 스케줄 등록
  --cron 인자: 스케줄러에 의한 자동 실행 (백업만)
"""
import sys, os, subprocess
from pathlib import Path
import backup  # PyInstaller가 같이 번들링

IS_FROZEN = getattr(sys, "frozen", False)
EXE_PATH  = Path(sys.executable if IS_FROZEN else __file__).resolve()

# webex_server 실행파일은 같은 폴더에 있다고 가정
SERVER_EXE = EXE_PATH.parent / ("webex_server.exe" if sys.platform == "win32" else "webex_server")
SERVER_LOG = backup.BACKUP_DIR / "server.log"

def setup_mac():
    # ── 백업 일배치 ──
    backup_plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key>              <string>com.webex.backup</string>
  <key>ProgramArguments</key>
  <array>
    <string>{EXE_PATH}</string>
    <string>--cron</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>    <integer>12</integer>
    <key>Minute</key>  <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>  <string>{backup.LOG_FILE}</string>
  <key>StandardErrorPath</key> <string>{backup.LOG_FILE}</string>
  <key>RunAtLoad</key> <false/>
</dict></plist>"""

    plist_path = Path.home() / "Library/LaunchAgents/com.webex.backup.plist"
    plist_path.parent.mkdir(exist_ok=True)
    plist_path.write_text(backup_plist)
    os.system(f'launchctl unload "{plist_path}" 2>/dev/null')
    os.system(f'launchctl load "{plist_path}"')
    print(f"✅ Mac 일배치 등록 완료 (매일 낮 12시)")

    # ── 웹 뷰어 서버 (부팅 시 자동 시작) ──
    if SERVER_EXE.exists():
        server_plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key>              <string>com.webex.server</string>
  <key>ProgramArguments</key>
  <array>
    <string>{SERVER_EXE}</string>
  </array>
  <key>RunAtLoad</key>  <true/>
  <key>KeepAlive</key>  <true/>
  <key>StandardOutPath</key>  <string>{SERVER_LOG}</string>
  <key>StandardErrorPath</key> <string>{SERVER_LOG}</string>
</dict></plist>"""

        server_plist_path = Path.home() / "Library/LaunchAgents/com.webex.server.plist"
        server_plist_path.write_text(server_plist)
        os.system(f'launchctl unload "{server_plist_path}" 2>/dev/null')
        os.system(f'launchctl load "{server_plist_path}"')
        print(f"✅ 웹 뷰어 서버 자동 시작 등록 완료 (부팅 시 http://localhost:1985)")
        print(f"   중지하려면 webex_backup_stop 실행 (포트 1985 해제됨)")
    else:
        print(f"⚠️  webex_server 파일이 없어 서버 자동 시작을 건너뜁니다")
        print(f"   webex_server와 webex_backup_start를 같은 폴더에 두세요")

def setup_windows():
    exe = str(EXE_PATH)
    os.system('schtasks /delete /tn "WebexBackup" /f 2>nul')
    ret = os.system(
        f'schtasks /create /tn "WebexBackup" /tr "{exe} --cron" '
        f'/sc daily /st 12:00 /f /rl HIGHEST'
    )
    if ret == 0:
        print("✅ Windows 일배치 등록 완료 (매일 낮 12시)")
    else:
        print("❌ 작업 스케줄러 등록 실패 - 관리자 권한으로 다시 실행해보세요")

    # ── 웹 뷰어 서버 (로그온 시 자동 시작) ──
    if SERVER_EXE.exists():
        server_exe = str(SERVER_EXE)
        os.system('schtasks /delete /tn "WebexServer" /f 2>nul')
        ret2 = os.system(
            f'schtasks /create /tn "WebexServer" /tr "{server_exe}" '
            f'/sc onlogon /f /rl HIGHEST'
        )
        # 지금 바로 시작
        os.system('schtasks /run /tn "WebexServer"')
        if ret2 == 0:
            print("✅ Windows 웹 뷰어 서버 자동 시작 등록 완료 (로그온 시 http://localhost:1985)")
            print("   중지하려면 webex_backup_stop 실행 (포트 1985 해제됨)")
    else:
        print(f"⚠️  webex_server.exe 파일이 없어 서버 자동 시작을 건너뜁니다")

def first_run():
    print("=" * 50)
    print("  Webex 백업 - 최초 설정")
    print("=" * 50)
    print()
    print("📥 전체 백업을 시작합니다 (처음엔 시간이 걸립니다)...")
    print()
    backup.run_backup()
    print()
    print("⏰ 자동 실행을 설정합니다...")
    if sys.platform == "darwin":
        setup_mac()
    elif sys.platform == "win32":
        setup_windows()
    else:
        print("⚠️  Linux는 crontab을 직접 등록해주세요:")
        print(f"   0 12 * * * {EXE_PATH} --cron")
    print()
    print("🎉 설정 완료!")
    print(f"   백업 파일: {backup.BACKUP_FILE}")
    print(f"   로그 파일: {backup.LOG_FILE}")
    print(f"   웹 뷰어:   http://localhost:1985")
    print()
    input("Enter를 눌러 종료...")

if __name__ == "__main__":
    if "--cron" in sys.argv:
        backup.run_backup()
    else:
        first_run()
