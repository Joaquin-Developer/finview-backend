# AGENTS.md - Finview Backend

## Project Overview

FastAPI-based backend for Finview expense tracking app. Provides REST API for expense management and purchase tracking (shopping cart + shopping lists).

## Relationship with Frontend

- **Frontend URL**: `http://localhost:5173`
- **Frontend Repo**: Separate repo (`finview-frontend`)
- **API Base**: `/api/v1`
- **CORS**: Currently configured for `localhost:5173` and `localhost:3000`

## Commands

```bash
# Development
cp .env.development .env
uvicorn app.main:app --reload --port 8000

# Production
cp .env.production .env
# Edit .env with production values
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Environment Variables

Create a `.env` file (copy from `.env.development` or `.env.production`).

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | MySQL connection string | Yes |
| `SECRET_KEY` | JWT secret key | Yes |
| `CORS_ORIGINS` | Comma-separated list of allowed origins | No |
| `GEMINI_API_KEY` | Google Gemini API key | No |
| `GROQ_API_KEY` | Groq API key | No |
| `UPLOAD_DIR` | Directory for file uploads | No |
| `MAX_FILE_SIZE_MB` | Max file size in MB | No |

### Environment Files

- `.env.default` - Template with all variables (committed to repo)
- `.env.development` - Local development values (gitignored)
- `.env.production` - Production template with empty values (committed to repo)

**Setup for development:**
```bash
cp .env.development .env
```

## Project Structure

```
app/
├── main.py           # FastAPI app entry point, CORS config, router registration
├── config.py         # Configuration (DB URL, etc.)
├── database.py       # SQLAlchemy engine and session
├── dependencies.py   # Auth dependencies (get_current_user)
├── models/          # SQLAlchemy models
│   ├── user.py
│   ├── purchase.py   # Purchase (cart, lists, categories)
│   └── ...
├── routers/          # API endpoints
│   ├── auth.py
│   ├── purchase.py   # Purchase module endpoints
│   └── ...
├── schemas/         # Pydantic schemas (request/response models)
│   └── purchase.py
└── services/        # Business logic
```

## Database

- **Engine**: MySQL (local)
- **ORM**: SQLAlchemy
- **Migrations**: Alembic (see `alembic/versions/`)

### Key Tables

| Table | Description |
|-------|-------------|
| `users` | User accounts |
| `purchase_carts` | Shopping carts (active/completed) |
| `purchase_cart_items` | Items in carts |
| `purchase_lists` | Shopping lists (planning) |
| `purchase_list_items` | Items in lists |
| `purchase_categories` | Categories for purchases |

## Purchase Module (Módulo de Compras)

Independent from expense tracking. Uses `purchase_` prefix for all tables.

### Business Logic (shared with Frontend)

1. **Shopping Cart**: Only 1 active cart at a time per user
2. **Shopping Lists**: User can have N lists for pre-shopping planning
3. **Categories**: Independent from expense categories, manually created
4. **Flow**: Add items from list → checkbox prompts for price/quantity → adds to cart

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/purchase/categories` | List categories |
| POST | `/purchase/categories` | Create category |
| GET | `/purchase/carts` | List carts (with pagination) |
| GET | `/purchase/carts/active` | Get active cart |
| POST | `/purchase/carts` | Create cart |
| GET | `/purchase/carts/{id}` | Get cart details |
| POST | `/purchase/carts/{id}/items` | Add item to cart |
| POST | `/purchase/carts/{id}/complete` | Complete cart |
| GET | `/purchase/lists` | List shopping lists |
| POST | `/purchase/lists` | Create shopping list |
| GET | `/purchase/lists/{id}` | Get list details |
| POST | `/purchase/lists/{id}/items/{item_id}/add-to-cart/{cart_id}` | Add single item to cart |
| GET | `/purchase/stats` | Get purchase statistics |

## Naming Conventions

- **Models**: `PascalCase` (e.g., `PurchaseCart`)
- **Schemas**: `PascalCase` with `Schema` suffix (e.g., `PurchaseCartCreate`)
- **Routers**: `snake_case` (e.g., `purchase.py`)
- **Database tables**: `snake_case` with prefixes (e.g., `purchase_carts`)
- **UUIDs**: Use `UUID` type, store as strings

## Auth

- JWT-based authentication
- Dependencies: `get_current_user`, `CurrentUserDep`

## Adding New Endpoints

1. Create/update model in `app/models/`
2. Create/update schema in `app/schemas/`
3. Add router in `app/routers/` or extend existing
4. Register router in `app/main.py`

## Linting & Type Checking

```bash
# Run any linting tools if configured
```

## Notes

- All monetary values stored as floats
- Timestamps use UTC
- Purchase module is independent from transaction/expense module
