FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home attendance
COPY backend ./backend
RUN mkdir /app/data && chown attendance:attendance /app/data
USER attendance
ENV DATABASE_PATH=/app/data/attendance.sqlite3
EXPOSE 8000
CMD ["uvicorn", "backend.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
