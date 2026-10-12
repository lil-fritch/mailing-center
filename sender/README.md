# Mailing Sender

Простий email-сендер для відправки листів через різні email провайдери (SMTP для Gmail, Selenium для op.pl).

## Огляд

Цей проект є **простим сендером** - приймає запити на відправку листів і відправляє їх негайно через відповідний провайдер залежно від вказаної пошти.

### Основні можливості:
- ✅ Негайна відправка через SMTP (Gmail та інші)
- ✅ Негайна відправка через Selenium (op.pl)
- ✅ Історія відправлених листів
- ✅ Управління скриншотами Selenium

### Що НЕ входить в цей проект:
- ❌ Генерація листів (робиться в "центрі керування")
- ❌ Планування та черги відправок (вирішується центром керування)
- ❌ AI для генерації контенту
- ❌ IMAP моніторинг вхідних листів

## Архітектура

```
Центр керування → POST /email/send → Email Service → SMTP/Selenium → Негайна відправка
```

## Вимоги

- Python 3.11+
- Для Gmail SMTP: App Password (якщо увімкнено 2FA)
- Для op.pl: Chrome/Chromium (для Selenium)

## Встановлення

```bash
pip install -r requirements.txt
```

## Конфігурація

### 1. Налаштування акаунтів

Створіть файл `config/email_accounts.json`:

```json
[
  {
    "email": "your.email@gmail.com",
    "provider": "gmail",
    "password": "your-app-password",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "selenium_required": false
  },
  {
    "email": "your.email@op.pl",
    "provider": "op.pl",
    "password": "your-password",
    "selenium_required": true
  }
]
```

### 2. Environment файл (опціонально)

Створіть `.env` файл:

```env
DEBUG=true
LOG_LEVEL=INFO
```

## Запуск

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Swagger API доступний на: `http://localhost:8000/docs`

## API Endpoints

### Основні endpoint'и

#### 1. Відправити лист негайно
```http
POST /email/send
Content-Type: application/json

{
  "from_email": "sender@gmail.com",
  "to_email": "recipient@example.com",
  "subject": "Тема листа",
  "body": "Текст листа"
}
```

**Відповідь (успіх):**
```json
{
  "status": "success",
  "from_email": "sender@gmail.com",
  "to_email": "recipient@example.com"
}
```

**Відповідь (помилка):**
```json
{
  "status": "error",
  "from_email": "sender@gmail.com",
  "to_email": "recipient@example.com",
  "error_message": "Email account sender@gmail.com not found or not configured"
}
```

#### 2. Переглянути історію відправлених листів
```http
GET /email/history?limit=50
```

**Відповідь:**
```json
[
  {
    "from_email": "sender@gmail.com",
    "to_email": "recipient@example.com",
    "subject": "Тема листа",
    "body": "Текст листа",
    "sent_at": "2025-10-24T12:34:56"
  }
]
```

#### 3. Очистити історію
```http
POST /email/history/clear
```

### Управління скриншотами (для Selenium)

#### 4. Список запусків зі скриншотами
```http
GET /email/screenshots/runs?account_email=your@op.pl
```

#### 5. Очистити старі скриншоти
```http
POST /email/screenshots/cleanup
Content-Type: application/json

{
  "older_than_days": 7,
  "account_email": null,
  "dry_run": true,
  "limit": null,
  "remove_empty_parents": true
}
```

**Параметри:**
- `dry_run: true` - показує що буде видалено, не видаляючи
- `dry_run: false` - реально видаляє файли

## Структура проекту

```
mailing_sender/
├── app/
│   ├── api/
│   │   └── routes/
│   │       └── email.py          # API endpoints
│   ├── core/
│   │   ├── config.py             # Конфігурація
│   │   ├── errors.py             # Обробка помилок
│   │   └── logger.py             # Логування
│   ├── schemas/
│   │   └── email.py              # Pydantic моделі
│   ├── services/
│   │   ├── email_service.py      # Основний сервіс відправки
│   │   ├── smtp_service.py       # SMTP провайдер
│   │   ├── email_manager.py      # Керування акаунтами
│   │   ├── history_service.py    # Історія відправлень
│   │   ├── cleanup_service.py    # Очищення скриншотів
│   │   └── selenium/
│   │       └── op_pl.py          # Selenium для op.pl
│   └── main.py                   # FastAPI додаток
├── config/
│   ├── email_accounts.json       # Конфігурація акаунтів
│   └── email_history.json        # Історія відправлених
├── selenium_data/
│   └── screenshots/              # Скриншоти Selenium
├── logs/
│   └── mailing_sender.log        # Логи
├── requirements.txt
└── README.md
```

## Як це працює

### Відправка через SMTP (Gmail)
1. Отримує запит з `from_email` (Gmail акаунт)
2. Знаходить SMTP конфігурацію для цього акаунту
3. Підключається до SMTP сервера
4. Відправляє лист негайно
5. Зберігає в історію

### Відправка через Selenium (op.pl)
1. Отримує запит з `from_email` (op.pl акаунт)
2. Запускає headless Chrome
3. Логінується на poczta.onet.pl
4. Заповнює форму листа
5. Відправляє негайно
6. Робить скриншоти на кожному етапі (для debugging)
7. Зберігає в історію

## Налаштування провайдерів

### Gmail (SMTP)
1. Увімкніть 2FA в Google Account
2. Згенеруйте App Password: https://myaccount.google.com/apppasswords
3. Використовуйте App Password в `config/email_accounts.json`

### op.pl (Selenium)
1. Просто вкажіть email і пароль
2. Selenium автоматично завантажить ChromeDriver
3. Скриншоти зберігаються в `selenium_data/screenshots/<email>/<run_id>/`

## Типи помилок

### Статуси відповіді:
- `success` - лист успішно відправлено
- `error` - сталася помилка при відправці

### Типові помилки:

#### 1. Акаунт не знайдено
```json
{
  "status": "error",
  "error_message": "Email account sender@gmail.com not found or not configured"
}
```

#### 2. SMTP помилки
```json
{
  "status": "error", 
  "error_message": "SMTP authentication failed - check email and password"
}
```
```json
{
  "status": "error",
  "error_message": "Recipient email address rejected: invalid@email.com"
}
```

#### 3. Selenium помилки
```json
{
  "status": "error",
  "error_message": "Selenium timeout - page elements not found"
}
```

## Troubleshooting

### Gmail SMTP не працює
- **Помилка:** Connection timeout
- **Рішення:** Перевірте, чи не блокує VPN/firewall порт 587
- **Команда:** `Test-NetConnection smtp.gmail.com -Port 587` (PowerShell)

### Selenium падає
- **Помилка:** ChromeDriver not found
- **Рішення:** Selenium автоматично завантажує, але можна встановити вручну
- **Дебаг:** Поставте `headless=False` в `op_pl.py` (рядок 261)

## Логування

Логи зберігаються в:
- **Файл:** `logs/mailing_sender.log`
- **Консоль:** stdout

Рівень логування налаштовується через `.env`:
```env
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

## Production

### Systemd Service (Linux)
Створіть `/etc/systemd/system/mailing-sender.service`:
```ini
[Unit]
Description=Mailing Sender Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/mailing_sender
ExecStart=/path/to/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Запустіть:
```bash
sudo systemctl enable mailing-sender
sudo systemctl start mailing-sender
```

## Інтеграція з центром керування

### Приклад використання

```python
import requests

# Відправка листа
response = requests.post(
    "http://localhost:8000/email/send",
    json={
        "from_email": "sender@gmail.com",
        "to_email": "recipient@example.com",
        "subject": "Hello from Control Center",
        "body": "This is an automated email"
    }
)

if response.status_code == 200:
    result = response.json()
    print(f"Email sent! Message ID: {result['message_id']}")
else:
    print(f"Error: {response.json()}")
```

## Ліцензія

MIT

## Підтримка

Для питань та проблем створюйте issue в репозиторії.
