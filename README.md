# Fitness Performance Tracker

![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?logo=postgresql&logoColor=white)
![Status](https://img.shields.io/badge/Status-Backend%20MVP-orange)

A FastAPI and PostgreSQL backend for tracking fitness progress across users, goals, exercises, and workouts.

## Overview

The project follows a layered architecture:

- `routers/` exposes HTTP endpoints
- `services/` applies business rules and ownership checks
- `repositories/` handles SQL and persistence
- `schemas/` defines request and response contracts

The live API currently covers:

- authentication and user profile management
- goal creation and lifecycle updates
- exercise library management with visibility rules
- workout logging, listing, updating, and deletion

The database schema is already prepared for future nutrition and body-tracking slices such as meals, body-weight entries, measurements, and progress photos.

## Current Status

This repository is in an API-first backend phase.

- live and routed today: users, goals, exercises, workouts
- implemented in the schema and repository layer, but not yet exposed end-to-end: meals, meal items, body-weight entries, body measurements, progress photos, workout exercises, set entries, workout templates
- `frontend/` is still a placeholder for later work

## Current Features

- JWT-based authentication with access and refresh tokens
- OAuth2-compatible `POST /users/token` endpoint for Swagger UI and password-flow clients
- authenticated profile read, update, avatar, password-change, and account-deletion flows
- goal creation, history lookup, activation, and deactivation
- exercise CRUD with filtering and built-in vs custom visibility handling
- workout CRUD with pagination, free-text search, and date-range filters
- database bootstrap script in `data/init_db.py`
- rerunnable Postman collection for users, goals, and exercises

## Tech Stack

- Python 3.13+
- FastAPI
- Pydantic v2
- PostgreSQL
- `psycopg`
- `python-jose`
- `passlib[bcrypt]`
- `python-dotenv`
- Ruff

## Project Structure

```text
Fitness-Performance-Tracker/
|-- auth/               # password hashing and JWT helpers
|-- core/               # configuration and app-level errors
|-- data/               # DB connection helpers, schema, init script, seed hook
|-- dependencies/       # FastAPI dependency providers and auth deps
|-- docs/               # docs assets such as the ERD image
|-- postman/            # manual API testing collection
|-- repositories/       # SQL repositories per domain
|-- routers/            # API route modules
|-- schemas/            # Pydantic request and response models
|-- services/           # business logic layer
|-- tests/              # test placeholder
|-- utils/              # environment and validation helpers
`-- main.py             # FastAPI application entrypoint
```

## Architecture

```text
HTTP Request
  -> Router
  -> Service
  -> Repository
  -> PostgreSQL
```

Each layer has a focused responsibility:

- routers translate HTTP requests into application calls
- services enforce rules such as ownership, visibility, and validation
- repositories execute SQL and return mapped domain data
- schemas validate request and response payloads

## Database Model

The schema in `data/schema.sql` defines tables for:

- users
- user goals
- exercises
- workouts
- workout exercises
- set entries
- workout templates
- workout template exercises
- meals
- meal items
- body weight entries
- body measurements
- progress photos

The current API exposes only the users, goals, exercises, and workouts slices, but the rest of the schema is already in place for future routes and services.

## Getting Started

### Prerequisites

- Python 3.13+
- PostgreSQL
- `pip`

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd Fitness-Performance-Tracker
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create the PostgreSQL database

Example:

```sql
CREATE DATABASE fitness_performance_tracker;
```

### 5. Configure environment variables

Use `.env.example` as a starting point and create a `.env` file in the project root:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=fitness_performance_tracker
DB_USER=postgres
DB_PASSWORD=your_password_here

LOG_LEVEL=DEBUG
JWT_SECRET_KEY=replace_with_a_long_random_secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### 6. Initialize the database schema

Run the bootstrap script:

```bash
python -m data.init_db
```

Useful options:

- `python -m data.init_db --no-reset` keeps the existing `public` schema and reapplies `schema.sql`
- `python -m data.init_db --no-seed` skips `seed.sql`

If you prefer, you can still apply the schema manually with `psql`.

### 7. Run the API

```bash
uvicorn main:app --reload
```

Open:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Root endpoint: `http://127.0.0.1:8000/`

## API Surface

### Public Endpoints

- `GET /`
- `POST /users/register`
- `POST /users/login`
- `POST /users/token`
- `POST /users/refresh`

### Authenticated User Endpoints

- `GET /users/me`
- `PATCH /users/me`
- `PATCH /users/me/avatar`
- `POST /users/me/change-password`
- `DELETE /users/me`

### Goal Endpoints

- `POST /goals/`
- `GET /goals/current`
- `GET /goals/history`
- `GET /goals/{goal_id}`
- `PATCH /goals/{goal_id}`
- `POST /goals/{goal_id}/activate`
- `POST /goals/{goal_id}/deactivate`

### Exercise Endpoints

- `POST /exercises/`
- `GET /exercises/`
- `GET /exercises/{exercise_id}`
- `PATCH /exercises/{exercise_id}`
- `DELETE /exercises/{exercise_id}`

`GET /exercises/` supports:

- `limit`
- `offset`
- `search`
- `muscle_group`
- `equipment`
- `is_compound`
- `is_custom`

### Workout Endpoints

- `POST /workouts/`
- `GET /workouts/`
- `GET /workouts/{workout_id}`
- `PATCH /workouts/{workout_id}`
- `DELETE /workouts/{workout_id}`

`GET /workouts/` supports:

- `search`
- `limit`
- `offset`
- `date_from`
- `date_to`

## Manual Testing

A Postman collection is included at `postman/Fitness-Performance-Tracker.postman_collection.json`.

It currently covers:

- health check
- users
- goals
- exercises

The collection is designed to be rerunnable:

- users are registered with randomized usernames and emails
- exercises are created with randomized names
- password changes are reverted at the end of the user flow

Workout endpoints are available in Swagger UI, but they are not yet represented in the Postman collection.

## Database Diagram

The schema is defined in `data/schema.sql`, and the current ERD is included below.

![Database Diagram](docs/images/database-diagram.png)

## Development Notes

- The app currently exposes API routes only.
- Automated tests are not implemented yet; current verification is mainly through Swagger UI and the Postman collection.
- Ruff configuration is defined in `pyproject.toml`.
- `data/init_db.py` is the quickest way to reset and rebuild the database during local development.

## Roadmap

- add workout exercises and set-entry API layers
- add nutrition endpoints for meals and meal items
- expose body-weight, measurement, and progress-photo tracking
- add automated tests
- expand the Postman collection to cover workouts
- expand documentation and diagrams

## Inspiration

The README structure was inspired by these templates:

- [Louis3797 / awesome-readme-template](https://github.com/Louis3797/awesome-readme-template)
- [othneildrew / Best-README-Template](https://github.com/othneildrew/Best-README-Template)
