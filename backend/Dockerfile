FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip==26.2.1 && python -m pip install --no-cache-dir -r requirements.txt
RUN groupadd --gid 10001 regulaai && useradd --uid 10001 --gid regulaai --no-create-home regulaai
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY start_render.py .
USER regulaai
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
