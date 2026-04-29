#!/usr/bin/env python3
"""
webex_backup_중지 - 일배치 및 웹 뷰어 서버 자동 실행 중지
"""
import sys, os
from pathlib import Path

def stop_mac():
    # 백업 일배치
    plist_path = Path.home() / "Library/LaunchAgents/com.webex.backup.plist"
    if plist_path.exists():
        os.system(f'launchctl unload "{plist_path}"')
        plist_path.unlink()
        print("✅ Mac 일배치 중지 완료")
    else:
        print("ℹ️  등록된 일배치가 없습니다")

    # 웹 뷰어 서버
    server_plist = Path.home() / "Library/LaunchAgents/com.webex.server.plist"
    if server_plist.exists():
        os.system(f'launchctl unload "{server_plist}"')
        server_plist.unlink()
        print("✅ 웹 뷰어 서버 자동 시작 중지 완료 (포트 1985 해제)")
    else:
        print("ℹ️  등록된 웹 뷰어 서버가 없습니다")

def stop_windows():
    # 백업 일배치
    ret = os.system('schtasks /delete /tn "WebexBackup" /f 2>nul')
    if ret == 0:
        print("✅ Windows 일배치 중지 완료")
    else:
        print("ℹ️  등록된 일배치가 없습니다")

    # 웹 뷰어 서버
    os.system('schtasks /end /tn "WebexServer" 2>nul')
    ret2 = os.system('schtasks /delete /tn "WebexServer" /f 2>nul')
    if ret2 == 0:
        print("✅ Windows 웹 뷰어 서버 자동 시작 중지 완료 (포트 1985 해제)")
    else:
        print("ℹ️  등록된 웹 뷰어 서버가 없습니다")

if __name__ == "__main__":
    print("=" * 50)
    print("  Webex 백업 중지")
    print("=" * 50)
    print()
    if sys.platform == "darwin":
        stop_mac()
    elif sys.platform == "win32":
        stop_windows()
    else:
        print("crontab -e 에서 webex_backup 항목을 직접 삭제해주세요")
    print()
    input("Enter를 눌러 종료...")
