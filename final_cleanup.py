import os
import re

# 1. Clean up the files
files_to_remove = [
    "convert_mermaid.py", "download_diagrams.py", "download_diagram_pako.py",
    "replace_with_ascii.py", "restore.py", "fix_mermaid_syntax.py",
    "temp_arch.md", "temp_er.md", "diagram_1.png", "diagram_3.png", "diagram_4.png",
    "add_category.py"
]

for f in files_to_remove:
    path = os.path.join(os.getcwd(), f)
    if os.path.exists(path):
        os.remove(path)

# 2. Re-write the original mermaid diagrams to system_architecture.md
arch_mermaid = """```mermaid
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
```"""

er_mermaid = """```mermaid
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
```"""

md_path = "../system_architecture.md"
with open(md_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the first ASCII block with the Mermaid Arch graph
content = re.sub(r'```text\n \+---------------------------------------------------------------------------------\+.*?```', arch_mermaid, content, flags=re.DOTALL)

# Replace the second ASCII block with the Mermaid ER graph
content = re.sub(r'```text\n\+-------------------\+       \+-------------------\+       \+-------------------\+.*?```', er_mermaid, content, flags=re.DOTALL)

with open(md_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Restored original schema and diagrams and deleted temp files!")
