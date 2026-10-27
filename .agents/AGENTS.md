# Influencers Analytics Platform — Agent Reference

This document provides comprehensive architecture and technical details
for AI agents working on this codebase.

## System Overview

A **Flask monolith** that scrapes social media profiles (Instagram, TikTok, Snapchat),
stores analytics snapshots, and exposes a web dashboard for influencer discovery.
The platform is designed as a **multi-tenant SaaS** product for marketing agencies.

**Tech Stack:**
- **Backend**: Flask 2.x, SQLAlchemy (Flask-SQLAlchemy), Flask-Login, Flask-Migrate (Alembic)
- **Database**: PostgreSQL (production), SQLite (local dev fallback)
- **Deployment**: Linux server with systemd + crontab (see `deploy/`)
- **Background Jobs**: `ThreadPoolExecutor` in `tasks.py`, system crontab via `cron_scan.py`
- **Scraping**: RapidAPI third-party endpoints (NOT official APIs)

---

## Project Structure

```
├── apps/                       # Flask application package
│   ├── __init__.py             # App factory: create_app(), db, login_manager
│   ├── config.py               # Configuration classes (Debug/Production)
│   ├── admin/                  # Admin utilities (db_utils.py for backups/exports)
│   ├── authentication/         # User auth: login, register, admin dashboard, scan control
│   │   ├── models.py           # Users model (with agency_id FK for multi-tenancy)
│   │   ├── routes.py           # Auth routes + admin scan/backup endpoints
│   │   ├── forms.py            # WTForms for login/register
│   │   └── util.py             # Password hashing, admin creation, decorators
│   ├── content_types/          # Content category management
│   │   ├── models.py           # Content model
│   │   └── routes.py           # CRUD for content categories
│   ├── globals/                # Shared utilities
│   │   ├── routes.py           # Excel import/export, photo serving, DB backup
│   │   └── util.py             # download_excel(), import_content_from_excel()
│   ├── health/                 # Health check endpoint
│   │   └── routes.py           # /health route for monitoring
│   ├── home/                   # Dashboard and search
│   │   ├── models.py           # Log model (activity audit trail)
│   │   ├── routes.py           # Dashboard, search, profile detail pages
│   │   └── util.py             # Platform scraper functions + get_summerized_report()
│   ├── profiles/               # Influencer profile management
│   │   ├── models.py           # Influencer model
│   │   └── routes.py           # CRUD for influencer profiles
│   ├── reports/                # Reporting and analytics
│   │   ├── models.py           # ScanResults, ScanLog models
│   │   └── routes.py           # Scan results, scan logs, content reports, daily report
│   ├── saas/                   # SaaS multi-tenancy layer
│   │   ├── __init__.py         # Blueprint placeholder
│   │   └── models.py           # Agency, Subscription, Shortlist models
│   ├── social/                 # Social account management
│   │   ├── models.py           # Platform, SocialAccount, SocialAccount_Content models
│   │   └── routes.py           # CRUD for social accounts
│   ├── static/                 # CSS, JS, images, profile pictures
│   └── templates/              # Jinja2 templates
├── tasks.py                    # Background scanning engine (ThreadPoolExecutor)
├── cron_scan.py                # Standalone cron job for scheduled scans
├── db_backup.py                # pg_dump backup utility
├── email_utils.py              # Email notifications for scan failures
├── ic_config.py                # icecream debug logging configuration
├── run.py                      # Development entry point (APScheduler)
├── wsgi.py                     # Production WSGI entry point (Gunicorn)
├── deploy/                     # Linux deployment configs
│   ├── socialscannerw.service  # systemd service file
│   ├── crontab                 # System crontab for scheduled jobs
│   └── README.md               # Deployment instructions
├── migrations/                 # Alembic migration scripts
├── tools/                      # Developer utility scripts
└── tests/                      # Test scripts
```

---

## Database Schema

### Entity-Relationship Summary

```
Agency (1) ──── (N) Users
Agency (1) ──── (N) Subscription
Plan (1) ──── (N) Subscription
Agency (1) ──── (N) Shortlist
Shortlist (M) ──── (N) Influencer       [via shortlist_influencer]
Influencer (1) ──── (N) SocialAccount
SocialAccount (M) ──── (N) Content      [via socialaccount_content]
SocialAccount (1) ──── (N) ScanResults
Platform (1) ──── (N) SocialAccount
Users (1) ──── (N) Log
```

### Core Tables

| Table | Purpose | Key Columns |
|---|---|---|
| `agencies` | SaaS tenant (paying company) | `id`, `name` (unique), `created_at` |
| `Users` | Authenticated users | `id`, `username`, `email`, `password`, `agency_id` (FK → agencies) |
| `plans` | Subscription plan definitions | `id`, `name` (unique), `tracking_limit`, `price`, `is_active`, `created_at` |
| `subscriptions` | Active agency subscription tracking | `id`, `agency_id` (FK), `plan_id` (FK → plans), `status`, `start_date`, `current_period_end` |
| `shortlists` | Saved influencer lists for campaigns | `id`, `agency_id` (FK), `created_by` (FK → Users), `name`, `description` |
| `shortlist_influencer` | M2M junction: Shortlist ↔ Influencer | `shortlist_id` (FK), `influencer_id` (FK) |
| `influencers` | Human profiles | `id`, `full_name` (unique), `gender`, `country`, `city`, `phone`, `email`, `profile_picture` |
| `socialaccounts` | Platform-specific handles | `id`, `influencer_id` (FK, indexed), `platform_id` (FK, indexed), `username`, `followers`, `likes`, `posts`, `bio_text`, `profile_picture` |
| `platforms` | Platform registry | `id`, `name`, `name_english` |
| `contents` | Content categories/niches | `id`, `name` (unique), `description` |
| `socialaccount_content` | M2M junction: SocialAccount ↔ Content | `socialaccount_id` (FK), `content_id` (FK) |
| `scanresults` | Time-series metrics snapshots | `id`, `socialaccount_id` (FK, indexed), `followers`, `likes`, `posts`, `creation_date`, `creation_time`, `time_taken` |
| `scanlog` | Scan execution logs (keeps last 3) | `id`, `success_count` (JSON), `failure_count` (JSON), `failures` (JSON), `time_taken` |
| `log` | User activity audit trail | `id`, `log_text`, `created_by` (FK → Users), `user_ip` |

### Design Decisions

- **ScanResults stores ONLY numerical metrics** — `bio_text`, `profile_picture`, `public_profile_name`, and `external_url` live on `SocialAccount` to avoid 365x/year duplication.
- **ScanLog cleanup** keeps only the 3 most recent entries via `cleanup_old_scanlogs()`.
- **ScanResults has NO automatic cleanup** — a data retention policy should be implemented.
- **agency_id on Users is nullable** — allows the existing admin account to work without an agency during the transition period.

---

## Scraping Pipeline

### How Scans Work

1. **Trigger**: Either the web UI (`/admin/start_scan`), APScheduler (`run.py`), or crontab (`cron_scan.py`).
2. **Orchestrator**: `scan_database()` in `tasks.py` queries all `SocialAccount` rows, interleaves them by platform (round-robin), and submits each to a `ThreadPoolExecutor`.
3. **Worker**: `process_username()` runs in its own app context with a thread-scoped DB session:
   - Calls `search_user_profile()` which dispatches to `tiktok()`, `snapchat()`, or `instagram()` based on `platform.name_english`.
   - Updates the canonical `SocialAccount` row with current display data.
   - Inserts a `ScanResults` row if the metrics have changed.
4. **Logging**: After all futures complete, a `ScanLog` row is created with per-platform success/failure counts.
5. **Email Alerts**: `cron_scan.py` checks failure rates and sends email notifications if a platform exceeds 50% failure.

### Platform Scraper Functions (apps/home/util.py)

| Function | API Endpoint | Notes |
|---|---|---|
| `tiktok()` | `tiktok-scraper2.p.rapidapi.com` | Uses `http.client` directly |
| `snapchat()` | `snapchat-scraper2.p.rapidapi.com` | Uses `requests.get()` |
| `instagram()` | `instagram-scraper-ai2.p.rapidapi.com` | Uses `requests.post()` |

**⚠️ Critical**: All API keys are currently hardcoded as `"YOUR_RAPIDAPI_KEY_HERE"`. These MUST be moved to environment variables before production use.

### Legacy Scrapers

The file contains `tiktok_old()`, `snapchat_old()`, `snapchat_old2()`, `instagram_old()`, `instagram_old2()` — these are deprecated iterations kept for reference. Only the un-suffixed functions are active.

---

## Blueprint Routing

| Blueprint | URL Prefix | Primary Responsibility |
|---|---|---|
| `authentication_blueprint` | `/` | Login, register, logout, admin dashboard, scan control, backup/export |
| `home_blueprint` | `/home` | Dashboard, profile search, profile detail |
| `profiles_blueprint` | `/profiles` | Influencer CRUD, influencer detail/edit |
| `social_blueprint` | `/social` | SocialAccount CRUD, platform management |
| `content_types_blueprint` | `/content` | Content category CRUD |
| `reports_blueprint` | `/reports` | Scan results, scan logs, content report, daily report |
| `globals_blueprint` | `/globals` | Excel import/export, photo serving, DB backup |
| `health_blueprint` | `/health` | Health check endpoint |

---

## Configuration

### Environment Files

| File | Purpose |
|---|---|
| `.env.dev` | Local development database credentials |
| `.env.prod` | Production database credentials |

### Key Environment Variables

| Variable | Description |
|---|---|
| `FLASK_ENV` | `development` or `production` |
| `DEBUG_MODE` | `True` or `False` |
| `DB_ENGINE` | Database engine (e.g., `postgresql`) |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USERNAME`, `DB_PASS` | Database connection |
| `SCHEDULER_API_ENABLED` | Enable/disable APScheduler |
| `SCHEDULER_TRIGGER_HOUR`, `SCHEDULER_TRIGGER_MINUTE` | APScheduler scan trigger time |
| `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` | Email notification config |
| `SENDER_EMAIL`, `NOTIFICATION_EMAILS` | Email sender and recipients |

---

## Known Limitations & External Dependencies

1. **RapidAPI Dependency**: All scraping relies on third-party RapidAPI endpoints that can break when platforms update their anti-bot measures.
2. **No Rate Limiting**: The scanning pipeline has no built-in rate limiting for API calls.
3. **Hardcoded API Keys**: `"YOUR_RAPIDAPI_KEY_HERE"` appears in `apps/home/util.py` — must be moved to env vars.
4. **No ScanResults Retention Policy**: The `scanresults` table grows monotonically. A cleanup job should be added.
5. **pgdumplib Import**: `apps/globals/routes.py` imports `pgdumplib` at the module level, which will fail if the library is not installed.
6. **PostgreRenderCert Import**: `apps/authentication/routes.py` imports `PostgreRenderCert` which may need updating for the new Linux deployment.
7. **Arabic UI**: The interface is primarily in Arabic (RTL layout). All flash messages and UI strings are in Arabic.

---

## Deployment (Linux Server)

The system deploys on a Linux server with:
- **Gunicorn** behind a reverse proxy (nginx recommended)
- **systemd** service for process management (see `deploy/socialscannerw.service`)
- **crontab** for scheduled scans (see `deploy/crontab`)
- **PostgreSQL** as the production database

See `deploy/README.md` for setup instructions.
