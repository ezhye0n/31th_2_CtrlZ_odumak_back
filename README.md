# 오두막 책방 Backend

FastAPI + PostgreSQL + SQLAlchemy 2.0(async) + Alembic

## 1. 처음 세팅

```bash
git clone <repo-url> && cd odumak-backend
cp .env.example .env
docker compose up --build
```

- Swagger: http://localhost:8000/docs
- 헬스체크: http://localhost:8000/health , http://localhost:8000/health/db

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
    auth/      온보딩·인증
    memo/      메모·클러스터링 (도메인 작성 예시로 참고)
  ml/          임베딩 모델 로더 (서버 기동 시 1회 로드)
  models.py    Alembic이 인식할 모델 import 모음
alembic/       마이그레이션
ml_models/     파인튜닝 모델 가중치 (Git LFS)
tests/
```

새 도메인 추가 순서: `domains/<이름>/` 폴더 생성 → models.py 작성 → `app/models.py`에 import 한 줄 →
router 작성 → `app/main.py`의 `api_v1`에 include 한 줄 → 마이그레이션 생성.

계층 규칙: router는 요청·응답 변환만, service는 비즈니스 규칙과 commit, repository는 쿼리만.

## 3. 공통 규칙

응답 포맷 (성공·실패 모두 동일한 형태)

```json
{ "success": true,  "data": { ... }, "error": null }
{ "success": false, "data": null,   "error": { "code": "NOT_FOUND", "message": "..." } }
```

- 성공: `return ok(data)`
- 실패: `raise NotFound(...)`, `Forbidden(...)` 또는 `AppException(status, code, message)`
- 인증 필요 API: `user_id: int = Depends(get_current_user_id)`
- URI prefix: `/api/v1`

## 4. DB 마이그레이션

모델을 바꿨으면 반드시 마이그레이션 파일을 같이 커밋한다.

```bash
docker compose exec api alembic revision --autogenerate -m "add rooms table"
docker compose exec api alembic upgrade head
```

같은 시점에 두 명이 마이그레이션을 만들면 head가 갈라진다. PR 머지 전 `alembic heads`로 하나인지 확인하고,
갈라졌으면 `alembic merge heads -m "merge"`로 합친다.

## 5. 브랜치 / PR

- `main`: 배포용, `develop`: 통합 개발 브랜치
- 작업 브랜치: `feat/<기능명세서번호>-<짧은설명>` (예: `feat/58-memo-create`), `fix/...`
- develop으로 PR, 리뷰 1명 이상 승인 후 머지
- CI(ruff 린트·포맷 검사, 마이그레이션, pytest)가 통과해야 머지

커밋 전 로컬에서:

```bash
ruff check . --fix && ruff format . && pytest -q
```
