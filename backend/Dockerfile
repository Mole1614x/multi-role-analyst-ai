FROM python:3.12-slim
ENV UV_PROJECT_ENVIRONMENT=/opt/analyst-venv UV_LINK_MODE=hardlink UV_PYTHON_DOWNLOADS=never \
    PATH=/opt/analyst-venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/analyst-matplotlib OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
WORKDIR /srv/analyst
RUN useradd -r -u 10001 analyst && mkdir storage && chown analyst:analyst storage
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi; \
    uv sync --locked --no-dev && uv cache clean
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
USER analyst
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
