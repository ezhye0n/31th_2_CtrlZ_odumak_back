# 개발 서버(dev) 배포

Docker가 깔린 리눅스 서버 1대(AWS EC2·Lightsail, GCP, NCP 등)에 `docker-compose.dev.yml`로
API + PostgreSQL(pgvector)을 같이 띄운다. main에 머지되어 CI가 통과하면 GitHub Actions가 SSH로 접속해 자동 배포한다.

## 1. 서버 최초 세팅 (한 번만)

권장 사양: 2 vCPU / 2GB RAM 이상 (AI 기능까지 켜면 4GB 이상), Ubuntu 22.04+.
보안 그룹/방화벽에서 22(SSH), 8000(API) 인바운드 허용. 5432는 열지 않는다.

```bash
# Docker 설치
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # 재접속 후 sudo 없이 docker 사용

# 코드 받기 (private 저장소면 deploy key 또는 PAT 사용)
git clone https://github.com/ezhye0n/31th_2_CtrlZ_odumak_back.git ~/odumak_back
cd ~/odumak_back

# 환경변수: 비밀번호·JWT 키 채우기 (DATABASE_URL의 비밀번호도 POSTGRES_PASSWORD와 같게)
cp .env.dev.example .env
openssl rand -hex 32   # → JWT_SECRET_KEY에 붙여넣기
vi .env

# 첫 기동 (마이그레이션은 컨테이너 시작 시 자동 실행)
docker compose -f docker-compose.dev.yml up -d --build
curl http://localhost:8000/health/db   # {"db":"ok"} 이면 성공
```

확인: `http://<서버IP>:8000/docs` (APP_ENV=dev라 Swagger 노출됨)

## 2. GitHub Actions 자동 배포 연결

저장소 Settings → Secrets and variables → Actions

| 종류 | 이름 | 값 |
| --- | --- | --- |
| Variable | `DEV_DEPLOY_ENABLED` | `true` (이 값이 있어야 배포 워크플로가 동작) |
| Secret | `DEV_HOST` | 서버 공인 IP 또는 도메인 |
| Secret | `DEV_USER` | SSH 사용자 (예: `ubuntu`) |
| Secret | `DEV_SSH_KEY` | 서버 접속용 개인키 전체 (`-----BEGIN ... KEY-----` 포함) |
| Secret | `DEV_SSH_PORT` | (선택) 기본 22 |
| Secret | `DEV_APP_DIR` | (선택) 서버 내 코드 경로, 기본 `~/odumak_back` |

배포 키는 따로 만들어 서버 `~/.ssh/authorized_keys`에 공개키를 추가하는 것을 권장한다.

```bash
ssh-keygen -t ed25519 -f odumak_deploy -N ""
# odumak_deploy.pub → 서버 authorized_keys, odumak_deploy(개인키) → DEV_SSH_KEY
```

동작: main push → CI 통과 → `Deploy dev` 워크플로가 서버에서
`git reset --hard origin/main` → `docker compose -f docker-compose.dev.yml up -d --build` → `/health/db` 확인.
Actions 탭에서 `Deploy dev` → Run workflow로 수동 배포도 가능.

## 3. 자주 쓰는 명령 (서버에서)

```bash
cd ~/odumak_back
docker compose -f docker-compose.dev.yml logs -f api        # 로그
docker compose -f docker-compose.dev.yml restart api        # .env 수정 후 재시작
docker compose -f docker-compose.dev.yml exec db psql -U odumak   # DB 접속
```

## 4. AI 기능(임베딩) 켜기

`.env`에서 `INSTALL_ML=true`, `ENABLE_EMBEDDING=true`로 바꾸고 `up -d --build`.
torch CPU 버전이 포함되어 이미지가 커지고, 첫 기동 시 모델을 Hugging Face에서 내려받는다(RAM 4GB 이상 권장).
꺼져 있으면 메모 작성·수정 응답의 `cluster_id`는 항상 `null`이다.

## 5. 참고

- HTTPS가 필요하면(FE 배포 도메인이 https인 경우 등) 서버에 Caddy/Nginx를 앞에 두고 8000으로 프록시한다.
- FE 개발 서버 주소가 정해지면 `.env`의 `CORS_ORIGINS`에 추가하고 api 재시작.
