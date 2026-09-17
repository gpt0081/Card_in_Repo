FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY packages/analyzer /app/packages/analyzer
COPY apps/api /app/apps/api

RUN python -m pip install --no-cache-dir /app/packages/analyzer /app/apps/api

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "card_in_repo_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
