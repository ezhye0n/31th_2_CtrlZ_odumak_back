from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.models import EmailVerification, Member


class AuthRepository:
    """DB 접근만 담당. 비즈니스 규칙은 service에."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_member(self, member_id: int) -> Member | None:
        return await self.db.get(Member, member_id)

    async def get_member_by_email(self, email: str) -> Member | None:
        return await self.db.scalar(select(Member).where(Member.email == email))

    async def get_member_by_social(self, provider: str, social_id: str) -> Member | None:
        stmt = select(Member).where(Member.provider == provider, Member.social_id == social_id)
        return await self.db.scalar(stmt)

    def add(self, obj: Member | EmailVerification) -> None:
        self.db.add(obj)

    async def get_latest_verification(self, email: str) -> EmailVerification | None:
        stmt = (
            select(EmailVerification)
            .where(EmailVerification.email == email)
            .order_by(EmailVerification.verification_id.desc())
            .limit(1)
        )
        return await self.db.scalar(stmt)

    async def delete_verifications(self, email: str) -> None:
        await self.db.execute(delete(EmailVerification).where(EmailVerification.email == email))
