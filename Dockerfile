FROM python:3.11-slim
ENV PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app
COPY requirements.lock ./
# pytest is the only third-party package (tests only); the environment itself is stdlib-only.
RUN pip install --no-cache-dir --no-deps pytest==9.2.0 iniconfig packaging pluggy pygments
COPY . .
# default: the official-style check, offline. `docker run --network none fin-env python -m audit`
CMD ["python", "scripts/check.py"]
