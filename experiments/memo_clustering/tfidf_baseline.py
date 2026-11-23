"""TF-IDF baseline (AI 사전계획서의 비교 실험 기준선).

형태소 분석기(konlpy 등, Java 필요) 없이 돌도록 두 가지 토큰화를 비교한다.
- word    : 공백 단위 어절 uni+bigram (한국어는 조사가 붙어서 불리할 것으로 예상)
- char_wb : 어절 경계 안 문자 2~4gram (조사·어미 변형에 강함)
입력 텍스트는 content만 / quote+content 두 가지.

실행 (repo 루트에서, requirements-ml.txt 설치 필요):
    python experiments/memo_clustering/tfidf_baseline.py
    python experiments/memo_clustering/tfidf_baseline.py --data path/to/memos.csv

주의: IDF는 평가 코퍼스 전체로 fit한다(transductive). 메모 수가 적어 불가피하며,
실서비스라면 독서방 단위로 주기적 재학습하거나 큰 코퍼스로 미리 fit해야 한다.
"""

import argparse
import json
from pathlib import Path

from evaluate import (
    DEFAULT_DATA,
    hardest_pairs,
    load_memos,
    pairwise_metrics,
    sweep_online,
    trivial_baselines,
)
from sklearn.feature_extraction.text import TfidfVectorizer

RESULTS_DIR = Path(__file__).parent / "results"

VECTORIZERS = {
    "word": lambda: TfidfVectorizer(
        analyzer="word", token_pattern=r"(?u)[^\s.,!?…~]+", ngram_range=(1, 2), sublinear_tf=True
    ),
    "char_wb": lambda: TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True),
}


def build_text(memo, with_quote: bool) -> str:
    text = f"{memo.quote} {memo.content}" if with_quote and memo.quote else memo.content
    return " ".join(text.split())


def run(data_path: Path) -> dict:
    memos = load_memos(data_path)
    results = {
        "data": str(data_path),
        "n_memos": len(memos),
        "trivial": trivial_baselines(memos),
        "runs": {},
    }
    for vec_name, make_vec in VECTORIZERS.items():
        for with_quote in (False, True):
            name = f"{vec_name}{'+quote' if with_quote else ''}"
            # TfidfVectorizer는 기본 norm="l2"라 내적 = 코사인 유사도
            X = make_vec().fit_transform([build_text(m, with_quote) for m in memos]).toarray()
            best_online, _ = sweep_online(memos, X)
            results["runs"][name] = {
                "vocab_size": X.shape[1],
                "pairwise": pairwise_metrics(memos, X),
                "online_best": best_online,
                "online_no_window": sweep_online(memos, X, window=None)[0],
                "hardest_pairs": hardest_pairs(memos, X),
            }
    return results


def print_table(results: dict) -> None:
    print(f"\n데이터: {results['data']} ({results['n_memos']}개)\n")
    header = (
        f"{'config':<16}{'AUC':>7}{'AP':>7}{'F1':>7}{'F1 thr':>8}"
        f"{'ARI':>7}{'NMI':>7}{'thr':>7}{'#clu':>7}"
    )
    print(header)
    print("-" * len(header))
    for name, r in results["runs"].items():
        p, o = r["pairwise"], r["online_best"]
        print(
            f"{name:<16}{p['roc_auc']:>7.3f}{p['avg_precision']:>7.3f}{p['best_f1']:>7.3f}"
            f"{p['best_f1_threshold']:>8.3f}{o['ari']:>7.3f}{o['nmi']:>7.3f}"
            f"{o['threshold']:>7.3f}{o['n_pred_clusters']:>4}/{o['n_gold_clusters']}"
        )
    for name, t in results["trivial"].items():
        print(f"(참고) {name:<20}ARI {t['ari']:.3f}  NMI {t['nmi']:.3f}")
    print("\nAUC/AP/F1: 같은 독서방·챕터 메모 쌍의 동일 주제 판별")
    print("ARI/NMI : 온라인 할당(ClusterMatcher 재현)에서 ARI가 최대인 임계값 기준")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "tfidf_baseline.json")
    args = parser.parse_args()

    results = run(args.data)
    print_table(results)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {args.out}")


if __name__ == "__main__":
    main()
