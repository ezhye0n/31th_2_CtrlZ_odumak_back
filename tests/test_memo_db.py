"""DB가 필요한 메모 테스트 (CI의 pgvector 서비스 / 로컬 docker compose의 db 사용).
DB에 연결할 수 없으면 건너뛴다."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import numpy as np
import pytest
from sqlalchemy import delete, select

from app.core.database import SessionLocal, engine
from app.core.security import create_access_token
from app.domains.auth.models import Member
from app.domains.book.models import Booklist
from app.domains.memo.models import EMBEDDING_DIM, Cluster, Memo
from app.domains.room.models import Bookroom, BookroomMember
from app.ml import embedder


def auth(member_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(member_id)}"}


@pytest.fixture
async def room():
    """회원 2명(참여자 reader, 비참여자 outsider), 책 1권, 독서방 1개 생성 후 정리."""
    now = datetime.now(UTC)
    try:
        async with SessionLocal() as db:
            reader = Member(email=f"r-{uuid4().hex}@test.com", terms_agreed_at=now)
            outsider = Member(email=f"o-{uuid4().hex}@test.com", terms_agreed_at=now)
            book = Booklist(title="책", writer="작가", status="approved")
            db.add_all([reader, outsider, book])
            await db.flush()
            bookroom = Bookroom(
                owner_id=reader.member_id,
                max_capacity=5,
                book_id=book.book_id,
                title="방",
                status="active",
                start_date=now,
                end_date=now + timedelta(days=14),
                is_public=True,
            )
            db.add(bookroom)
            await db.flush()
            db.add(
                BookroomMember(
                    bookroom_id=bookroom.bookroom_id,
                    member_id=reader.member_id,
                    current_chapter=2,
                    joined_at=now,
                )
            )
            await db.commit()
            ids = {
                "room_id": bookroom.bookroom_id,
                "reader": reader.member_id,
                "outsider": outsider.member_id,
                "book_id": book.book_id,
            }
    except OSError:
        await engine.dispose()
        pytest.skip("DB에 연결할 수 없음")

    yield ids

    async with SessionLocal() as db:
        await db.execute(delete(Memo).where(Memo.bookroom_id == ids["room_id"]))
        await db.execute(delete(Cluster).where(Cluster.bookroom_id == ids["room_id"]))
        await db.execute(delete(Bookroom).where(Bookroom.bookroom_id == ids["room_id"]))
        await db.execute(delete(Booklist).where(Booklist.book_id == ids["book_id"]))
        await db.execute(
            delete(Member).where(Member.member_id.in_([ids["reader"], ids["outsider"]]))
        )
        await db.commit()
    await engine.dispose()  # 테스트마다 이벤트 루프가 달라서 커넥션 풀 비우기


@pytest.fixture
def fake_embedder(monkeypatch):
    """본문 첫 글자로 방향이 정해지는 가짜 임베딩: 첫 글자가 같으면 유사도 1, 다르면 0."""

    def encode(texts):
        out = []
        for t in texts:
            v = np.zeros(EMBEDDING_DIM)
            v[ord(t[0]) % EMBEDDING_DIM] = 1.0
            out.append(v)
        return np.array(out)

    monkeypatch.setattr(embedder, "_model", object())
    monkeypatch.setattr(embedder, "encode", encode)


async def create(client, room, member, **body):
    payload = {"chapter": 1, "content": "가 메모"} | body
    return await client.post(
        f"/api/rooms/{room['room_id']}/memos", json=payload, headers=auth(member)
    )


async def test_create_and_list(client, room):
    res = await create(client, room, room["reader"])
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["cluster_id"] is None  # ENABLE_EMBEDDING=false
    assert data["is_spoiler"] is False

    res = await client.get(f"/api/rooms/{room['room_id']}/memos", headers=auth(room["reader"]))
    assert res.status_code == 200
    memos = res.json()["data"]["memos"]
    assert [m["memo_id"] for m in memos] == [data["memo_id"]]


async def test_room_not_found(client, room):
    res = await client.post(
        "/api/rooms/999999999/memos",
        json={"chapter": 1, "content": "a"},
        headers=auth(room["reader"]),
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "ROOM_NOT_FOUND"


async def test_not_room_member(client, room):
    res = await create(client, room, room["outsider"])
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "NOT_ROOM_MEMBER"
    res = await client.get(f"/api/rooms/{room['room_id']}/memos", headers=auth(room["outsider"]))
    assert res.status_code == 403


async def test_spoiler_auto_judged_by_progress(client, room):
    # reader의 진행 챕터는 2
    assert (await create(client, room, room["reader"], chapter=3)).json()["data"]["is_spoiler"]
    assert not (await create(client, room, room["reader"], chapter=2)).json()["data"]["is_spoiler"]
    marked = await create(client, room, room["reader"], chapter=1, is_spoiler=True)
    assert marked.json()["data"]["is_spoiler"]


async def test_list_pagination_and_chapter_filter(client, room):
    ids = [
        (await create(client, room, room["reader"], chapter=c)).json()["data"]["memo_id"]
        for c in (1, 1, 2)
    ]
    url = f"/api/rooms/{room['room_id']}/memos"
    page1 = (await client.get(f"{url}?limit=2", headers=auth(room["reader"]))).json()["data"]
    assert [m["memo_id"] for m in page1["memos"]] == [ids[2], ids[1]]
    page2 = (
        await client.get(
            f"{url}?limit=2&cursor={page1['next_cursor']}", headers=auth(room["reader"])
        )
    ).json()["data"]
    assert [m["memo_id"] for m in page2["memos"]] == [ids[0]]
    assert page2["next_cursor"] is None

    ch1 = (await client.get(f"{url}?chapter=1&sort=oldest", headers=auth(room["reader"]))).json()
    assert [m["memo_id"] for m in ch1["data"]["memos"]] == ids[:2]


async def test_update_and_delete_permissions(client, room):
    memo_id = (await create(client, room, room["reader"])).json()["data"]["memo_id"]

    res = await client.patch(
        f"/api/memos/{memo_id}", json={"content": "x"}, headers=auth(room["outsider"])
    )
    assert res.json()["error"]["code"] == "SELF_ONLY"
    res = await client.delete(f"/api/memos/{memo_id}", headers=auth(room["outsider"]))
    assert res.status_code == 403

    res = await client.patch(
        f"/api/memos/{memo_id}", json={"content": "수정"}, headers=auth(room["reader"])
    )
    assert res.status_code == 200
    assert res.json()["data"] == {"memo_id": memo_id, "cluster_id": None}

    res = await client.delete(f"/api/memos/{memo_id}", headers=auth(room["reader"]))
    assert res.status_code == 200
    assert res.json() == {"success": True, "data": None, "error": None}
    res = await client.delete(f"/api/memos/{memo_id}", headers=auth(room["reader"]))
    assert res.json()["error"]["code"] == "MEMO_NOT_FOUND"


async def test_clustering_flow(client, room, fake_embedder):
    a = (await create(client, room, room["reader"], content="가 첫 메모")).json()["data"]
    b = (await create(client, room, room["reader"], content="가 비슷한 메모")).json()["data"]
    c = (await create(client, room, room["reader"], content="나 다른 메모")).json()["data"]
    other_chapter = (
        await create(client, room, room["reader"], chapter=2, content="가 메모")
    ).json()
    assert a["cluster_id"] is not None
    assert b["cluster_id"] == a["cluster_id"]
    assert c["cluster_id"] not in (None, a["cluster_id"])
    assert other_chapter["data"]["cluster_id"] not in (a["cluster_id"], c["cluster_id"])

    # c를 '가' 메모로 수정하면 a 클러스터로 이동하고, 비게 된 c 클러스터는 삭제
    res = await client.patch(
        f"/api/memos/{c['memo_id']}", json={"content": "가 로 바꿈"}, headers=auth(room["reader"])
    )
    assert res.json()["data"]["cluster_id"] == a["cluster_id"]
    async with SessionLocal() as db:
        assert await db.get(Cluster, c["cluster_id"]) is None

    # 클러스터에 메모가 남아 있으면 유지, 마지막 메모까지 지우면 클러스터 삭제
    for memo, remains in ((a, True), (b, True), (c, False)):
        await client.delete(f"/api/memos/{memo['memo_id']}", headers=auth(room["reader"]))
        async with SessionLocal() as db:
            cluster = await db.scalar(select(Cluster).where(Cluster.cluster_id == a["cluster_id"]))
            assert (cluster is not None) == remains
