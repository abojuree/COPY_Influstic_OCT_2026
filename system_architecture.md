# System Architecture — Influencers Analytics Platform

## Architecture Overview

The platform is a **Flask monolith** deployed on a **Linux server** with **Gunicorn**, backed by **PostgreSQL**. It scrapes social media profiles via RapidAPI third-party endpoints, stores time-series analytics, and exposes a web dashboard for influencer discovery and campaign management.

```mermaid
graph TB
    subgraph "Linux Server"
        subgraph "Web Layer"
            NGINX["Nginx Reverse Proxy"]
            GUNICORN["Gunicorn (4 workers)"]
            FLASK["Flask Application"]
        end
        subgraph "Background Jobs"
            CRON["System Crontab"]
            SCAN["cron_scan.py"]
            BACKUP["db_backup.py"]
        end
        subgraph "Data Layer"
            PG["PostgreSQL"]
        end
    end
    subgraph "External Services"
        RAPID["RapidAPI Scrapers"]
        SMTP["SMTP Email"]
    end

    NGINX --> GUNICORN --> FLASK
    FLASK --> PG
    CRON --> SCAN --> FLASK
    CRON --> BACKUP --> PG
    FLASK --> RAPID
    SCAN --> SMTP
```

---

## Database Schema (ER Diagram)

```mermaid
erDiagram
    ROLES ||--o{ USERS : "assigned to"
    AGENCY ||--o{ USERS : "has"
    AGENCY ||--o{ SUBSCRIPTION : "bills"
    AGENCY ||--o{ CAMPAIGN : "manages"
    AGENCY ||--o{ FAVOURITE : "saves"
    PLAN ||--o{ SUBSCRIPTION : "defines rules for"
    CAMPAIGN ||--o{ SHORTLIST : "scopes"
    USERS ||--o{ SHORTLIST : "creates"
    USERS ||--o{ LOG : "generates"
    SHORTLIST }o--o{ INFLUENCER : "contains"
    FAVOURITE }o--|| INFLUENCER : "stars"
    INFLUENCER ||--o{ SOCIAL_ACCOUNT : "has accounts"
    INFLUENCER ||--o{ SOCIAL_POST : "authors"
    PLATFORM ||--o{ SOCIAL_ACCOUNT : "hosts"
    SOCIAL_ACCOUNT }o--o{ CONTENT : "categorized as"
    SOCIAL_ACCOUNT ||--o{ SCAN_RESULTS : "metrics history"
    SOCIAL_ACCOUNT ||--o{ SOCIAL_POST : "publishes"

    ROLES {
        int id PK
        string name "UK"
        string description
        boolean is_active
        json permissions
    }
    USERS {
        int id PK
        string username "UK"
        string email "UK"
        binary password
        string phone
        boolean is_active
        string role
        int role_id FK
        int agency_id FK
    }
    AGENCY {
        int id PK
        string name "UK"
        datetime created_at
    }
    PLAN {
        int id PK
        string name "UK"
        int tracking_limit
        int campaign_limit
        float price
        boolean is_active
        datetime created_at
    }
    SUBSCRIPTION {
        int id PK
        int agency_id FK
        int plan_id FK
        string status
        datetime start_date
        datetime current_period_end
    }
    CAMPAIGN {
        int id PK
        int agency_id FK
        string name
        string status
        string target_platform
        string objective
        text keywords
        datetime created_at
        datetime updated_at
    }
    SHORTLIST {
        int id PK
        int campaign_id FK
        int created_by FK
        string name
        text description
        datetime created_at
    }
    FAVOURITE {
        int id PK
        int agency_id FK
        int influencer_id FK
        datetime created_at
    }
    INFLUENCER {
        int id PK
        string full_name "UK"
        string gender
        string country
        string city
        string phone
        string email
        string category
        text profile_picture
        date creation_date
        time creation_time
        int created_by FK
    }
    PLATFORM {
        int id PK
        string name "UK"
        string name_english "UK"
        date creation_date
        time creation_time
        int created_by FK
    }
    SOCIAL_ACCOUNT {
        int id PK
        int influencer_id FK
        int platform_id FK
        string username "UK_COMPOSITE"
        string public_profile_name
        text bio_text
        text profile_picture
        string external_url
        int followers
        int total_likes
        int total_posts
        string category
        date creation_date
        time creation_time
        int created_by FK
    }
    SOCIAL_POST {
        int id PK
        int influencer_id FK
        int socialaccount_id FK
        string platform_post_id "UK"
        datetime posted_at
        int plays
        int likes
        int comments
        int shares
        int saves
        text caption
        json raw_data
    }
    CONTENT {
        int id PK
        string name "UK"
        string description
        date creation_date
        time creation_time
        int created_by FK
    }
    SCAN_RESULTS {
        int id PK
        int socialaccount_id FK
        int followers
        int likes
        int posts
        date creation_date
        time creation_time
        string time_taken
    }
    SCAN_LOG {
        int id PK
        json success_count
        json failure_count
        json failures
        date creation_date
        time creation_time
        string time_taken
    }
    LOG {
        int id PK
        string log_text
        string user_ip
        date creation_date
        time creation_time
        int created_by FK
    }
```

---

### Comprehensive Data Dictionary

| Table Name | Description | Key Fields & Constraints | Relationships |
|---|---|---|---|
| **`roles`** | Custom RBAC role definitions with granular JSON permissions matrix. | `id` (PK), `name` (UK), `is_active`, `permissions` (JSON) | Has many `Users` (`role_id`) |
| **`Users`** | Authenticated platform users (admins, employee users, agency client users). | `id` (PK), `username` (UK), `email` (UK), `role_id` (FK), `agency_id` (FK), `is_active`, `phone` | Belongs to `Agency`, `Role`. Has many `Log` |
| **`agencies`** | Paying tenant organizations in multi-tenant SaaS architecture. | `id` (PK), `name` (UK), `created_at` | Has many `Users`, `Subscription`, `Campaign`, `Favourite` |
| **`plans`** | Subscription tier definitions (limits, pricing). | `id` (PK), `name` (UK), `tracking_limit`, `campaign_limit`, `price`, `is_active` | Has many `Subscription` |
| **`subscriptions`** | Active billing status and cycle dates for an agency. | `id` (PK), `agency_id` (FK), `plan_id` (FK), `status`, `current_period_end` | Belongs to `Agency`, `Plan` |
| **`campaigns`** | Multi-campaign container for influencers and agency objectives. | `id` (PK), `agency_id` (FK), `name`, `status`, `target_platform`, `objective`, `keywords` | Belongs to `Agency`. Has many `Shortlist` |
| **`shortlists`** | Saved collections of influencers scoped to a specific campaign. | `id` (PK), `campaign_id` (FK), `created_by` (FK), `name`, `description` | Belongs to `Campaign`, `Users`. Many-to-Many with `Influencer` |
| **`shortlist_influencer`** | Junction table for `shortlists` and `influencers`. | `shortlist_id` (PK, FK), `influencer_id` (PK, FK) | Cascade deletes on shortlist or influencer deletion |
| **`favourites`** | Globally saved favourite influencers per agency independent of campaigns. | `id` (PK), `agency_id` (FK), `influencer_id` (FK) | Belongs to `Agency`, `Influencer` |
| **`influencers`** | Global database of social media influencer entities. | `id` (PK), `full_name` (UK), `gender`, `country`, `city`, `phone`, `email`, `profile_picture` | Has many `SocialAccount`, `SocialPost`, `Favourite`. M2M `Shortlist` |
| **`platforms`** | Supported social media channels (TikTok, Instagram, Snapchat). | `id` (PK), `name` (UK), `name_english` (UK) | Has many `SocialAccount` |
| **`socialaccounts`** | Platform-specific profiles belonging to an influencer. | `id` (PK), `influencer_id` (FK), `platform_id` (FK), `username`, Unique(`username`, `platform_id`), `followers`, `total_likes`, `total_posts`, `category` | Belongs to `Influencer`, `Platform`. Has many `SocialPost`, `ScanResults`. M2M `Content` |
| **`socialaccount_content`** | Junction table for `socialaccounts` and `contents`. | `socialaccount_id` (PK, FK), `content_id` (PK, FK) | Categorizes social accounts by niche/content type |
| **`social_posts`** | Individual scraped posts for deep analytics & engagement calculations. | `id` (PK), `influencer_id` (FK), `socialaccount_id` (FK), `platform_post_id` (UK), `plays`, `likes`, `comments`, `shares`, `saves`, `raw_data` (JSON) | Belongs to `Influencer`, `SocialAccount` |
| **`contents`** | Niche & content category tags (e.g. Fashion, Tech, Gaming). | `id` (PK), `name` (UK), `description` | M2M `SocialAccount` |
| **`scanresults`** | Time-series historical snapshot of followers, likes, and post counts. | `id` (PK), `socialaccount_id` (FK), `followers`, `likes`, `posts`, `creation_date`, `time_taken` | Belongs to `SocialAccount` |
| **`scanlog`** | Execution audit trail for background cron scraper batches. | `id` (PK), `success_count` (JSON), `failure_count` (JSON), `failures` (JSON), `creation_date` | Scraper job audit log |
| **`log`** | User action audit log (auth, exports, edits). | `id` (PK), `log_text`, `user_ip`, `created_by` (FK), `creation_date` | Belongs to `Users` |

---

## SaaS Multi-Tenancy Architecture

The platform uses an **Agency-based multi-tenancy** model:

| Layer | Table | Purpose |
|---|---|---|
| **Tenant** | `agencies` | Represents a paying company/agency |
| **Identity** | `Users` | Each user belongs to exactly one agency via `agency_id` |
| **Billing** | `subscriptions` | Tracks plan tier, tracking limits, and billing status |
| **Campaigns** | `shortlists` | Agencies save influencer selections for campaign planning |
| **Data Isolation** | All queries | Filter by `agency_id` to prevent cross-tenant data leakage |

### Subscription Enforcement Flow

```mermaid
sequenceDiagram
    participant Agency
    participant App as Flask App
    participant DB as PostgreSQL

    Agency->>App: Request to track new influencer
    App->>DB: SELECT tracking_limit FROM subscriptions WHERE agency_id = ?
    App->>DB: SELECT COUNT(*) FROM shortlist_influencer WHERE shortlist_id IN (agency shortlists)
    alt Under limit
        App->>DB: INSERT INTO shortlist_influencer
        App-->>Agency: Success
    else Over limit
        App-->>Agency: Error: Tracking limit reached. Upgrade your plan.
    end
```

---

## Scraping Pipeline

```mermaid
sequenceDiagram
    participant Trigger as Trigger (Cron/UI/Scheduler)
    participant Scan as scan_database()
    participant Pool as ThreadPoolExecutor
    participant Worker as process_username()
    participant API as RapidAPI
    participant DB as PostgreSQL

    Trigger->>Scan: Start scan
    Scan->>DB: Query all SocialAccounts
    Scan->>Pool: Submit workers (round-robin by platform)
    Pool->>Worker: Execute in thread
    Worker->>API: GET/POST profile data
    API-->>Worker: JSON response
    Worker->>DB: UPDATE SocialAccount (display data)
    Worker->>DB: INSERT ScanResults (if metrics changed)
    Worker-->>Pool: Done
    Pool-->>Scan: All futures complete
    Scan->>DB: INSERT ScanLog (success/failure counts)
    Scan->>DB: Cleanup old ScanLogs (keep 3)
```

---

## Calculated Metrics & KPIs

The platform computes several key performance indicators (KPIs) and metrics for both system administration and influencer analytics.

### System & Admin KPIs
| Metric | Calculation Method | Purpose |
|---|---|---|
| **Total API Calls / Scans** | `sum(ScanLog.success_count) + sum(ScanLog.failure_count)` for a given date range. | Tracks total usage against third-party RapidAPI limits. |
| **Scraper Success Rate** | `(Total Successful Scans / Total API Calls) * 100` | Monitors the health and reliability of background cron scrapers and external APIs. |
| **Quota Used (Influencers)** | Count of unique `influencer_id` values across all `Shortlist` records belonging to an `Agency`'s Campaigns. | Validates if a tenant (Agency) is within their Subscription `tracking_limit`. |
| **Platform Distribution** | Grouping and counting `SocialAccount` records by `platform_id`. | Shows which social media platforms dominate the database. |

### Influencer Profile Metrics
These metrics are calculated dynamically for SaaS users when viewing an Influencer's profile (`influencer_detail` route) based on the latest scraped data:

| Metric | Calculation Method | Purpose |
|---|---|---|
| **Followers / Total Likes** | Directly mapped and stored in `SocialAccount` during scraping (`profile_data['followers_count']`). | Provides top-level account popularity. |
| **Average Views** | `sum(plays) / count(plays)` across all valid `SocialPost` records linked to the account. | Estimates reach of a typical post. |
| **Average Likes** | `sum(likes) / count(likes)` across all valid `SocialPost` records. | Evaluates direct content appreciation. |
| **Average Comments** | `sum(comments) / count(comments)` across all valid `SocialPost` records. | Evaluates conversational engagement. |
| **Average Interactions** | `Average Likes + Average Comments` | A unified metric representing active user interaction with the influencer's recent content. |

---

## Deployment Architecture

### Previous (Render.com)
- Web service + Cron service + Managed PostgreSQL
- Configured via `render.yaml`

### Current (Linux Server)
- **Web**: `systemd` service running Gunicorn → see `deploy/socialscannerw.service`
- **Cron Jobs**: System crontab → see `deploy/crontab`
  - Scan: Every 2 days at 06:00 AM
  - Backup: Daily at 03:00 AM
  - Log rotation: Weekly
- **Database**: Self-managed PostgreSQL
- **Reverse Proxy**: Nginx (recommended, not included in repo)

---

## Key File Reference

| File | Purpose |
|---|---|
| `run.py` | Dev entry point with APScheduler |
| `wsgi.py` | Production WSGI entry point |
| `tasks.py` | Background scanning engine |
| `cron_scan.py` | Standalone cron job for scans |
| `db_backup.py` | PostgreSQL backup via pg_dump |
| `email_utils.py` | SMTP notifications |
| `apps/config.py` | Flask configuration |
| `apps/home/util.py` | Platform scraper functions |
| `apps/saas/models.py` | SaaS tenant models |
| `.agents/AGENTS.md` | Agent reference documentation |
