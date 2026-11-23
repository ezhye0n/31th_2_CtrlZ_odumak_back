# 메모 클러스터링 실험 (TF-IDF baseline vs Ko-SBERT/e5)

AI 사전계획서의 비교 실험용 폴더. 서버 코드(`app/`)와 분리되어 있고 CI 테스트 대상이 아니다.

```
data/memos_v0.csv      평가용 독서 메모 73개 + 정답 클러스터 label
evaluate.py            모델 공통 평가 (임베딩 행렬만 넘기면 됨)
tfidf_baseline.py      TF-IDF baseline 4가지 설정
results/               실행 결과 JSON
```

## 실행

```bash
pip install -r requirements-ml.txt   # scikit-learn, numpy
python experiments/memo_clustering/tfidf_baseline.py
```

## 데이터 (`memos_v0.csv`)

| 컬럼 | 설명 |
|---|---|
| memo_id | 작성 순서. 온라인 할당 시뮬레이션이 이 순서로 메모를 넣는다 |
| room / book / chapter | 같은 room·chapter 안에서만 클러스터가 생긴다 (서비스와 동일) |
| page / total_pages | `progress_rate` 계산 → 후보를 ±0.1 범위로 좁힘 (`POSITION_WINDOW`) |
| quote | 인용문 (선택) |
| content | 메모 본문 |
| label | 정답 주제. **같은 room·chapter 안에서만** 의미가 있다 |
| source | `synthetic` = 팀이 작성한 예시, `real` = 실제 수집 |

v0 구성: 공유저작물 단편 3편(「어린 왕자」 1·21장, 「운수 좋은 날」 전·후반, 「동백꽃」),
5개 그룹, 정답 클러스터 15개, 메모 73개.
일부러 넣은 어려운 사례:
- 같은 주제지만 표현이 다른 경우 (예: 17번 "제일 유명한 문장" ↔ 21번 "눈은 속기 쉽다")
- 단어는 겹치지만 주제가 다른 경우 (예: 23번 "길들였으면 책임" → rose, 72번 "닭 죽였을 때" → class)

> ⚠️ v0는 **전부 직접 작성한 합성 메모**다. 실제 사용자 메모보다 문체가 고르고,
> 작성자가 "어려운 사례"를 의도해서 만들었으므로 수치는 참고용이다. 아래 방법으로 실제 메모를 모아 교체·보강해야 한다.

### 실제 메모 수집 가이드

1. 팀원·지인에게 위 3편(또는 공통으로 읽은 책 1~2권) 중 한 챕터를 읽고 메모 5~10개씩 써 달라고 한다.
   메모 앱 캡처, 노션, 밀리의서재 하이라이트 등 **본인이 쓴 메모만** 받고, 연구용으로 쓴다는 동의를 받는다.
2. 이름·연락처 등 개인정보는 지우고 CSV에 `source=real`로 추가한다. memo_id는 실제 작성 시각 순으로 매긴다.
3. **라벨링은 2명이 따로** 한다. "이 두 메모가 같은 이야기방에 있으면 자연스러운가?"를 기준으로 그룹 안에서 주제를 나눈다.
   의견이 갈린 메모는 표시해 두고 합의로 정한다. 일치율(예: 두 사람 라벨 간 ARI)을 같이 기록해 두면 모델 성능의 상한선으로 쓸 수 있다.
4. 파일은 `memos_v1.csv`처럼 새 버전으로 저장하고 `--data`로 지정해 실행한다.

## 평가 방법

- **pairwise**: 같은 room·chapter 안 모든 메모 쌍에 대해 코사인 유사도로 "같은 label인가"를 판별
  → ROC-AUC, AP, F1 최대 임계값. 임계값과 무관하게 표현력 자체를 비교한다.
- **online**: `app/domains/memo/clustering.py`의 `ClusterMatcher.assign()`을 그대로 재현
  (가장 가까운 메모 1개와 비교 → 임계값 이상이면 편입, 아니면 신규 클러스터). 임계값 0~0.95를 탐색해 ARI 최대 지점을 보고한다.
- **trivial baseline**: `one_per_chapter`(챕터별로 전부 한 클러스터 = 임계값 0)와 `singletons`. 모델은 최소한 이보다 나아야 한다.

## v0 결과 (TF-IDF)

| config | ROC-AUC | AP | best F1 | ARI (online) | NMI |
|---|---|---|---|---|---|
| word (어절 1-2gram) | 0.556 | 0.326 | 0.422 | 0.449 | 0.774 |
| word + quote | 0.569 | 0.354 | 0.422 | 0.449 | 0.774 |
| char_wb (문자 2-4gram) | 0.605 | 0.380 | 0.441 | 0.458 | 0.777 |
| char_wb + quote | **0.632** | **0.427** | **0.456** | **0.458** | **0.777** |
| (참고) one_per_chapter | – | – | – | 0.366 | 0.734 |

pairwise 양성 비율 = AP의 우연 수준 ≈ 0.27 (549쌍).

해석:
- 짧은 한국어 메모는 단어가 거의 겹치지 않는다. 같은 주제 쌍의 평균 유사도도 0.01~0.04 수준이라 **AUC 0.56~0.63으로 우연(0.5)보다 조금 나은 정도**다.
- online ARI가 최대인 임계값이 0.0(=챕터 안에서 위치 창이 겹치면 전부 합침)이다.
  one_per_chapter보다 높은 건 텍스트 덕이 아니라 **페이지 위치 창(±0.1)이 클러스터를 나눠 준 효과**다
  (창을 끄면 ARI 0.366~0.383으로 trivial 수준).
- 문자 n-gram이 어절보다 낫고, quote를 붙이면 조금 오른다 → 임베딩 모델 실험에서도 quote 포함 여부를 같이 비교할 것.
- 즉 TF-IDF로는 현재 `SIMILARITY_THRESHOLD` 같은 고정 임계값을 정할 수 없다. 의미 기반 임베딩이 필요하다는 근거로 쓸 수 있다.

## 다음: 임베딩 모델 붙이기

`evaluate.py`는 (N, D) L2 정규화 행렬만 받으므로 아래처럼 붙이면 같은 표에 나란히 비교된다.

```python
from sentence_transformers import SentenceTransformer
from evaluate import load_memos, pairwise_metrics, sweep_online

memos = load_memos()
model = SentenceTransformer("jhgan/ko-sroberta-multitask")
X = model.encode([m.content for m in memos], normalize_embeddings=True)
print(pairwise_metrics(memos, X), sweep_online(memos, X)[0])
```

e5 계열은 입력 앞에 `"query: "` 접두사를 붙여야 한다. 파인튜닝 모델을 평가할 때는 학습에 쓴 메모가 평가셋에 섞이지 않게 나눌 것.
