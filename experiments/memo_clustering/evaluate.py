"""모델 공통 평가 로직. 어떤 모델이든 (N, D) L2 정규화 행렬만 넘기면 같은 기준으로 비교된다.

평가 단위는 서비스와 동일하게 '같은 독서방(room)·챕터' 그룹. 그룹 간 메모는 절대 묶이지 않으므로
쌍(pair)·클러스터 지표 모두 그룹 안에서만 계산한다.

1) pairwise   : 같은 그룹 안 모든 메모 쌍의 코사인 유사도로 '같은 label인가'를 맞히는 이진 분류
                → ROC-AUC, AP, F1 최대 임계값 (임계값 독립적인 '표현력' 비교용)
2) online     : app/domains/memo/clustering.py의 ClusterMatcher.assign()을 그대로 재현
                (작성 순서대로 하나씩 들어오며, 같은 그룹·페이지 위치 ±window 안의
                 가장 가까운 메모와 비교해 임계값 이상이면 편입, 아니면 신규 클러스터)
                → ARI, NMI, 클러스터 수
                작성 시각이 없는 데이터(v1)는 순서에 따라 결과가 달라지므로
                무작위 순서 n_orders번의 평균·표준편차를 낸다.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    adjusted_rand_score,
    average_precision_score,
    normalized_mutual_info_score,
    precision_recall_curve,
    roc_auc_score,
)

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_DATA = DATA_DIR / "memos_v1.csv"  # 실제 수집 메모. v0는 합성
POSITION_WINDOW = 0.1  # clustering.py와 동일


@dataclass
class Memo:
    memo_id: str
    room: int
    book: str
    chapter: int
    page: int | None
    total_pages: int | None
    quote: str
    content: str
    label: str
    author: str = ""
    theme: str = ""  # 챕터를 넘는 공통 테마 (v1만)

    @property
    def group(self) -> tuple[int, int]:
        return (self.room, self.chapter)

    @property
    def progress_rate(self) -> float | None:
        if self.page is None or not self.total_pages:
            return None
        return self.page / self.total_pages


def load_memos(path: Path = DEFAULT_DATA) -> list[Memo]:
    def to_int(v: str) -> int | None:
        return int(v) if v.strip() else None

    with open(path, encoding="utf-8") as f:
        memos = [
            Memo(
                memo_id=r["memo_id"],
                room=int(r["room"]),
                book=r["book"],
                chapter=int(r["chapter"]),
                page=to_int(r["page"]),
                total_pages=to_int(r["total_pages"]),
                quote=r["quote"].strip(),
                content=r["content"].strip(),
                label=r["label"].strip(),
                author=r.get("author", ""),
                theme=r.get("theme", ""),
            )
            for r in csv.DictReader(f)
        ]
    return memos  # 파일 행 순서 = 작성 순서로 간주


def _group_pairs(memos: list[Memo]):
    for i in range(len(memos)):
        for j in range(i + 1, len(memos)):
            if memos[i].group == memos[j].group:
                yield i, j


def pairwise_metrics(memos: list[Memo], X: np.ndarray) -> dict:
    sim = X @ X.T
    pairs = list(_group_pairs(memos))
    y = np.array([memos[i].label == memos[j].label for i, j in pairs], dtype=int)
    s = np.array([sim[i, j] for i, j in pairs])

    prec, rec, thr = precision_recall_curve(y, s)
    f1 = 2 * prec * rec / np.clip(prec + rec, 1e-12, None)
    best = int(np.argmax(f1[:-1]))  # 마지막 원소는 임계값 없음
    return {
        "n_pairs": len(pairs),
        "pos_ratio": round(float(y.mean()), 3),
        "roc_auc": round(float(roc_auc_score(y, s)), 4),
        "avg_precision": round(float(average_precision_score(y, s)), 4),
        "best_f1": round(float(f1[best]), 4),
        "best_f1_threshold": round(float(thr[best]), 4),
        "mean_sim_pos": round(float(s[y == 1].mean()), 4),
        "mean_sim_neg": round(float(s[y == 0].mean()), 4),
    }


def online_assign(
    memos: list[Memo], X: np.ndarray, threshold: float, window: float | None = POSITION_WINDOW
) -> list[int]:
    """ClusterMatcher.assign() 재현. 반환값은 memos 순서의 예측 cluster id."""
    pred: list[int] = [-1] * len(memos)
    next_id = 0
    for i, m in enumerate(memos):
        best_j, best_sim = None, -np.inf
        for j in range(i):  # 먼저 작성된 메모(이미 클러스터 있음)만 후보
            o = memos[j]
            if o.group != m.group:
                continue
            if window is not None and m.progress_rate is not None and o.progress_rate is not None:
                if abs(o.progress_rate - m.progress_rate) > window:
                    continue
            s = float(X[i] @ X[j])
            if s > best_sim:
                best_j, best_sim = j, s
        if best_j is not None and best_sim >= threshold:
            pred[i] = pred[best_j]
        else:
            pred[i] = next_id
            next_id += 1
    return pred


def online_metrics(
    memos: list[Memo],
    X: np.ndarray,
    threshold: float,
    window: float | None = POSITION_WINDOW,
    order: list[int] | None = None,
) -> dict:
    """order: 메모가 들어오는 순서(memos 인덱스). None이면 파일 순서."""
    if order is None:
        order = list(range(len(memos)))
    pred = online_assign([memos[i] for i in order], X[order], threshold, window)
    gold = [f"{memos[i].group}:{memos[i].label}" for i in order]  # 그룹이 다르면 다른 클러스터
    return {
        "ari": float(adjusted_rand_score(gold, pred)),
        "nmi": float(normalized_mutual_info_score(gold, pred)),
        "n_pred_clusters": len(set(pred)),
        "n_gold_clusters": len(set(gold)),
    }


def trivial_baselines(memos: list[Memo]) -> dict:
    """모델 없이 얻는 하한선. 이보다 못하면 모델이 의미 없다."""
    gold = [f"{m.group}:{m.label}" for m in memos]
    preds = {
        "one_per_chapter": [str(m.group) for m in memos],  # 임계값 0 과 동일
        "singletons": list(range(len(memos))),  # 임계값 1 과 동일
    }
    return {
        name: {
            "ari": round(float(adjusted_rand_score(gold, p)), 4),
            "nmi": round(float(normalized_mutual_info_score(gold, p)), 4),
        }
        for name, p in preds.items()
    }


def sweep_online(
    memos: list[Memo],
    X: np.ndarray,
    thresholds=None,
    window: float | None = POSITION_WINDOW,
    n_orders: int = 1,
    seed: int = 0,
) -> tuple[dict, list[dict]]:
    """임계값별 온라인 할당 성능. n_orders>1이면 무작위 작성 순서 n_orders개의 평균·표준편차.
    best는 평균 ARI 최대 임계값."""
    if thresholds is None:
        thresholds = np.round(np.arange(0.0, 0.951, 0.025), 3)
    rng = np.random.default_rng(seed)
    orders = (
        [None] if n_orders <= 1 else [list(rng.permutation(len(memos))) for _ in range(n_orders)]
    )
    rows = []
    for t in thresholds:
        runs = [online_metrics(memos, X, float(t), window, o) for o in orders]
        ari = np.array([r["ari"] for r in runs])
        rows.append(
            {
                "threshold": round(float(t), 3),
                "ari": round(float(ari.mean()), 4),
                "ari_std": round(float(ari.std()), 4),
                "nmi": round(float(np.mean([r["nmi"] for r in runs])), 4),
                "n_pred_clusters": round(float(np.mean([r["n_pred_clusters"] for r in runs])), 1),
                "n_gold_clusters": runs[0]["n_gold_clusters"],
                "n_orders": len(orders),
            }
        )
    best = max(rows, key=lambda r: (r["ari"], r["nmi"]))
    return best, rows


def hardest_pairs(memos: list[Memo], X: np.ndarray, k: int = 5) -> dict:
    """에러 분석용: 다른 주제인데 유사도가 높은 쌍 / 같은 주제인데 낮은 쌍."""
    sim = X @ X.T
    pos, neg = [], []
    for i, j in _group_pairs(memos):
        item = (round(float(sim[i, j]), 3), memos[i].memo_id, memos[j].memo_id)
        (pos if memos[i].label == memos[j].label else neg).append(item)
    return {
        "false_positive_like": sorted(neg, reverse=True)[:k],
        "false_negative_like": sorted(pos)[:k],
    }
