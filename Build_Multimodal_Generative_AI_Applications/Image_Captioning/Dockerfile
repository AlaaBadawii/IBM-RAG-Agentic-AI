FROM python:3.10-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY . .

ENV OPENROUTER_API_KEY=
ENV OPENROUTER_MODEL=
ENV OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

CMD ["python", "-m", "src.main"]
