FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
RUN mkdir -p /app/data \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "ticket_api.main:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
