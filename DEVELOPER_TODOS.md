# Developer To-Dos & Implementation Plan: Platform Fixes & Feature Enhancements

This document outlines the detailed developer tasks, root-cause analyses, file locations, code modifications, and verification plans required to address the fixes and enhancements for both the **Admin** module and the **Influencers / Client** user interface.

---

## Task Summary Matrix

| ID | Category | Feature / Fix Point | Core Files Affected | Priority |
|---|---|---|---|---|
| **ADM-01** | Admin | Fix Scraping Errors & Resiliency | [tasks.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/tasks.py), [apps/home/util.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/home/util.py), [cron_scan.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/cron_scan.py) | High |
| **ADM-02** | Admin | System Role-Based Access Control (RBAC) | [apps/authentication/models.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/authentication/models.py), [apps/authentication/util.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/authentication/util.py) | High |
| **ADM-03** | Admin | Manual Account Creation, Role Assignment & Settings | [apps/authentication/routes.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/authentication/routes.py), [apps/templates/accounts/users.html](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/templates/accounts/users.html) | High |
| **ADM-04** | Admin | Fix Database Exporting & Backup System | [db_backup.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/db_backup.py), [apps/admin/db_utils.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/admin/db_utils.py), [apps/templates/admin/system.html](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/templates/admin/system.html) | Medium |
| **INF-01** | Influencers | Simplify & Modernize Influencer Interface | [apps/templates/admin/influencers.html](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/templates/admin/influencers.html), [apps/templates/profiles/influencer_edit.html](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/templates/profiles/influencer_edit.html) | Medium |
| **INF-02** | Influencers | Global Display Table Info, Sorting & Filtering | [apps/templates/home/discover.html](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/templates/home/discover.html), [apps/home/routes.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/home/routes.py) | High |

---

## 1. Admin Fixes & Enhancements

---

### ADM-01: Fix Scraping Engine & RapidAPI Scrapers
#### Problem & Root Cause Analysis
1. **Unbound Variables in Scrapers**: In `snapchat()` inside [apps/home/util.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/home/util.py#L565-L574), when RapidAPI returns a JSON structure without `publicProfileInfo`, `user_data` is left undefined. Continuing execution causes Python to raise an unhandled `UnboundLocalError: local variable 'user_data' referenced before assignment`.
2. **RapidAPI Key Configuration**: Hardcoded string fallbacks like `"YOUR_RAPIDAPI_KEY_HERE"` cause requests to fail silently or return 401 Unauthorized without descriptive user messaging.
3. **Thread Safety & DB Session Leaks**: In [tasks.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/tasks.py#L63-L140), multi-threaded executions with `ThreadPoolExecutor` must safely commit and close scoped Flask-SQLAlchemy database sessions upon failures or exceptions.
4. **Unhandled Rate Limits (HTTP 429)**: Lack of exponential backoff or retry logic for HTTP 429 (Too Many Requests) causes bulk database background scans to fail prematurely.

#### Developer To-Do Steps
- [ ] **Fix Snapchat Scraper Variable Initialization**:
  - Update `snapchat()` in [apps/home/util.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/home/util.py#L513-L597) to initialize `user_data = {}` prior to parsing JSON structures.
  - Return explicit error dictionary (`profile_data["error"] = "ملف المستخدم غير موجود أو خاص"`) when profile parsing fails.
- [ ] **Harden API Key Validation & Rate Limit Retries**:
  - Add API key check at startup: Verify `os.getenv("RAPIDAPI_KEY")` is present and valid before issuing requests.
  - Decorate `tiktok()`, `snapchat()`, and `instagram()` scraper functions with `@retry` backoff policies handling `TransientHTTPError` and HTTP 429 status codes.
- [ ] **Update Thread Worker Exception Handling**:
  - In `process_username()` in [tasks.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/tasks.py#L63-L141), wrap thread executions in a `try...except Exception...finally` block that strictly calls `db.session.remove()` and records individual error tracebacks in `ScanLog`.
- [ ] **Add Admin Scrape Error Reporting**:
  - Update [apps/templates/home/admin_scrape_influencer.html](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/templates/home/admin_scrape_influencer.html) to render clear flash warning banners when live scraping fails for a username.

---

### ADM-02: Create & Implement Role-Based Access Control (RBAC) System
#### Problem & Root Cause Analysis
Currently, user roles in [apps/authentication/models.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/authentication/models.py#L25) are stored as a plain text string `role = db.Column(db.String(20), default='user')` with only binary logic (`admin` vs `user` / `client`). There are no granular permissions, role definitions, or system-wide RBAC management tools.

#### Developer To-Do Steps
- [ ] **Create Database Models for Roles & Permissions**:
  - Define `Role` model in [apps/authentication/models.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/authentication/models.py):
    ```python
    class Role(db.Model):
        __tablename__ = 'roles'
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(50), unique=True, nullable=False) # e.g. 'Super Admin', 'Agency Manager', 'Analyst', 'Client'
        code = db.Column(db.String(30), unique=True, nullable=False) # e.g. 'super_admin', 'agency_manager', 'analyst', 'client'
        description = db.Column(db.String(255))
        is_default = db.Column(db.Boolean, default=False)
    ```
  - Update `Users` model to reference `role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=True)`.
- [ ] **Database Migration & Seeding**:
  - Create standard initial roles in a seed function or CLI script:
    1. **Super Admin** (`super_admin`): Full platform access, user management, system diagnostics, backups.
    2. **Agency Admin** (`agency_admin`): Full access to agency campaigns, team member management, billing.
    3. **Campaign Manager** (`campaign_manager`): Can create/edit shortlists, campaigns, and discover influencers.
    4. **Client / Viewer** (`client_viewer`): Read-only view of shared campaign shortlists and reports.
- [ ] **Build Permission Decorators**:
  - Create `@roles_required(*roles)` decorator in [apps/authentication/util.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/authentication/util.py) to replace static `@admin_required`.
  - Enforce route protection based on the user's assigned role code.

---

### ADM-03: Admin Account Management, Manual User Creation & Settings Assignment
#### Problem & Root Cause Analysis
The current user creation logic in [apps/authentication/routes.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/authentication/routes.py#L213-L250) (`/admin/add_by_email`) only creates admin accounts with auto-generated passwords and default usernames. Administrators lack an interactive modal/view to manually add accounts, specify passwords, assign specific system roles, link users to an Agency tenant, and configure subscription/tracking settings.

#### Developer To-Do Steps
- [ ] **Create User Management Forms**:
  - Update [apps/authentication/forms.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/authentication/forms.py) with `AdminUserCreateForm` and `AdminUserEditForm` supporting fields:
    - Username, Email, Password.
    - Role Select (dynamic choices from `Role.query.all()`).
    - Agency Select (dynamic choices from `Agency.query.all()`).
    - Account Status (Active / Inactive toggle).
    - Custom Tracking Limit / Plan Tier Override.
- [ ] **Implement Admin Routes for User Management**:
  - In [apps/authentication/routes.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/authentication/routes.py):
    - `POST /admin/users/create`: Validate input, hash password, instantiate `Users`, assign `role_id` and `agency_id`, and log action.
    - `POST /admin/users/<int:user_id>/edit`: Update role, assigned agency, active status, or reset user password.
    - `POST /admin/users/<int:user_id>/toggle-status`: Quick toggle for activating/deactivating accounts.
- [ ] **Upgrade Admin User Management UI**:
  - Redesign [apps/templates/accounts/users.html](file:///e:/Freelancing/Influencers Analytics Platform/Influencers-Analytics-Platform/apps/templates/accounts/users.html):
    - Add "إضافة حساب جديد" (Add New Account) modal with clean dropdown selects for Roles and Agencies.
    - Add badge labels displaying assigned Role (e.g. `Super Admin`, `Agency Manager`) and Agency Name.
    - Add "Edit Account" and "Reset Password" action triggers per table row.

---

### ADM-04: Fix Database Exporting & Backup Engine
#### Problem & Root Cause Analysis
1. **`pg_dump` Binary Path & Authentication Errors**: In [db_backup.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/db_backup.py#L61-L89) and [apps/admin/db_utils.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/admin/db_utils.py#L60-L133), `pg_dump` fails when PostgreSQL client tools are not installed in system PATH or when environment variables (`DB_PORT`, `DB_PASS`) are misconfigured.
2. **Missing Directories**: Backup and Export directories (`apps/static/backups`, `apps/static/exports`) may not exist when triggered, causing `FileNotFoundError`.
3. **Database Export Format**: In [apps/admin/db_utils.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/admin/db_utils.py#L250-L337) `export_db_to_excel()`, individual CSVs are bundled into a ZIP file instead of producing a native, structured `.xlsx` Excel workbook with styled table tabs.
4. **Large File HTTP Timeout**: Web requests to `/admin/backup` block the Flask main thread.

#### Developer To-Do Steps
- [ ] **Fix Backup Utilities & Fallback Path Resolution**:
  - In [apps/admin/db_utils.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/admin/db_utils.py):
    - Ensure target directories (`apps/static/backups` and `apps/static/exports`) are automatically created with `os.makedirs(..., exist_ok=True)`.
    - Enhance `pg_dump` command detection: inspect standard system binary paths (e.g., `/usr/bin/pg_dump` or Windows PostgreSQL installation paths) if `pg_dump` is not found directly.
    - Enhance SQLAlchemy fallback exporter (`create_db_backup_sqlalchemy`) to correctly wrap non-ASCII strings and handles raw binary data.
- [ ] **Upgrade Database Export to Native Multi-Tab Excel (.xlsx)**:
  - Rewrite `export_db_to_excel()` in [apps/admin/db_utils.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/admin/db_utils.py#L250-L337) using `pandas` and `openpyxl`:
    ```python
    def export_db_to_excel(db):
        output_path = os.path.join(current_app.root_path, 'static', 'exports', f'db_export_{timestamp}.xlsx')
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            for table_name in inspector.get_table_names():
                df = pd.read_sql_table(table_name, db.engine)
                df.to_excel(writer, sheet_name=table_name[:31], index=False)
        return True, output_path
    ```
- [ ] **Add Async Background Execution for Backups**:
  - Wrap database backup triggers in background thread tasks to prevent request timeouts on large databases, notifying users via AJAX status updates in [apps/templates/admin/system.html](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/templates/admin/system.html).

---

## 2. Influencer Module & User Interface Enhancements

---

### INF-01: Simplify & Modernize Influencer Interface
#### Problem & Root Cause Analysis
The influencer detail and management templates ([apps/templates/admin/influencers.html](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/templates/admin/influencers.html), [apps/templates/profiles/influencer_edit.html](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/templates/profiles/influencer_edit.html)) present cluttered cards, repetitive input fields, and lack visual hierarchy.

#### Developer To-Do Steps
- [ ] **Redesign Influencer Profile & Management Views**:
  - Simplify layout in [apps/templates/profiles/influencer_edit.html](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/templates/profiles/influencer_edit.html) and [apps/templates/admin/influencer_detail.html](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/templates/admin/influencer_detail.html):
    - Introduce clean tabbed navigation: **Overview**, **Social Accounts & Metrics**, **Historical Analytics**, and **Campaign History**.
    - Replace heavy form borders with sleek glassmorphism/card UI, modern typography (Inter / Tajawal font), and platform-specific color highlights (Instagram pink/purple, TikTok black, Snapchat yellow).
- [ ] **Streamline Action Controls**:
  - Consolidate quick actions (Add Social Account, Trigger Manual Refresh, Edit Details, Delete Profile) into a clean sticky action bar at top-right of the page.
  - Implement instant feedback spinners during social profile refresh triggers.

---

### INF-02: Global Display Table: Metrics, Sorting & Filtering
#### Problem & Root Cause Analysis
In [apps/templates/home/discover.html](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/templates/home/discover.html#L56-L86), the main table currently displays only **المؤثر (Influencer Name/Avatar)**, **المنصات (Platforms)**, and **الإجراءات (Actions)**. Critical analytics data (follower counts, reach, location, country, category/niche, engagement rates, contact details) are omitted from the global list view. Furthermore, client users cannot sort by follower metrics or filter by platform/country.

#### Developer To-Do Steps
- [ ] **Expand Global Table Schema & Data Queries**:
  - Update `discover()` route in [apps/home/routes.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/home/routes.py#L147-L158) and `influencers()` in [apps/profiles/routes.py](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/profiles/routes.py) to eager-load `socialaccounts` and summarize metrics.
  - Add calculating helpers for **Total Followers / Reach** (sum across all platforms) and **Primary Niche**.
- [ ] **Enhance HTML Table Structure**:
  - In [apps/templates/home/discover.html](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/templates/home/discover.html) and [apps/templates/profiles/influencers.html](file:///e:/Freelancing/Influencers%20Analytics%20Platform/Influencers-Analytics-Platform/apps/templates/profiles/influencers.html):
    - Add comprehensive columns to `<thead>`:
      1. **المؤثر (Influencer)**: Avatar, Name, Gender badge.
      2. **إجمالي المتابعين (Total Reach)**: Highlighted total follower count with platform breakdown popovers.
      3. **المنصات المرتبطة (Social Accounts)**: Badges with usernames and direct links.
      4. **الدولة والمدينة (Location)**: Country flag / City text.
      5. **التخصص / النيش (Category / Niche)**: Content category tags.
      6. **معلومات التواصل (Contact Info)**: Phone / Email status badges.
      7. **تاريخ الإضافة (Date Added)**: ISO formatted creation date.
      8. **الإجراءات (Actions)**: Quick Add to Campaign, Favorite toggle, View Profile.
- [ ] **Implement Multi-Column Sorting & Interactive Filtering**:
  - Integrate **DataTables** with Bootstrap 5 integration:
    - **Sorting**: Enable column-based sorting for Total Followers (`data-order`), Name, Country, and Date Added.
    - **Platform Filter**: Add filter buttons/select (`All`, `Instagram`, `TikTok`, `Snapchat`).
    - **Country Filter**: Add dynamic dropdown filter populated from unique countries in the dataset.
    - **Follower Range Filter**: Add a dropdown filter (e.g. `< 50K`, `50K - 250K`, `250K - 1M`, `1M+`).
    - **Search Input**: Live multi-keyword search input filtering across name, handle, country, and bio text.

---

## 3. Verification & Definition of Done (DoD)

To consider these points fully resolved, execute the following verification steps:

1. **Scraping Engine Test**:
   - Run manual profile scrape for Instagram, TikTok, and Snapchat handles.
   - Verify zero unhandled `UnboundLocalError` or thread crashes occur.
   - Verify failed requests log readable Arabic error messages in `ScanLog`.
2. **RBAC & User Management Test**:
   - Create accounts with `Admin`, `Campaign Manager`, and `Client Viewer` roles via `/admin/users/create`.
   - Log in as each role and verify permission decorators block unauthorized route access.
3. **Export & Backup Test**:
   - Trigger database backup via Admin system dashboard (`/admin/system`).
   - Trigger database Excel export and open generated `.xlsx` file to confirm all database tables exist as individual formatted sheets.
4. **Influencers Table Test**:
   - Open `/discover` in browser.
   - Test sorting by Total Followers (Ascending/Descending).
   - Test filtering by Platform (e.g., display only TikTok accounts) and Country.
   - Confirm all columns (Reach, Social Badges, Location, Category, Actions) render correctly across desktop and mobile screens.
