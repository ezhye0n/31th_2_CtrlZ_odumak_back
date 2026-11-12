"""61. 메모 클러스터 매칭 (임시 구현).

AI 사전계획서의 비교 실험(TF-IDF baseline vs Ko-SBERT/e5 파인튜닝)이 끝나기 전까지 쓰는 임시 로직.
- ENABLE_EMBEDDING=false(모델 미로드)면 아무것도 하지 않고 cluster_id=null
- 켜져 있으면: 임베딩 생성 → 같은 독서방·챕터(+페이지 상대 위치 근처)에서 가장 가까운 메모 1개와
  코사인 유사도 비교 → 임계값 이상이면 그 메모의 클러스터에 편입, 아니면 신규 클러스터 생성
최종 모델·임계값·KMeans/HDBSCAN 등이 확정되면 assign()과 상수만 교체하면 된다.
"""

from app.domains.memo.models import Cluster, Memo
from app.domains.memo.repository import MemoRepository
from app.ml import embedder

SIMILARITY_THRESHOLD = 0.6  # TODO: 평가 데이터셋으로 튜닝
POSITION_WINDOW = 0.1  # 페이지 상대 위치(0~1) 기준 후보 범위 ±10%


def _preprocess(memo: Memo) -> str:
    return " ".join(memo.content.split())


class ClusterMatcher:
    def __init__(self, repo: MemoRepository):
        self.repo = repo

    async def assign(self, memo: Memo) -> None:
        """memo.embedding·cluster_id를 채운다. commit은 호출한 service에서."""
        if not embedder.is_ready():
            memo.embedding = None
            memo.cluster_id = None
            return

        vector = [float(x) for x in embedder.encode([_preprocess(memo)])[0]]
        memo.embedding = vector

        nearest = await self.repo.find_nearest_clustered_memo(memo, vector, POSITION_WINDOW)
        if nearest is not None and 1 - nearest[1] >= SIMILARITY_THRESHOLD:
            memo.cluster_id = nearest[0].cluster_id
        else:
            cluster = Cluster(bookroom_id=memo.bookroom_id, chapter=memo.chapter)
            self.repo.add_cluster(cluster)
            await self.repo.db.flush()
            memo.cluster_id = cluster.cluster_id
        await self.invalidate(memo.cluster_id)

    async def invalidate(self, cluster_id: int | None) -> None:
        """클러스터 구성이 바뀌면 AI 요약 캐시 무효화. (질문 캐시도 추가되면 여기서 같이)"""
        if cluster_id is None:
            return
        cluster = await self.repo.get_cluster(cluster_id)
        if cluster is not None:
            cluster.summary = None

    async def cleanup(self, cluster_id: int | None) -> None:
        """메모가 빠진 클러스터 정리: 비었으면 삭제, 남았으면 요약 캐시 무효화 (flush 후 호출)."""
        if cluster_id is None:
            return
        cluster = await self.repo.get_cluster(cluster_id)
        if cluster is None:
            return
        if await self.repo.count_cluster_memos(cluster_id) == 0:
            await self.repo.delete_cluster(cluster)
        else:
            cluster.summary = None
