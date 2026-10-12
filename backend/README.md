# 📧 Mailing Center

A comprehensive email campaign management system built with FastAPI, designed for B2B outreach campaigns with AI-powered email generation and automated reply processing.

## 🚀 Features

- **AI-Powered Email Generation**: Uses OpenAI assistants to generate personalized emails
- **Database-Driven Campaigns**: Launch campaigns directly from B2B object database
- **Automated Reply Processing**: IMAP integration for processing incoming replies
- **Campaign Tracking**: Real-time monitoring of campaign progress and statistics
- **B2B Object Management**: Full CRUD operations for business objects
- **Throttling & Rate Limiting**: Configurable email sending delays to prevent spam
- **Background Processing**: Asynchronous email sending and processing

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python 3.13+)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **AI Integration**: OpenAI API with custom assistants
- **Email Processing**: IMAP for inbound emails
- **Background Tasks**: FastAPI BackgroundTasks
- **Migrations**: Alembic
- **Validation**: Pydantic

## 📋 Prerequisites

- Python 3.13+
- PostgreSQL database
- OpenAI API key
- Email accounts for sending (IMAP/SMTP)

## 🚀 Quick Start

### 1. Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy the example environment file and configure:

```bash
cp env.example .env
```

Edit `.env` with your settings:

```env
# OpenAI Settings
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_ASSISTANT_ID_MAIL_GENERATOR=your_mail_generator_assistant_id
OPENAI_ASSISTANT_ID_ANSWER_GENERATOR=your_answer_generator_assistant_id

# Database Settings
DATABASE_URL=postgresql://username:password@localhost:5432/mailing_center
DATABASE_ECHO=false

# Email Campaign Settings
EMAIL_PAUSE_SECONDS=1.0
EMAIL_PAUSE_MIN_SECONDS=0.5
EMAIL_PAUSE_MAX_SECONDS=2.0
CAMPAIGN_FROM_EMAILS=email1@example.com,email2@example.com

# Mail API Settings
MAIL_API_URL=http://127.0.0.1:8001/email/send
MAIL_API_KEY=your_mail_api_key_here
```

### 3. Database Setup

```bash
alembic upgrade head
```

### 4. Run the Application

```bash
# Development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## 📚 API Documentation

### Interactive Documentation
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## 🎯 Main Endpoints

### Authentication

#### `POST /api/auth/login`
Exchange the shared dashboard password for a JWT access token. Every other
route (campaigns, B2B objects, sender accounts) requires it as a bearer
token — there's no per-user model, just one password gate behind a real
signed, expiring token instead of a boolean flag.

**Request Body:**
```json
{ "password": "..." }
```

**Response:**
```json
{ "access_token": "eyJ...", "token_type": "bearer" }
```

### Email Campaigns

#### `POST /api/emails/send`
Launch email campaign with provided studio list.

**Request Body:**
```json
[
  {
    "studio": {
      "place_id": "123",
      "title": "Studio Name",
      "type": "yoga_studio",
      "emails": ["studio@example.com"],
      "address": "Studio Address"
    },
    "parsing": false
  }
]
```

**Response:**
```json
{
  "queued": 1
}
```

#### `POST /api/emails/setup`
Launch email campaign with advanced configuration and object selection.

**Request Body:**
```json
{
  // ВИБІР ОБ'ЄКТІВ (mutually exclusive - тільки один варіант)
  
  // Варіант 1: Фільтрація по базі даних
  "country": "PL",                    // Країна для фільтрації
  "object_type": "yoga_studio",       // Тип об'єкта
  
  // Варіант 2: Конкретний список email адрес
  "emails": ["info@yoga.com", "contact@studio.pl"],
  
  // AI ПАРСИНГ
  "parsing": false,                   // Чи використовувати AI парсинг
  "parsing_prompt": "Extract key info", // Промт для парсингу (обов'язковий якщо parsing=true)
  
  // ГЕНЕРАЦІЯ ЛИСТІВ
  "subject_prompt": "Generate catchy subject", // Промт для генерації заголовку
  "body_prompt": "Create personalized body",    // Промт для генерації тіла листа
  
  // АВТО-ВІДПОВІДІ
  "auto_answering": false,            // Чи увімкнути авто-відповіді
  "reply_prompt": "Generate replies", // Промт для генерації відповідей (обов'язковий якщо auto_answering=true)
  
  // СТИЛЬ
  "tov": "friendly",                  // Тон голосу: "casual" | "friendly" | "professional" | "enthusiastic" | "sincere" | "playful"
  "style": "conversational",          // Стиль письма: "short" | "storytelling" | "question_centric" | "compliment_first" | "conversational" | "structured"
  
  // НАЛАШТУВАННЯ ВІДПРАВКИ
  "use_corporate": true,              // true = корпоративні email, false = приватні
  "daily_limit": 50,                  // Максимальна кількість листів на день
  "timezone": "+2"                    // Часова зона (наприклад: "+2", "-5")
}
```

**Validation Rules:**
1. **Mutually Exclusive Inputs:**
   - Або `emails` (список не порожній), або одночасно `country` + `object_type`
   - Не можна передавати обидва варіанти одночасно
   - Не можна не передавати жодного варіанту

2. **Required Prompts:**
   - Якщо `parsing = true` → обов'язковий `parsing_prompt` (непорожній рядок)
   - Якщо `auto_answering = true` → обов'язковий `reply_prompt` (непорожній рядок)

**Response (Success - 200):**
```json
{
  "message": "Campaign started successfully",
  "queued": 25,
  "filters": {
    "country": "PL",
    "object_type": "yoga_studio"
  },
  "settings": {
    "parsing": false,
    "auto_answering": false,
    "use_corporate": true,
    "tov": "friendly",
    "style": "conversational"
  }
}
```

**HTTP Status Codes:**
- `200` - Кампанія успішно запущена у фоновому режимі
- `422` - Validation Error (порушення правил валідації)
- `500` - Internal Server Error

**Важливо:**
- **Відповідь повертається одразу** після валідації та постановки в чергу
- **Реальна відправка відбувається у фоновому режимі**
- Для відстеження прогресу використовуйте `GET /api/emails/status`

#### `POST /api/emails/send-from-db`
Launch campaign from database B2B objects (legacy endpoint).

**Request Body:**
```json
{
  "count": 10,
  "parsing": false
}
```

**Response:**
```json
{
  "message": "Campaign queued from database",
  "count": 10,
  "parsing": false
}
```

#### `GET /api/emails/status`
Get current campaign status and progress.

**Response:**
```json
{
  "status": "running",
  "total": 100,
  "processed": 45,
  "successful": 42,
  "failed": 3,
  "progress_percent": 45.0,
  "started_at": "2024-01-15T10:30:00Z",
  "last_pause": 2.5
}
```

### B2B Object Management

#### `GET /api/b2b/`
List all B2B objects with pagination.

**Query Parameters:**
- `skip`: Number of records to skip (default: 0)
- `limit`: Maximum number of records (default: 100, max: 1000)

#### `POST /api/b2b/`
Create a new B2B object.

**Request Body:**
```json
{
  "place_id": "unique_id_123",
  "name": "Studio Name",
  "type": "yoga_studio",
  "email": "studio@example.com",
  "phone": "+1234567890",
  "website": "https://studio.com",
  "address": "123 Main St",
  "city": "Warsaw",
  "country": "Poland"
}
```

#### `GET /api/b2b/{place_id}`
Get specific B2B object by place_id.

#### `PUT /api/b2b/{place_id}`
Update B2B object.

#### `DELETE /api/b2b/{place_id}`
Delete B2B object.

#### `POST /api/b2b/search`
Search B2B objects with filters.

**Request Body:**
```json
{
  "query": "yoga",
  "type": "yoga_studio",
  "city": "Warsaw",
  "has_email": true,
  "skip": 0,
  "limit": 50
}
```

#### `GET /api/b2b/type/{obj_type}`
Get objects by type.

#### `GET /api/b2b/city/{city}`
Get objects by city.

#### `GET /api/b2b/with-email/`
Get objects that have email addresses.

#### `GET /api/b2b/stats/`
Get B2B objects statistics.

**Response:**
```json
{
  "total_count": 1500,
  "types": ["yoga_studio", "fitness_center", "spa"],
  "cities": ["Warsaw", "Krakow", "Gdansk"],
  "countries": ["Poland", "Germany", "Czech Republic"],
  "with_email_count": 1200
}
```

### Sender Accounts API

#### `GET /api/sender-accounts`
List all sender accounts.

**Query Parameters:**
- `active_only`: Filter by active accounts only (default: true)
- `server_id`: Filter by server ID ("1" or "2")

**Response:**
```json
[
  {
    "id": "uuid",
    "email": "sender@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "server_id": "1",
    "is_active": true,
    "mail_api_url_id": "uuid"
  }
]
```

#### `POST /api/sender-accounts`
Create a new sender account.

**Request Body:**
```json
{
  "email": "sender@example.com",
  "password": "app_password",
  "first_name": "John",
  "last_name": "Doe",
  "imap_host": "imap.example.com",
  "imap_port": 993,
  "imap_ssl": true,
  "server_id": "1",
  "mail_api_url_id": "uuid",
  "is_active": true
}
```

#### `GET /api/sender-accounts/{account_id}`
Get specific sender account by ID.

#### `PUT /api/sender-accounts/{account_id}`
Update sender account.

#### `DELETE /api/sender-accounts/{account_id}`
Delete sender account.

#### `GET /api/mail-api-urls`
List all mail API URLs.

#### `POST /api/mail-api-urls`
Create new mail API URL.

**Request Body:**
```json
{
  "name": "Personal",
  "url": "http://mail-sender-host:8000",
  "endpoint": "/email/send",
  "is_active": true
}
```

### Inbound Email Processing

#### `GET /api/inbound/queue`
List pending replies queued for sending.

#### `GET /api/inbound/history`
List sent replies history.

#### `GET /api/imap/blocklist`
Get current IMAP login blocklist status.

#### `POST /api/imap/unblock/{email}`
Manually unblock an IMAP account.

## 🗄️ Database Schema

### B2B Objects Table
```sql
CREATE TABLE b2b_objects (
    place_id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    type VARCHAR(100) NOT NULL,
    owner_name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    website VARCHAR(500),
    description TEXT,
    address TEXT,
    city VARCHAR(100),
    country VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## 👤 Sender Accounts Management

Sender accounts live in the database and are managed through the
`/api/sender-accounts` REST endpoints (see above). `scripts/update_sender_accounts_from_json.py`
is a one-off import helper for bootstrapping from a JSON export —
see `app/config/sender_accounts.example.json` for the expected shape
(the real file with live credentials is obviously not in this repo).

## 🔧 Configuration

### Email Settings
- `EMAIL_PAUSE_SECONDS`: Base delay between emails
- `EMAIL_PAUSE_MIN_SECONDS`: Minimum random delay
- `EMAIL_PAUSE_MAX_SECONDS`: Maximum random delay
- `CAMPAIGN_FROM_EMAILS`: Comma-separated list of sender emails

### Database Settings
- `DATABASE_URL`: PostgreSQL connection string
- `DATABASE_ECHO`: Enable SQL query logging

### AI Settings
- `OPENAI_API_KEY`: Your OpenAI API key
- `OPENAI_ASSISTANT_ID_MAIL_GENERATOR`: Assistant for email generation
- `OPENAI_ASSISTANT_ID_ANSWER_GENERATOR`: Assistant for reply processing

## 🚨 Rate Limits & Constraints

- Maximum objects per campaign: **1000**
- Minimum objects per campaign: **1**
- Only one campaign can run at a time
- Configurable email sending delays
- IMAP account blocking for failed logins

## 📊 Monitoring & Logging

- All operations are logged with structured logging
- Campaign progress tracking in real-time
- IMAP polling every 60 seconds
- Reply dispatch every 30 seconds
- Logs stored in `logs/app.log`

## 🧪 Testing

```bash
# Run test campaign
python test_database_campaign.py

# Test specific endpoints
curl -X GET "http://localhost:8000/api/emails/status"
curl -X GET "http://localhost:8000/api/b2b/stats/"
```

## 🔄 Background Processes

The application runs several background processes:

1. **IMAP Polling**: Checks for new incoming emails every 60 seconds
2. **Reply Dispatch**: Processes queued replies every 30 seconds
3. **Campaign Processing**: Handles email sending in background tasks

## 📝 Development

### Project Structure
```
mailing_center/
├── app/
│   ├── api/           # API endpoints
│   ├── core/          # Core utilities (exceptions, logger, settings)
│   ├── database/      # Database models and CRUD operations
│   ├── integrations/  # External service integrations (AI, email)
│   ├── models/        # Pydantic models
│   ├── schemas/       # API schemas
│   ├── services/      # Business logic services
│   └── utils/         # Utility functions
├── alembic/           # Database migrations
├── logs/              # Application logs
└── requirements.txt   # Python dependencies
```

### Adding New Features
1. Create models in `app/models/`
2. Add schemas in `app/schemas/`
3. Implement services in `app/services/`
4. Create API endpoints in `app/api/`
5. Add database migrations if needed

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For support and questions:
- Check the API documentation at `/docs`
- Review logs in `logs/app.log`
- Check database connection and migrations
- Verify environment variables are set correctly
