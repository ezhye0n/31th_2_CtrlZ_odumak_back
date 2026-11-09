from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    ),
]
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Password = Annotated[str, StringConstraints(min_length=1)]


class LoginRequest(BaseModel):
    email: Email
    password: Password


class SocialLoginRequest(BaseModel):
    social_token: NonBlank


class SignupRequest(BaseModel):
    signup_type: Literal["email", "social"]
    email: Email | None = None
    password: Password | None = None
    verification_token: NonBlank | None = None
    provider: NonBlank | None = None
    social_token: NonBlank | None = None
    required_agreements: list[str]
    optional_agreements: list[str] = []

    @model_validator(mode="after")
    def check_required_by_type(self):
        if self.signup_type == "email":
            if not (self.email and self.password and self.verification_token):
                raise ValueError("이메일 가입은 email, password, verification_token이 필요합니다.")
        elif not (self.provider and self.social_token):
            raise ValueError("소셜 가입은 provider, social_token이 필요합니다.")
        return self


class EmailRequest(BaseModel):
    email: Email


class CodeConfirmRequest(BaseModel):
    email: Email
    code: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{6}$")]


class PasswordResetRequest(BaseModel):
    token: NonBlank
    new_password: Password
    new_password_confirm: Password


class TokenRefreshRequest(BaseModel):
    refresh_token: NonBlank


class PreferenceRequest(BaseModel):
    genres: list[NonBlank] = Field(min_length=1)
    purpose: NonBlank


class TokenResponse(BaseModel):
    member_id: int
    access_token: str
    refresh_token: str


class SocialLoginResponse(BaseModel):
    is_new_user: bool
    has_email: bool | None = None
    member_id: int | None = None
    access_token: str | None = None
    refresh_token: str | None = None
