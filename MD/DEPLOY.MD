# 🚀 План деплоя cute-nails на дедик (Новосибирск)

---

## 0. Подготовка на локальной машине

```bash
# Отозвать старый токен бота (сделай вручную через @BotFather → /revoke)
# Получить новый токен и записать его

# Убедиться что .env актуален (НЕ коммить в git!)
# Поля для дедика:
#   BOT_TOKEN=НОВЫЙ_ТОКЕН
#   ADMIN_IDS=675574689,1276884131
#   ADMIN_USERNAME=@zhechka228
#   DB_HOST=db            ← имя Docker-сервиса, НЕ localhost!
#   DB_PORT=5432
#   DB_USER=cute_nails
#   DB_PASS=СИЛЬНЫЙ_ПАРОЛЬ  ← сгенерируй: openssl rand -base64 32
#   DB_NAME=cute_nails_db
```

---

## 1. Подключение к серверу

```bash
ssh root@IP_ДЕДИКА
```

---

## 2. Установка Docker (если ещё нет)

```bash
# Обновляем систему
apt update && apt upgrade -y

# Ставим Docker
curl -fsSL https://get.docker.com | sh

# Проверяем
docker --version
docker compose version
```

---

## 3. Клонирование проекта

```bash
# Создаём директорию
mkdir -p /opt/cute-nails
cd /opt/cute-nails

# Клонируем репо (если приватный — используй SSH-ключ или токен)
git clone https://github.com/ВАШ_ЮЗЕРНЕЙМ/cute-nails.git .

# Или если репо приватный:
# git clone git@github.com:ВАШ_ЮЗЕРНЕЙМ/cute-nails.git .
```

---

## 4. Создание .env на сервере

```bash
# Генерируем пароль для БД
openssl rand -base64 32

# Создаём .env (вставляем руками)
nano /opt/cute-nails/.env
```

Содержимое `.env`:
```env
BOT_TOKEN=СЮДА_НОВЫЙ_ТОКЕН
ADMIN_IDS=675574689,1276884131
ADMIN_USERNAME=@zhechka228

DB_HOST=db
DB_PORT=5432
DB_USER=cute_nails
DB_PASS=СЮДА_СГЕНЕРИРОВАННЫЙ_ПАРОЛЬ
DB_NAME=cute_nails_db
```

> ⚠️ DB_HOST=db — это имя Docker-сервиса, не localhost!
> PROXY не нужен — прокси теперь через v2rayA в Docker-сети.

---

## 5. Запуск контейнеров

```bash
cd /opt/cute-nails

# Собираем и поднимаем всё
docker compose up -d --build

# Проверяем что всё запустилось
docker compose ps

# Смотрим логи (убедиться что нет ошибок)
docker compose logs -f --tail=50
# Ctrl+C чтобы выйти из логов
```

На этом этапе:
- ✅ PostgreSQL поднялся и прошёл healthcheck
- ✅ v2rayA поднялся (но ещё не настроен — бот пока не работает!)
- ⏳ Бот запустился но не может достучаться до Telegram API

---

## 6. Настройка v2rayA (прокси для Telegram)

```bash
# С ЛОКАЛЬНОЙ МАШИНЫ (не с дедика!) пробрасываем порт панели:
ssh -L 2017:127.0.0.1:2017 root@IP_ДЕДИКА
```

Теперь открой в браузере: **http://localhost:2017**

1. Создай аккаунт администратора (логин/пароль для панели)
2. Нажми **Import** → вставь ссылку подписки
3. Зайди в **⚙️ Setting** (справа сверху) → включи **Port Sharing** (чтобы v2rayA принимал соединения из Docker-сети) → нажми Save.
4. На вкладке **SERVER** выбери сервер → нажми **▶ Start**
5. Убедись что статус **Connected**

После этого бот получит доступ к Telegram API через `socks5://v2raya:20170`.

---

## 7. Миграция базы данных

```bash
cd /opt/cute-nails

# Накатываем миграции Alembic внутри контейнера бота
docker compose exec bot python -m alembic upgrade head
```

Должно вывести:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 9002ba9cf653
INFO  [alembic.runtime.migration] Running upgrade 9002ba9cf653 -> a1b2c3d4e5f6
```

---

## 8. Перезапуск бота (после настройки v2rayA и миграций)

```bash
docker compose restart bot

# Проверяем логи — должно быть "Бот запущен и готов к работе"
docker compose logs -f bot --tail=20
```

---

## 9. Проверка что всё работает

```bash
# Статус всех контейнеров — все должны быть Up
docker compose ps

# Проверка БД
docker compose exec db psql -U cute_nails -d cute_nails_db -c "\dt"
# Должны быть таблицы: users, slots, bookings, alembic_version

# Проверка логов бота
docker compose logs bot --tail=10
```

Теперь зайди в Telegram → нажми **/start** в боте → убедись что всё работает.

---

## 10. Полезные команды для обслуживания

```bash
# ── Логи ──────────────────────────────────
docker compose logs -f bot         # Логи бота в реальном времени
docker compose logs -f db          # Логи PostgreSQL
docker compose logs -f v2raya      # Логи прокси

# ── Перезапуск ────────────────────────────
docker compose restart bot         # Перезапуск только бота
docker compose restart             # Перезапуск всего

# ── Обновление кода ──────────────────────
cd /opt/cute-nails
git pull                           # Тянем изменения
docker compose up -d --build bot   # Пересобираем только бота

# ── Бэкап БД ─────────────────────────────
docker compose exec db pg_dump -U cute_nails cute_nails_db > backup_$(date +%Y%m%d).sql

# ── Восстановление БД ────────────────────
cat backup_20260708.sql | docker compose exec -T db psql -U cute_nails cute_nails_db

# ── Полная остановка ──────────────────────
docker compose down                # Остановить (данные БД сохранятся в volume)
docker compose down -v             # ⚠️ Остановить + УДАЛИТЬ данные БД

# ── Миграции ──────────────────────────────
docker compose exec bot python -m alembic upgrade head      # Накатить
docker compose exec bot python -m alembic downgrade -1      # Откатить последнюю
docker compose exec bot python -m alembic current           # Текущая версия
```

---

## Порядок действий (чеклист)

- [ ] Отозвать старый BOT_TOKEN через @BotFather
- [ ] Подключиться к серверу по SSH
- [ ] Установить Docker (если нет)
- [ ] Склонировать репо в `/opt/cute-nails`
- [ ] Создать `.env` с новым токеном и сильным паролем БД
- [ ] `docker compose up -d --build`
- [ ] Настроить v2rayA через SSH-туннель (localhost:2017)
- [ ] `docker compose exec bot python -m alembic upgrade head`
- [ ] `docker compose restart bot`
- [ ] Проверить бота в Telegram — /start
