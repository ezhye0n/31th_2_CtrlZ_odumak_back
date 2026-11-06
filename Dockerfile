FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# INSTALL_ML=true일 때만 CPU 전용 torch + sentence-transformers 설치
# (기본 torch는 CUDA 포함이라 이미지가 수 GB로 커짐)
ARG INSTALL_ML=false

COPY requirements.txt requirements-ml.txt ./
RUN pip install -r requirements.txt && \
    if [ "$INSTALL_ML" = "true" ]; then \
      pip install torch --index-url https://download.pytorch.org/whl/cpu && \
      pip install -r requirements-ml.txt ; \
    fi

COPY . .

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
