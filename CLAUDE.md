# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Webex 대화 아카이빙 도구. 두 가지 독립적인 방식으로 동작한다:

1. **Python 백업 엔진** (`backup.py` + `start.py`/`stop.py`): Webex API에서 전체 대화를 `~/Desktop/webex_backup/backup.json`으로 증분 백업
2. **웹 뷰어** (`server.py` + `index.html`): 백업 파일을 오프라인으로 보거나 Webex API에 라이브로 연결

별도 독립 도구: **`webex_space_archiver.html`** — 서버 불필요, 브라우저에서 직접 실행, 스페이스당 마크다운 파일로 내보내기

## Running

```bash
# 백업 실행 (OAuth 인증 포함)
python backup.py

# 최초 설정: 백업 + OS 스케줄러 등록 (Mac launchd / Windows Task Scheduler, 매일 03:00)
python start.py

# 스케줄러 해제
python stop.py

# 웹 뷰어 서버 시작 → http://localhost:1985
python server.py
```

## Building executables

GitHub Actions (`build.yml`)이 버전 태그(`v*`) 또는 수동 트리거 시 PyInstaller로 Mac/Windows 단일 실행 파일을 빌드하고 GitHub Release로 배포한다.

로컬 빌드:
```bash
pip install pyinstaller
# Mac
pyinstaller --onefile --name webex_backup_시작 --add-data "backup.py:." start.py
pyinstaller --onefile --name webex_backup_중지 stop.py
# Windows
pyinstaller --onefile --name webex_backup_시작 --add-data "backup.py;." start.py
```

`backup.py`는 Python 표준 라이브러리만 사용하므로 **직접 실행 시 pip 설치 불필요**. `requirements.txt`의 `pyinstaller`는 빌드 전용.

## Architecture

### OAuth 흐름 (`backup.py`)
- PKCE 방식 OAuth2, 로컬 콜백 서버 포트 `8765`
- 토큰은 `~/Desktop/webex_backup/.credentials.json`에 캐시, 만료 시 refresh token으로 자동 갱신
- `CLIENT_ID` / `CLIENT_SECRET`은 파일 상단에 하드코딩됨 (Webex Integration 등록 필요)

### 백업 데이터 구조 (`backup.json`)
```json
{
  "version": 2,
  "me": { "id": "...", "displayName": "..." },
  "people": { "<person_id>": "<displayName>" },
  "spaces": [
    {
      "id": "...", "title": "...", "type": "direct|group",
      "lastActivity": "<ISO8601>",
      "messages": [ { "id": "...", "created": "...", "files": [...], "localFiles": [...] } ]
    }
  ],
  "lastBackup": "<ISO8601>"
}
```
- 증분 백업: `lastActivity` 비교로 변경 없는 스페이스 스킵, 각 스페이스는 마지막 메시지 이후 신규 메시지만 추가
- 첨부파일: `~/Desktop/webex_backup/files/<space_id>/<msg_id_suffix>_<filename>`에 저장, `localFiles` 배열로 경로 기록

### 웹 뷰어 (`index.html` + `server.py`)
- **라이브 모드**: `server.py`(포트 1985)가 `/api/` 경로를 `https://webexapis.com/v1/`로 프록시 (CORS 우회), OAuth는 브라우저 `localStorage`에 토큰 저장
- **오프라인 모드**: `backup.json` 파일을 드래그&드롭 또는 파일 선택으로 로드
- 단일 HTML 파일, 외부 의존성 없음

### `webex_space_archiver.html`
- 완전 독립형 단일 파일, 서버 불필요
- 사용자가 Webex Access Token 직접 입력
- 스페이스 선택 후 마크다운(.md) 파일로 내보내기 (현재 `2026-04-22/` 폴더에 결과물)

## Key constraints
- `backup.py`의 `get_all_messages`는 스페이스당 최대 10,000개 메시지로 제한됨
- Rate limit(429) 자동 처리: `Retry-After` 헤더 준수
- 백업 저장 시 `.tmp` → `.rename()` 원자적 쓰기로 파일 손상 방지
