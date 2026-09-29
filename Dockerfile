FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY catalyst ./catalyst
COPY frontend ./frontend
COPY tools ./tools
COPY CATALYST.md ./CATALYST.md
RUN pip install --upgrade pip && pip install . && python -m playwright install --with-deps chromium

COPY . .
RUN mkdir -p /app/catalyst_data /app/workspace
VOLUME ["/app/catalyst_data", "/app/workspace"]
EXPOSE 8000
CMD ["uvicorn", "catalyst.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
