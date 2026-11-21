# Builds the website, then serves website + API from one Python server (works on Hugging Face Spaces).
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
RUN useradd -m -u 1000 user
WORKDIR /home/user/app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY --chown=user:user backend backend
COPY --from=web --chown=user:user /web/dist frontend/dist
USER user
ENV AUTOSEED=1 DEMO_OTP=1 RESQ_DB=/tmp/resqgrid.db PORT=7860
WORKDIR /home/user/app/backend
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
