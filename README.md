# 오두막 책방 Backend

FastAPI + PostgreSQL + SQLAlchemy 2.0(async) + Alembic

## 1. 처음 세팅

Docker Desktop만 설치되어 있으면 된다.

```bash
git clone https://github.com/ezhye0n/31th_2_CtrlZ_odumak_back.git
cd 31th_2_CtrlZ_odumak_back
cp .env.example .env
docker compose up --build
```

- Swagger: http://localhost:8000/docs
- 헬스체크: http://localhost:8000/health , http://localhost:8000/health/db (`"db": "ok"`면 세팅 완료)
- `requirements*.txt`나 `Dockerfile`이 바뀌었을 때만 `--build`가 필요하고, 평소엔 `docker compose up`
- 5432 또는 8000 포트가 이미 사용 중이라는 에러가 나면 로컬에 켜져 있는 PostgreSQL 등을 먼저 종료

AI 기능까지 같이 띄울 때 (torch CPU 버전 포함, 이미지가 커짐):

```bash
INSTALL_ML=true docker compose up --build   # .env의 ENABLE_EMBEDDING=true도 같이
```

### Docker 없이 로컬 실행

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
# .env의 DATABASE_URL host를 db -> localhost로 변경, DB만 docker로 띄우기
docker compose up -d db
alembic upgrade head
uvicorn app.main:app --reload
```

## 2. 폴더 구조

```
app/
  core/        config, DB 세션, JWT·비밀번호
  common/      공통 응답 포맷, 예외, 인증 의존성
  domains/     기능 영역별 폴더 (router / schemas / models / service / repository)
    auth/          회원·이메일 인증·권한 (member, email_verification, authority)
    book/          책 (booklist)
    room/          독서방·참여자 (bookroom, bookroom_member)
    memo/          메모·클러스터·열람기록·첨부 (도메인 작성 예시로 참고)
    comment/       댓글 (comment)
    report/        신고·이의제기 (report, appeal)
    notification/  알림 (notification)
    record/        독서 기록 (bookrecord, bookrecord_trace)
  ml/          임베딩 모델 로더 (서버 기동 시 1회 로드)
  models.py    Alembic이 인식할 모델 import 모음
alembic/       마이그레이션
ml_models/     파인튜닝 모델 가중치 (Git LFS)
tests/
```

새 도메인 추가 순서: `domains/<이름>/` 폴더 생성 → models.py 작성 → `app/models.py`에 import 한 줄 →
router 작성 → `app/main.py`의 `api`에 include 한 줄 → 마이그레이션 생성.

계층 규칙: router는 요청·응답 변환만, service는 비즈니스 규칙과 commit, repository는 쿼리만.

## 3. 공통 규칙

응답 포맷 (성공·실패 모두 동일한 형태)

```json
{ "success": true,  "data": { ... }, "error": null }
{ "success": false, "data": null,   "error": { "code": "NOT_FOUND", "message": "..." } }
```

- 성공: `return ok(data)`
- 실패: 명세서 Error Response의 코드·메시지 그대로 예외로 던짐
  - `raise NotFound("MEMO_NOT_FOUND", "요청한 메모를 찾을 수 없습니다.")`
  - `raise Forbidden("SELF_ONLY", "...")`, `BadRequest(...)` 또는 `AppException(status, code, message)`
- 요청 형식 오류(필수값 누락, 타입·길이 위반)는 자동으로 400 `INVALID_INPUT`
- 인증 필요 API: `member_id: int = Depends(get_current_member_id)`
- URI prefix: `/api` (명세서 URI 그대로)
- ID는 모두 숫자(Number)

## 4. DB 마이그레이션

모델을 바꿨으면 반드시 마이그레이션 파일을 같이 커밋한다. 생성된 파일은 ruff로 자동 정리된다(alembic.ini의 post_write_hooks).

```bash
docker compose exec api alembic revision --autogenerate -m "add rooms table"
docker compose exec api alembic upgrade head
```

같은 시점에 두 명이 마이그레이션을 만들면 head가 갈라진다. PR 올리기 전 main을 pull 받고 `docker compose exec api alembic heads`로 head가 하나인지 확인하고,
갈라졌으면 `alembic merge heads -m "merge"`로 합친다.

## 5. 브랜치 / PR

- `main` 하나만 사용. 직접 push 하지 않고 PR로만 머지
- 작업 브랜치: `<타입>/<짧은설명>` (예: `feat/memo-create`, `fix/memo-delete`)
  - 타입: `feat` 기능, `fix` 버그, `refactor` 리팩터링, `chore` 설정·문서
- main으로 PR, 리뷰 1명 이상 승인 후 머지, 머지한 브랜치는 삭제
- CI(ruff 린트·포맷 검사, 마이그레이션, pytest)가 통과해야 머지

커밋 전 한 번 실행 (`docker compose up`으로 api 컨테이너가 떠 있는 상태에서):

```bash
docker compose exec api sh -c "ruff check . --fix && ruff format . && pytest -q"
```

venv로 로컬 실행 중이면 `ruff check . --fix && ruff format . && pytest -q`를 그대로 실행해도 된다.
