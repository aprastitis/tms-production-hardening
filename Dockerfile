# syntax=docker/dockerfile:1.7

# ---- builder stage ----
FROM python:3.12-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


# ---- runtime stage ----
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Non-root user: fixed UID/GID 1001 so the runtime is predictable across
# CI and the host. --system avoids /etc/passwd writes that some slim
# image configs reject.
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --create-home --home-dir /home/app app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY . /app

USER app
EXPOSE 8000

# gunicorn with uvicorn workers — 2 workers is a reasonable default for a
# small service; override at deploy time by changing the CMD in a child
# image if needed.
CMD ["gunicorn", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "app.main:app"]