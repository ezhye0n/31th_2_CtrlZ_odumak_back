"""DB 없이 확인 가능한 요청 검증 테스트."""

from app.core.security import create_access_token, create_refresh_token
from app.domains.auth.tokens import create_reset_token, create_verification_token

AUTH = {"Authorization": f"Bearer {create_access_token(1)}"}
AGREEMENTS = ["TERMS_OF_SERVICE", "PRIVACY_POLICY"]


def error_code(res) -> str:
    return res.json()["error"]["code"]


def email_signup(**overrides) -> dict:
    body = {
        "signup_type": "email",
        "email": "reader@example.com",
        "password": "book1234",
        "verification_token": create_verification_token("reader@example.com"),
        "required_agreements": AGREEMENTS,
    }
    return {**body, **overrides}


# S-01-1 로그인
async def test_login_requires_password(client):
    res = await client.post("/api/auth/login", json={"email": "reader@example.com"})
    assert res.status_code == 400
    assert error_code(res) == "INVALID_INPUT"


async def test_login_rejects_invalid_email(client):
    res = await client.post("/api/auth/login", json={"email": "reader", "password": "book1234"})
    assert res.status_code == 400
    assert error_code(res) == "INVALID_INPUT"


# S-01-2 소셜 로그인 진입
async def test_social_login_rejects_unsupported_provider(client):
    res = await client.post("/api/auth/social/naver", json={"social_token": "token"})
    assert res.status_code == 400
    assert error_code(res) == "UNSUPPORTED_PROVIDER"


async def test_social_login_requires_token(client):
    res = await client.post("/api/auth/social/kakao", json={"social_token": " "})
    assert res.status_code == 400
    assert error_code(res) == "INVALID_INPUT"


# S-31-2 회원가입
async def test_signup_rejects_unknown_type(client):
    res = await client.post("/api/auth/signup", json=email_signup(signup_type="phone"))
    assert res.status_code == 400
    assert error_code(res) == "INVALID_INPUT"


async def test_signup_email_requires_password(client):
    res = await client.post("/api/auth/signup", json=email_signup(password=None))
    assert res.status_code == 400
    assert error_code(res) == "INVALID_INPUT"


async def test_signup_social_requires_social_token(client):
    body = {"signup_type": "social", "provider": "kakao", "required_agreements": AGREEMENTS}
    res = await client.post("/api/auth/signup", json=body)
    assert res.status_code == 400
    assert error_code(res) == "INVALID_INPUT"


async def test_signup_requires_all_required_agreements(client):
    body = email_signup(required_agreements=["TERMS_OF_SERVICE"])
    res = await client.post("/api/auth/signup", json=body)
    assert res.status_code == 400
    assert error_code(res) == "REQUIRED_AGREEMENT_MISSING"


async def test_signup_rejects_weak_password(client):
    for password in ["short1", "onlyletters", "12345678", "a1" * 11]:
        res = await client.post("/api/auth/signup", json=email_signup(password=password))
        assert res.status_code == 400, password
        assert error_code(res) == "PASSWORD_POLICY_VIOLATION"


async def test_signup_rejects_invalid_verification_token(client):
    res = await client.post("/api/auth/signup", json=email_signup(verification_token="invalid"))
    assert res.status_code == 401
    assert error_code(res) == "INVALID_VERIFICATION_TOKEN"


async def test_signup_rejects_token_for_other_email(client):
    token = create_verification_token("other@example.com")
    res = await client.post("/api/auth/signup", json=email_signup(verification_token=token))
    assert res.status_code == 401
    assert error_code(res) == "INVALID_VERIFICATION_TOKEN"


async def test_signup_social_rejects_unsupported_provider(client):
    body = {
        "signup_type": "social",
        "provider": "naver",
        "social_token": "token",
        "required_agreements": AGREEMENTS,
    }
    res = await client.post("/api/auth/signup", json=body)
    assert res.status_code == 400
    assert error_code(res) == "UNSUPPORTED_PROVIDER"


# S-30-1·S-30-2·S-30-3 인증코드
async def test_send_code_rejects_invalid_email(client):
    res = await client.post("/api/auth/email/verification-code", json={"email": "not-email"})
    assert res.status_code == 400
    assert error_code(res) == "INVALID_INPUT"


async def test_confirm_code_requires_six_digits(client):
    for code in ["12345", "1234567", "abcdef"]:
        body = {"email": "reader@example.com", "code": code}
        res = await client.post("/api/auth/email/verification-code/confirm", json=body)
        assert res.status_code == 400, code
        assert error_code(res) == "INVALID_INPUT"


async def test_resend_code_requires_email(client):
    res = await client.post("/api/auth/email/verification-code/resend", json={})
    assert res.status_code == 400
    assert error_code(res) == "INVALID_INPUT"


# S-02-1·S-32-1 비밀번호 재설정
async def test_reset_request_requires_email(client):
    res = await client.post("/api/auth/password/reset-request", json={})
    assert res.status_code == 400
    assert error_code(res) == "INVALID_INPUT"


async def test_reset_rejects_password_mismatch(client):
    body = {"token": "token", "new_password": "book1234", "new_password_confirm": "book5678"}
    res = await client.post("/api/auth/password/reset", json=body)
    assert res.status_code == 400
    assert error_code(res) == "PASSWORD_MISMATCH"


async def test_reset_rejects_weak_password(client):
    body = {"token": "token", "new_password": "weak", "new_password_confirm": "weak"}
    res = await client.post("/api/auth/password/reset", json=body)
    assert res.status_code == 400
    assert error_code(res) == "PASSWORD_POLICY_VIOLATION"


async def test_reset_rejects_invalid_token(client):
    for token in ["invalid", create_access_token(1), create_verification_token("a@b.com")]:
        body = {"token": token, "new_password": "book1234", "new_password_confirm": "book1234"}
        res = await client.post("/api/auth/password/reset", json=body)
        assert res.status_code == 401
        assert error_code(res) == "INVALID_RESET_TOKEN"


def test_reset_token_changes_with_password():
    from app.domains.auth.tokens import password_fingerprint, read_reset_token

    _, fingerprint = read_reset_token(create_reset_token(1, "old-hash"))
    assert fingerprint == password_fingerprint("old-hash")
    assert fingerprint != password_fingerprint("new-hash")


# S-01-4 토큰 갱신
async def test_refresh_requires_token(client):
    res = await client.post("/api/auth/token/refresh", json={})
    assert res.status_code == 400
    assert error_code(res) == "INVALID_INPUT"


async def test_refresh_rejects_invalid_token(client):
    for token in ["invalid", create_access_token(1)]:
        res = await client.post("/api/auth/token/refresh", json={"refresh_token": token})
        assert res.status_code == 401
        assert error_code(res) == "INVALID_REFRESH_TOKEN"


def test_refresh_token_is_refresh_type():
    from app.domains.auth.tokens import create_refresh_token as create_rotating_token
    from app.domains.auth.tokens import read_refresh_token

    assert read_refresh_token(create_refresh_token(7)) == 7
    # 같은 순간에 발급해도 토큰이 달라야 이전 토큰 재사용을 구분할 수 있음
    assert create_rotating_token(7) != create_rotating_token(7)
    assert read_refresh_token(create_rotating_token(7)) == 7


# S-03-1 취향 입력
async def test_preferences_requires_token(client):
    body = {"genres": ["소설"], "purpose": "교양"}
    res = await client.post("/api/users/me/preferences", json=body)
    assert res.status_code == 401
    assert error_code(res) == "UNAUTHORIZED"


async def test_preferences_requires_genres(client):
    res = await client.post(
        "/api/users/me/preferences", json={"genres": [], "purpose": "교양"}, headers=AUTH
    )
    assert res.status_code == 400
    assert error_code(res) == "INVALID_INPUT"
