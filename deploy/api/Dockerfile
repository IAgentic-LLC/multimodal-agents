FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app
RUN pip install --no-cache-dir \
  fastapi==0.119.1 \
  "uvicorn[standard]==0.38.0" \
  "psycopg[binary]==3.2.12" \
  "pyjwt[crypto]==2.15.0"
COPY src ./src
RUN useradd --system --uid 10001 --no-create-home studio
USER 10001
EXPOSE 8000
CMD ["uvicorn", "multimodal_agents.studio_api:app", \
  "--host", "0.0.0.0", "--port", "8000"]
