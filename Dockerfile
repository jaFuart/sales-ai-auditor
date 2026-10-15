FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY auditor/ auditor/
COPY dist/ dist/
COPY examples/ examples/
RUN useradd --system --uid 10001 appuser && mkdir -p runtime && chown -R appuser:appuser /app
USER appuser
RUN python -m auditor build-demo
EXPOSE 8080
CMD ["python", "-m", "auditor", "serve", "--host", "0.0.0.0", "--port", "8080"]
