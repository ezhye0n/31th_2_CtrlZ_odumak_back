# 개발 서버(dev) 배포

AWS EC2(Ubuntu) 서버 1대에 `docker-compose.dev.yml`로 API + PostgreSQL(pgvector)을 같이 띄운다.
main에 머지되어 CI가 통과하면 GitHub Actions(`Deploy dev`)가 SSH로 접속해 자동 배포한다.

- 접속 주소: `http://<서버IP>:8000` (Swagger: `/docs`, 헬스체크: `/health/db`)
- 서버 IP와 키 파일은 저장소에 올리지 않는다 (public 저장소)

## 1. 서버 만들기 (AWS 콘솔, 한 번만)

1. Budgets에서 월 예산 알림을 먼저 설정 (프리 티어·크레딧 조건은 가입 시기마다 다르므로 확인)
2. 리전: 아시아 태평양(서울)
3. EC2 → 인스턴스 시작

| 항목 | 선택 |
| --- | --- |
| AMI | Ubuntu Server 24.04 LTS |
| 인스턴스 유형 | `t3.micro` (프리 티어 표시가 있는 것) |
| 키 페어 | 새로 생성, `.pem` 다운로드 (다시 받을 수 없음) |
| 스토리지 | 20~30GB gp3 |
| VPC / 서브넷 | 기본 VPC `(default)` / 기본 설정 없음 또는 `2a`·`2c` |
| 퍼블릭 IP 자동 할당 | 활성화 |

4. 보안 그룹 인바운드 규칙

| 포트 | 소스 | 용도 |
| --- | --- | --- |
| 22 (SSH) | 0.0.0.0/0 | GitHub Actions 배포 접속 (로그인은 키로만 가능) |
| 8000 | 0.0.0.0/0 | API·Swagger |

5432(DB)는 열지 않는다. DB는 서버 안에서만 사용한다.

5. 탄력적 IP: 네트워크 및 보안 → 탄력적 IP → 할당 → 작업 → 인스턴스에 연결.
   연결하면 처음 받은 퍼블릭 IP는 사라지고 탄력적 IP로 바뀐다. 서버를 없앨 때는 탄력적 IP도 릴리스해야 요금이 나가지 않는다.

기본 VPC가 목록에 없으면 VPC 콘솔 → 작업 → 기본 VPC 생성.

## 2. SSH 접속

Mac / Linux

```bash
chmod 400 ~/Downloads/odumak-dev.pem
ssh -i ~/Downloads/odumak-dev.pem ubuntu@<서버IP>
```

Windows (PowerShell). `UNPROTECTED PRIVATE KEY FILE` 오류가 나면 키 파일 권한을 본인만 읽기로 바꾼다.

```powershell
icacls "$HOME\Downloads\odumak-dev.pem" /inheritance:r
icacls "$HOME\Downloads\odumak-dev.pem" /grant:r "$($env:USERNAME):(R)"
ssh -i ~/Downloads/odumak-dev.pem ubuntu@<서버IP>
```

처음 접속할 때 나오는 `Are you sure you want to continue connecting?`에는 `yes`.

## 3. 서버 준비 (서버에서, 한 번만)

t3.micro는 메모리가 약 1GB라 이미지 빌드·DB 실행 중 메모리가 부족할 수 있어 swap 2GB를 먼저 만든다.

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab   # 재부팅 후에도 유지
sudo timedatectl set-timezone Asia/Seoul                     # 로그를 한국 시간으로
```

Docker 설치 후 sudo 없이 쓰도록 docker 그룹에 추가한다. 그룹 변경은 재접속해야 적용된다.

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
exit
```

재접속 후 확인: `free -h` (Swap 2.0Gi), `docker run --rm hello-world`

## 4. 코드 받기·`.env` 작성·첫 실행 (서버에서, 한 번만)

```bash
git clone https://github.com/ezhye0n/31th_2_CtrlZ_odumak_back.git ~/odumak_back
cd ~/odumak_back
cp .env.dev.example .env
```

DB 비밀번호와 JWT 키는 무작위로 생성해 넣는다. DB 비밀번호는 `POSTGRES_PASSWORD`와 `DATABASE_URL` 두 곳에 같은 값이 들어가야 한다.

```bash
DB_PW=$(openssl rand -hex 16); JWT=$(openssl rand -hex 32)
sed -i "s/change-me-strong-password/$DB_PW/g; s/^JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$JWT/" .env
chmod 600 .env
grep -c change-me .env; grep -cE '^JWT_SECRET_KEY=.{64}$' .env   # 0, 1 이면 정상
```

```bash
docker compose -f docker-compose.dev.yml up -d --build   # 처음엔 3~5분
curl -s localhost:8000/health/db                          # {"db":"ok"} 이면 성공
```

마이그레이션은 컨테이너 시작 시 자동 실행된다. 내 PC 브라우저에서 `http://<서버IP>:8000/docs` 접속 확인.

## 5. GitHub Actions 자동 배포 연결 (한 번만)

GitHub 전용 배포 키를 서버에서 만들어 등록한다. 개인 `.pem` 키는 GitHub에 올리지 않는다.

```bash
ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N "" -C "github-actions-deploy"
cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/github_deploy   # BEGIN~END 줄까지 전부 복사 → DEV_SSH_KEY
```

저장소 Settings → Secrets and variables → Actions

| 종류 | 이름 | 값 |
| --- | --- | --- |
| Secret | `DEV_HOST` | 서버 IP (탄력적 IP) |
| Secret | `DEV_USER` | `ubuntu` |
| Secret | `DEV_SSH_KEY` | 위에서 복사한 개인키 전체 |
| Secret | `DEV_SSH_PORT` | (선택) 기본 22 |
| Secret | `DEV_APP_DIR` | (선택) 기본 `~/odumak_back` |
| Variable | `DEV_DEPLOY_ENABLED` | `true` (없으면 배포 워크플로가 skipped) |

등록 후 서버의 개인키는 지운다: `rm ~/.ssh/github_deploy`

확인: Actions 탭 → `Deploy dev` → Run workflow (main). 로그 끝에 `{"db":"ok"}`가 찍히면 성공.

동작: main push → CI 통과 → 서버에서 `git reset --hard origin/main` → `docker compose -f docker-compose.dev.yml up -d --build` → `/health/db` 확인 (실패 시 api 로그 100줄 출력). 서버의 `.env`는 git에 없으므로 배포해도 유지된다.

### 배포 실패 시

| 로그 | 원인 |
| --- | --- |
| `handshake failed` / `unable to authenticate` | `DEV_SSH_KEY` 일부만 복사됨, 또는 공개키를 `authorized_keys`에 등록하지 않음 |
| `dial tcp ... i/o timeout` | 보안 그룹 22번이 "내 IP"로만 열려 있음 |
| `permission denied ... docker.sock` | docker 그룹 추가 후 재접속 안 됨 |
| 실행이 skipped | `DEV_DEPLOY_ENABLED` 변수가 없거나 `true`가 아님 |

## 6. 운영 (서버에서)

```bash
cd ~/odumak_back
docker compose -f docker-compose.dev.yml ps                       # 상태
docker compose -f docker-compose.dev.yml logs -f --tail 100 api   # 로그
docker compose -f docker-compose.dev.yml exec db psql -U odumak   # DB 접속
```

`.env`를 수정한 뒤에는 `restart`가 아니라 `up -d`로 컨테이너를 다시 만들어야 새 값이 적용된다.

```bash
docker compose -f docker-compose.dev.yml up -d
```

### CORS (FE 주소 추가)

`.env`의 `CORS_ORIGINS`에 FE 주소를 JSON 배열로 추가하고 `up -d`.

```
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","https://<FE 배포 주소>"]
```

FE가 https로 배포되면 브라우저가 http API 호출을 막는다(mixed content). 그때는 도메인을 연결하고 서버 앞에 Caddy/Nginx로 HTTPS를 붙인다.

## 7. AI 기능(임베딩) 켜기

`.env`에서 `INSTALL_ML=true`, `ENABLE_EMBEDDING=true`로 바꾸고 `up -d --build`.
torch CPU 버전이 포함되어 이미지가 커지고 첫 기동 시 모델을 내려받는다. 메모리 1GB 서버에서는 부족하므로 인스턴스 유형을 올린 뒤 켠다.
꺼져 있으면 메모 작성·수정 응답의 `cluster_id`는 항상 `null`이다.
