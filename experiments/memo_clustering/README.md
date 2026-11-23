# 메모 클러스터링 실험 (TF-IDF baseline vs Ko-SBERT/e5)

AI 사전계획서의 비교 실험용 폴더. 서버 코드(`app/`)와 분리되어 있고 CI 테스트 대상이 아니다.

```
data/memos_v1.csv      실제 수집 메모 70개 (「어린 왕자」, 기본 평가셋)
data/memos_v0.csv      합성 메모 73개 (파이프라인 점검용, 참고만)
evaluate.py            모델 공통 평가 (임베딩 행렬만 넘기면 됨)
tfidf_baseline.py      TF-IDF baseline 4가지 설정
results/               실행 결과 JSON (tfidf_baseline_<데이터명>.json)
```

## 실행

```bash
pip install -r requirements-ml.txt   # scikit-learn, numpy
python experiments/memo_clustering/tfidf_baseline.py                       # v1, 무작위 순서 20개
python experiments/memo_clustering/tfidf_baseline.py --data experiments/memo_clustering/data/memos_v0.csv --orders 1
```

## 데이터

### v1 — 실제 수집 (`memos_v1.csv`)

구글시트 「[AI 데이터 수집] 어린왕자 독서 메모」에서 옮김. 작성자 4명(A~D, 실명 제외), 메모 70개.

| 챕터 | 2 | 7 | 8 | 13 | 14 | 20 | 21 | 26 |
|---|---|---|---|---|---|---|---|---|
| 메모 수 | 10 | 10 | 5 | 10 | 10 | 10 | 10 | 5 |
| 주제 수 | 2 | 3 | 2 | 2 | 2 | 2 | 3 | 3 |

- `label` = 시트의 topic(예: `21-c`), `theme` = 챕터를 넘는 공통 테마(T1~T9, 지금은 평가에 안 씀)
- 작성 시각·페이지가 없어서 위치 창은 꺼지고, 온라인 할당은 **무작위 순서 20개 평균**으로 본다.
- `quote`는 작성자가 비고란에 적은 인용문(D 4건)만 들어 있다.

옮기면서 확인한 점:
- 시트 텍스트 추출 과정에서 긴 칸 끝에 `...`이 붙어 나와, 시트의 `글자 수` 열과 대조해 제거했다.
- **A07-2는 추출이 잘려 끝의 약 8글자가 빠져 있다** ("…삶의 태도를 좀 지녀야겠단"까지). 시트 원문으로 채워야 한다.

**라벨 재검토가 필요해 보이는 메모** (안내문의 "주제에 고루 나눠서" 규칙 때문에 내용과 다른 topic을 고른 것으로 보임):

| memo_id | 현재 | 내용 | 더 맞아 보이는 topic |
|---|---|---|---|
| A26-4 | 26-c 책임 | "죽는게 너무 슬프네… 왜 물려서 왜 죽냐고" | 26-a 이별의 슬픔 |
| D21-1 | 21-c 기다림 | "'길들인다'가 무슨 뜻인지 묻는데…" | 21-a 길들임 |
| D21-3 | 21-c 기다림 | "날 길들여죠! 여우 사람 꼬시네" | 21-a 길들임 |
| D21-5 | 21-c 기다림 | "여우와 보낸 시간 덕분에 친구가 되었구나" | 21-a 길들임 |

이 중 A26-1↔A26-4, A21-1↔D21-3은 TF-IDF가 "다른 주제인데 가장 비슷하다"고 본 쌍 1·2위다 → 모델이 아니라 라벨이 틀렸을 가능성이 크다.
다음 수집 때는 주제 개수 배분 규칙을 빼고, **작성자가 아닌 2명이 따로 라벨링**한 뒤 일치율(두 라벨 간 ARI)을 기록하는 것을 권장한다. 그 일치율이 모델 성능의 현실적인 상한선이다.

### v0 — 합성 (`memos_v0.csv`)

수집 전 파이프라인 점검용으로 직접 작성한 메모 73개(「어린 왕자」·「운수 좋은 날」·「동백꽃」). 문체가 고르고 어려운 사례를 의도해 넣었으므로 수치는 참고만 한다.

### 컬럼

| 컬럼 | 설명 |
|---|---|
| memo_id | 파일 행 순서 = 작성 순서로 간주 (`--orders 1`일 때) |
| author | 작성자 코드 (v1) |
| room / book / chapter | 같은 room·chapter 안에서만 클러스터가 생긴다 (서비스와 동일) |
| page / total_pages | 있으면 `progress_rate` → 후보를 ±0.1 범위로 좁힘 (`POSITION_WINDOW`) |
| quote / content | 인용문(선택) / 메모 본문 |
| label | 정답 주제. **같은 room·chapter 안에서만** 의미가 있다 |
| theme | 공통 테마 (v1) |
| source | `real` / `synthetic` |

## 평가 방법

- **pairwise**: 같은 room·chapter 안 모든 메모 쌍에 대해 코사인 유사도로 "같은 label인가"를 판별
  → ROC-AUC, AP, F1 최대 임계값. 임계값과 무관하게 표현력 자체를 비교한다.
- **online**: `app/domains/memo/clustering.py`의 `ClusterMatcher.assign()`을 그대로 재현
  (가장 가까운 메모 1개와 비교 → 임계값 이상이면 편입, 아니면 신규 클러스터). 임계값 0~0.95를 탐색해 평균 ARI 최대 지점을 보고한다.
- **trivial baseline**: `one_per_chapter`(챕터별로 전부 한 클러스터 = 임계값 0)와 `singletons`. 모델은 최소한 이보다 나아야 한다.

## v1 결과 (실제 메모, TF-IDF)

| config | ROC-AUC | AP | best F1 | ARI (online) | 최적 임계값 |
|---|---|---|---|---|---|
| word (어절 1-2gram) | 0.484 | 0.410 | 0.585 | 0.554 | 0.0 |
| word + quote | 0.494 | 0.415 | 0.585 | 0.554 | 0.0 |
| char_wb (문자 2-4gram) | 0.546 | 0.456 | 0.585 | 0.554 | 0.0 |
| char_wb + quote | 0.558 | 0.461 | 0.585 | 0.554 | 0.0 |
| (참고) one_per_chapter | – | – | – | **0.554** | – |

290쌍, 양성 비율(= AP·F1의 우연 수준) 0.41. best F1 0.585도 "전부 같은 주제"라고 답했을 때의 F1과 같다.

임계값별 online ARI (char_wb+quote, 무작위 순서 20개 평균):

| 임계값 | 0 | 0.025 | 0.05 | 0.075 | 0.1 | 0.15 | 0.2 |
|---|---|---|---|---|---|---|---|
| ARI | 0.554 | 0.519 | 0.451 | 0.321 | 0.199 | 0.058 | 0.00 |
| 클러스터 수 (정답 19) | 8 | 12 | 21 | 36 | 48 | 63 | 68 |

해석:
- **TF-IDF는 실제 메모에서 우연 수준이다.** 같은 주제 쌍과 다른 주제 쌍의 평균 유사도가 0.054 vs 0.048로 사실상 같고, 어절 기준 AUC는 0.5 미만이다.
- 실제 메모는 합성 메모(v0, AUC 0.63)보다 더 어렵다. 말투가 사람마다 크게 다르고("개패고싶음", "노조 들어가고 파업해도 될듯"), 같은 장면을 전혀 다른 단어로 말한다.
- 임계값을 0보다 조금만 올려도 성능이 떨어진다 → **텍스트 유사도로 챕터를 더 쪼개는 순간 손해**. 즉 TF-IDF로는 `SIMILARITY_THRESHOLD`를 정할 수 없다.
- 같은 작성자 쌍(AUC 0.570)이 다른 작성자 쌍(0.556)보다 조금 높다. 문체가 겹치는 효과로, 임베딩 모델에서도 이 차이를 같이 봐야 "주제"가 아니라 "작성자"로 묶는지 확인할 수 있다.
- 임베딩 모델의 목표선: **ROC-AUC > 0.56, online ARI > 0.554(챕터 통째 묶기)**. 그룹이 작아서(챕터당 5~10개, 주제 2~3개) 이 하한선 자체가 높다는 점에 유의.

## v0 결과 (합성 메모, 참고)

| config | ROC-AUC | AP | ARI (online) |
|---|---|---|---|
| word | 0.556 | 0.326 | 0.449 |
| char_wb + quote | 0.632 | 0.427 | 0.458 |
| (참고) one_per_chapter | – | – | 0.366 |

v0에서 one_per_chapter보다 높게 나온 건 텍스트 덕이 아니라 페이지 위치 창(±0.1)이 클러스터를 나눠 준 효과다 (창을 끄면 0.366~0.383).

## 다음: 임베딩 모델 붙이기

`evaluate.py`는 (N, D) L2 정규화 행렬만 받으므로 아래처럼 붙이면 같은 기준으로 비교된다.

```python
from sentence_transformers import SentenceTransformer
from evaluate import load_memos, pairwise_metrics, sweep_online

memos = load_memos()
model = SentenceTransformer("jhgan/ko-sroberta-multitask")
X = model.encode([m.content for m in memos], normalize_embeddings=True)
print(pairwise_metrics(memos, X), sweep_online(memos, X, n_orders=20)[0])
```

e5 계열은 입력 앞에 `"query: "` 접두사를 붙여야 한다. 파인튜닝 모델을 평가할 때는 학습에 쓴 메모가 평가셋에 섞이지 않게 나눌 것
(70개로는 파인튜닝·평가를 동시에 하기 어려우므로 v1은 평가 전용으로 두는 것을 권장).
