FROM python:3.12-slim

# Не буферизовать вывод Python (логи сразу в stdout)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Устанавливаем зависимости отдельным слоем (кэширование Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY bot/ bot/
COPY alembic.ini .

CMD ["python", "-m", "bot"]
