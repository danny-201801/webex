#!/usr/bin/env python3
"""
webex_backup_시작 - 첫 실행 or 일배치 실행
  인자 없이 실행: OAuth 인증 + 전체 백업 + 일배치 스케줄 등록
  --cron 인자: 스케줄러에 의한 자동 실행 (백업만)
"""
import sys, os, subprocess
from pathlib import Path
import backup  # PyInstaller가 같이 번들링

IS_FROZEN = getattr(sys, "frozen", False)
EXE_PATH  = Path(sys.executable if IS_FROZEN else __file__).resolve()

def setup_mac():
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
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
    <key>Hour</key>    <integer>3</integer>
    <key>Minute</key>  <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>{backup.LOG_FILE}</string>
  <key>StandardErrorPath</key>
  <string>{backup.LOG_FILE}</string>
  <key>RunAtLoad</key> <false/>
</dict></plist>"""

    plist_path = Path.home() / "Library/LaunchAgents/com.webex.backup.plist"
    plist_path.parent.mkdir(exist_ok=True)
    plist_path.write_text(plist)
    os.system(f'launchctl unload "{plist_path}" 2>/dev/null')
    os.system(f'launchctl load "{plist_path}"')
    print(f"✅ Mac 일배치 등록 완료 (매일 오전 3시)")
    print(f"   실행 파일: {EXE_PATH}")

def setup_windows():
    exe = str(EXE_PATH)
    os.system('schtasks /delete /tn "WebexBackup" /f 2>nul')
    ret = os.system(
        f'schtasks /create /tn "WebexBackup" /tr "{exe} --cron" '
        f'/sc daily /st 03:00 /f /rl HIGHEST'
    )
    if ret == 0:
        print("✅ Windows 일배치 등록 완료 (매일 오전 3시)")
    else:
        print("❌ 작업 스케줄러 등록 실패 - 관리자 권한으로 다시 실행해보세요")

def first_run():
    print("=" * 50)
    print("  Webex 백업 - 최초 설정")
    print("=" * 50)
    print()
    print("📥 전체 백업을 시작합니다 (처음엔 시간이 걸립니다)...")
    print()
    backup.run_backup()
    print()
    print("⏰ 일배치 자동 실행을 설정합니다...")
    if sys.platform == "darwin":
        setup_mac()
    elif sys.platform == "win32":
        setup_windows()
    else:
        print("⚠️  Linux는 crontab을 직접 등록해주세요:")
        print(f"   0 3 * * * {EXE_PATH} --cron")
    print()
    print("🎉 설정 완료!")
    print(f"   백업 파일: {backup.BACKUP_FILE}")
    print(f"   로그 파일: {backup.LOG_FILE}")
    print()
    input("Enter를 눌러 종료...")

if __name__ == "__main__":
    if "--cron" in sys.argv:
        # 스케줄러에 의한 자동 실행
        backup.run_backup()
    else:
        first_run()
