FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app
RUN pip install --no-cache-dir \
    "a2a-sdk[http-server]==1.1.2" \
    fastapi==0.119.1 \
    "google-genai==2.25.0" \
    "pyjwt[crypto]==2.15.0" \
    "uvicorn[standard]==0.38.0"
COPY src ./src
RUN useradd --system --uid 10002 --no-create-home specialist
USER 10002
EXPOSE 8000
CMD ["uvicorn", "multimodal_agents.a2a_specialist_service:app", "--host", "0.0.0.0", "--port", "8000"]
