#!/usr/bin/env python3
"""
scripts/onboard_legacy_data.py
================================
Idempotent ETL script for onboarding historical influencer data from a
3-sheet Excel workbook into the existing PostgreSQL/SQLite database.

Usage
-----
Normal run (commits changes):
    python scripts/onboard_legacy_data.py legacy_data.xlsx

Dry-run (parses & reports; no DB writes):
    python scripts/onboard_legacy_data.py legacy_data.xlsx --dry-run

Specify sheet names or 0-based indices (defaults: 0, 1, 2):
    python scripts/onboard_legacy_data.py legacy_data.xlsx \
        --sheet1 "Master" --sheet2 "Meta" --sheet3 "History"

Sheet layout
------------
Sheet 1  -- Master profiles / contact directory
Sheet 2  -- Legacy meta enrichment (scraped account strings)
Sheet 3  -- Historical scan results (time-series follower snapshots)

Transaction safety
------------------
All three sheets are processed inside ONE database transaction.
A fatal error on any sheet triggers a full rollback so the DB is never
left partially migrated.
"""

import os
import re
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import argparse
import traceback
from datetime import date, datetime
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Bootstrap: the script lives in <project_root>/scripts/.
# Add the parent directory so Flask app imports resolve correctly.
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Configure icecream BEFORE importing anything that uses it.
from ic_config import configure_icecream  # noqa: E402
configure_icecream()

import pandas as pd  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

# ---------------------------------------------------------------------------
# Load the correct .env file (same logic as run.py / wsgi.py).
# ---------------------------------------------------------------------------
_env_file = ".env.prod" if os.getenv("FLASK_ENV") == "production" else ".env.dev"
load_dotenv(os.path.join(PROJECT_ROOT, _env_file))

# ---------------------------------------------------------------------------
# Create the Flask app.  This initialises db, registers blueprints, etc.
# All subsequent imports that touch `db` must happen AFTER this call.
# ---------------------------------------------------------------------------
from apps.config import config_dict  # noqa: E402
from apps import create_app, db      # noqa: E402

_debug = os.getenv("DEBUG_MODE", "False") == "True"
_config_mode = "Debug" if _debug else "Production"
app = create_app(config_dict[_config_mode])

# Models -- imported AFTER app creation so SQLAlchemy metadata is ready.
from apps.profiles.models import Influencer         # noqa: E402
from apps.social.models import Platform, SocialAccount  # noqa: E402
from apps.reports.models import ScanResults          # noqa: E402



# ===========================================================================
# PLATFORM MAP
# ===========================================================================
# Maps every Arabic/English platform name variant to the database platform_id.
# platform_id 2 = TikTok, 3 = Instagram, 4 = Snapchat
# Values must match actual rows in the `platforms` table.
# Note: \uXXXX escape sequences in normal (non-raw) Python string literals
# are decoded automatically — the Arabic text in comments is informational.
# ===========================================================================
PLATFORM_MAP: dict = {
    # TikTok  (Arabic: تيك توك)
    "tiktok": 2,
    "tik tok": 2,
    "\u062a\u064a\u0643 \u062a\u0648\u0643": 2,
    # Instagram  (Arabic: انستقرام / إنستاجرام / انستغرام)
    "instagram": 3,
    "\u0627\u0646\u0633\u062a\u0642\u0631\u0627\u0645": 3,
    "\u0625\u0646\u0633\u062a\u0627\u062c\u0631\u0627\u0645": 3,
    "\u0627\u0646\u0633\u062a\u063a\u0631\u0627\u0645": 3,
    # Snapchat  (Arabic: سناب شات / سناب)
    "snapchat": 4,
    "snap chat": 4,
    "\u0633\u0646\u0627\u0628 \u0634\u0627\u062a": 4,
    "\u0633\u0646\u0627\u0628": 4,
}



# ===========================================================================
# MIGRATION COUNTERS
# ===========================================================================
_s1 = dict(
    rows_read=0, valid=0, invalid=0,
    influencers_created=0, influencers_updated=0,
    accounts_created=0, accounts_updated=0, skipped=0,
)
_s2 = dict(rows_read=0, enriched=0, unmatched=0, invalid=0)
_s3 = dict(
    rows_read=0, inserted=0, duplicates_skipped=0,
    accounts_updated=0, unmatched=0, invalid=0,
)


# ===========================================================================
# NORMALISATION HELPERS
# ===========================================================================

def normalize_platform(raw) -> Optional[int]:
    """
    Maps a raw Excel platform cell to a canonical platform_id (int).

    1. Strips whitespace and lower-cases.
    2. Looks up in PLATFORM_MAP (which covers Arabic and English variants).
    3. Returns None for unknown / missing values -- caller must log and skip.
    """
    if raw is None:
        return None
    if isinstance(raw, float) and (raw != raw):  # NaN check without pandas import
        return None
    s = str(raw).strip().lower()
    if s in ("nan", "none", "null", ""):
        return None
    return PLATFORM_MAP.get(s)


def normalize_username(raw) -> Optional[str]:
    """
    Normalises a social-media username.

    Steps:
    1. Strip whitespace.
    2. Reject null sentinels (nan, none, null, empty).
    3. Extract the username from supported profile URLs:
       - TikTok:    tiktok.com/@username
       - Instagram: instagram.com/username
       - Snapchat:  snapchat.com/add/username
    4. Strip a bare leading '@'.
    5. Lower-case (all three platforms are case-insensitive for usernames).
    6. Return None for empty result.
    """
    if raw is None:
        return None
    if isinstance(raw, float) and (raw != raw):
        return None

    s = str(raw).strip()
    if s.lower() in ("nan", "none", "null", ""):
        return None

    # --- URL extraction ------------------------------------------------
    m = re.search(r"tiktok\.com/@?([\w.]+)", s, re.IGNORECASE)
    if m:
        return m.group(1).lower()

    m = re.search(r"instagram\.com/([^/?#\s]+)", s, re.IGNORECASE)
    if m:
        uname = m.group(1).strip("/").lower()
        if uname:
            return uname

    m = re.search(r"snapchat\.com/(?:add/)?([^/?#\s]+)", s, re.IGNORECASE)
    if m:
        uname = m.group(1).strip("/").lower()
        if uname:
            return uname

    # --- Strip bare leading '@' ----------------------------------------
    s = s.lstrip("@").strip()
    if not s or s.lower() in ("nan", "none", "null"):
        return None

    return s.lower()


def normalize_phone(raw) -> Optional[str]:
    """
    Normalises a phone number to E.164 format.

    Saudi Arabia special handling:
    - '0501234567'     -> '+966501234567'
    - '966501234567'   -> '+966501234567'
    - '+966 50 123 4567' -> '+966501234567'

    General:
    - Remove spaces, hyphens, parentheses, dots.
    - Keep existing '+' prefix.
    - Do NOT blindly add +966 to non-Saudi numbers.

    Returns None for missing / malformed values.
    """
    if raw is None:
        return None
    if isinstance(raw, float) and (raw != raw):
        return None

    s = str(raw).strip()
    if s.lower() in ("nan", "none", "null", ""):
        return None

    # Remove all formatting characters except leading '+'.
    has_plus = s.startswith("+")
    cleaned = re.sub(r"[\s\-().]", "", s)
    if has_plus:
        cleaned = "+" + cleaned.lstrip("+")

    if cleaned.startswith("+"):
        digits = cleaned[1:]
        if digits.isdigit() and 7 <= len(digits) <= 15:
            return cleaned
        return None

    if not cleaned.isdigit():
        return None

    # Saudi local: 05XXXXXXXX (10 digits).
    if cleaned.startswith("0") and len(cleaned) == 10:
        return "+966" + cleaned[1:]

    # Already has 966 prefix, 12 digits total.
    if cleaned.startswith("966") and len(cleaned) == 12:
        return "+" + cleaned

    # Generic plausible number.
    if 7 <= len(cleaned) <= 15:
        return "+" + cleaned

    return None


def normalize_gender(raw) -> Optional[str]:
    """
    Maps Arabic / English gender strings to 'male' or 'female'.
    Returns None for missing or unrecognised values.
    """
    if raw is None:
        return None
    if isinstance(raw, float) and (raw != raw):
        return None
    s = str(raw).strip()
    # Arabic: أنثى / انثى; English: female / f
    female_values = {
        "\u0623\u0646\u062b\u0649",  # أنثى
        "\u0627\u0646\u062b\u0649",  # انثى
        "female", "f",
    }
    male_values = {
        "\u0630\u0643\u0631",  # ذكر
        "male", "m",
    }
    if s in female_values:
        return "female"
    if s in male_values:
        return "male"
    return None


def clean_numeric(raw) -> Optional[int]:
    """
    Converts a cell value to a plain Python int.

    Handles:
    - Comma-separated thousands  ('1,340,000')
    - Trailing decimal zeros     ('1340000.0', '1340000.00')
    - Suffix abbreviations       ('2.24M', '1.5K', '3.2B')
    - Native int / float

    Returns None (SQL NULL) for:
    - NaN, None, null, empty, 'None', 'nan'
    - Unconvertible values (logs a warning)

    Does NOT convert numeric zero to None.
    """
    if raw is None:
        return None
    if isinstance(raw, float):
        if raw != raw:  # NaN
            return None
        return int(raw)
    if isinstance(raw, int):
        return raw

    s = str(raw).strip().replace(",", "")
    if s.lower() in ("nan", "none", "null", ""):
        return None

    multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
    if s and s[-1].lower() in multipliers:
        try:
            return int(float(s[:-1]) * multipliers[s[-1].lower()])
        except ValueError:
            print(f"  [WARN] Malformed numeric (suffix): {raw!r}")
            return None

    try:
        return int(float(s))
    except (ValueError, OverflowError):
        print(f"  [WARN] Malformed numeric: {raw!r}")
        return None


def parse_update_date(raw) -> Optional[date]:
    """
    Parses a Sheet 3 date cell into a Python date object.

    Accepts:
    - pandas Timestamp / datetime / date objects
    - ISO string 'YYYY-MM-DD'
    - Common formats: 'DD/MM/YYYY', 'DD-MM-YYYY', 'MM/DD/YYYY', 'YYYY/MM/DD'

    Returns None and prints a warning for unparseable values.
    """
    if raw is None:
        return None
    if isinstance(raw, float) and (raw != raw):
        return None

    # Handle pandas / datetime objects.
    if hasattr(raw, "date") and callable(raw.date):
        return raw.date()
    if isinstance(raw, date):
        return raw

    s = str(raw).strip()
    if s.lower() in ("nan", "none", "null", ""):
        return None

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue

    print(f"  [WARN] Could not parse date: {raw!r}")
    return None


def _normalize_email(raw) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, float) and (raw != raw):
        return None
    s = str(raw).strip().lower()
    return s if s and s not in ("nan", "none", "null") else None


def _normalize_str(raw) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, float) and (raw != raw):
        return None
    s = str(raw).strip()
    return s if s and s.lower() not in ("nan", "none", "null") else None


# ===========================================================================
# COLUMN-NAME NORMALISATION
# ===========================================================================
# Maps each canonical internal key to a list of possible Excel header
# spellings (case-insensitive).  Using this layer means the ETL is not
# brittle against minor header changes or Arabic/English mixing.
# ===========================================================================

SHEET1_COL_ALIASES = {
    "full_name": ["full_name", "name", "اسم", "الاسم", "اسم كامل", "الاسم الكامل", "إسم الملف"],
    "username":  ["username", "اسم المستخدم", "يوزر", "حساب", "معرف", "إسم الحساب"],
    "platform":  ["platform", "platform_name", "منصة", "المنصة"],
    "gender":    ["gender", "الجنس", "جنس"],
    "category":  ["category", "niche", "التصنيف", "تصنيف", "مجال", "المحتوى"],
    "followers": ["followers", "متابعون", "متابعين", "عدد المتابعين", "المتابعين"],
    "email":     ["email", "البريد", "بريد إلكتروني", "إيميل", "ايميل", "البريد الإلكتروني"],
    "phone":     ["phone", "هاتف", "جوال", "رقم الجوال", "رقم الهاتف", "رقم الهاتف"],
}

SHEET2_COL_ALIASES = {
    "account_repr": ["account", "social_account", "socialaccount", "repr", "حساب", "نص الحساب", "socialaccount_id"],
    "bio":          ["bio", "bio_text", "السيرة", "نبذة", "وصف", "نص البايو", "نص البايو\n"],
    "profile_pic":  ["profile_picture", "profile_pic", "avatar", "cdn_url", "صورة", "صورة الملف"],
    "external_url": ["external_url", "url", "رابط", "الرابط", "رابط الصفحة"],
    "username":     ["username", "اسم المستخدم", "يوزر", "اليوزر نيم"],
    "platform":     ["platform", "منصة", "المنصة"],
}

SHEET3_COL_ALIASES = {
    "username":    ["username", "اسم المستخدم", "يوزر", "معرف", "اليوزر نيم"],
    "platform":    ["platform", "منصة", "المنصة"],
    "followers":   ["followers", "متابعون", "متابعين", "عدد المتابعين", "عدد المتابعين المتغير", "المتابعين"],
    "likes":       ["likes", "اعجابات", "إعجابات", "عدد الاعجابات المتغير", "الإعجابات"],
    "posts":       ["posts", "منشورات", "عدد المنشورات", "المنشورات"],
    "update_date": ["update_date", "date", "تاريخ التحديث", "تاريخ", "التاريخ", "تاريخ التحديث\n"],
}


def _resolve_columns(df: "pd.DataFrame", alias_map: dict) -> dict:
    """
    Returns {canonical_key -> actual_df_column_name or None}.
    Matching is case-insensitive against stripped column names.
    """
    df_cols_lower = {c.strip().lower(): c for c in df.columns}
    resolved = {}
    for canonical, aliases in alias_map.items():
        found = None
        for alias in aliases:
            # Decode escape sequences in the alias string for Arabic matching.
            try:
                decoded = alias.encode("raw_unicode_escape").decode("unicode_escape")
            except Exception:
                decoded = alias
            if decoded.strip().lower() in df_cols_lower:
                found = df_cols_lower[decoded.strip().lower()]
                break
            if alias.strip().lower() in df_cols_lower:
                found = df_cols_lower[alias.strip().lower()]
                break
        resolved[canonical] = found
    return resolved


def _get(row: "pd.Series", col_map: dict, key: str):
    col = col_map.get(key)
    if col is None:
        return None
    return row.get(col)


# ===========================================================================
# INFLUENCER MATCHING / UPSERT
# ===========================================================================

def find_or_create_influencer(
    full_name: Optional[str],
    email: Optional[str],
    phone: Optional[str],
    gender: Optional[str],
    category: Optional[str],
    dry_run: bool,
    existing_account=None,
) -> Tuple[Optional[object], str]:
    """
    Resolves to an existing Influencer or creates a new one.

    Matching priority (stops at the first match):
    1. The SocialAccount already exists in the DB -- use its linked Influencer.
    2. Exact normalised email match.
    3. Exact normalised phone match.
    4. Exact full_name match (unique constraint in the DB).
    5. Create new (requires full_name; skips if not present).

    Existing records are enriched (NULL fields filled) but valid data is
    never overwritten.

    Returns (influencer | None, action_string).
    action_string: 'existing_via_account' | 'existing_via_email' |
                   'existing_via_phone' | 'existing_via_name' |
                   'created' | 'skipped'
    """
    # Priority 1 -- linked via existing SocialAccount
    if existing_account is not None:
        inf = existing_account.influencer
        _enrich_influencer(inf, email, phone, gender, category, dry_run)
        return inf, "existing_via_account"

    # Priority 2 -- email
    if email:
        inf = Influencer.query.filter(
            db.func.lower(Influencer.email) == email.lower()
        ).first()
        if inf:
            _enrich_influencer(inf, email, phone, gender, category, dry_run)
            return inf, "existing_via_email"

    # Priority 3 -- phone
    if phone:
        inf = Influencer.query.filter_by(phone=phone).first()
        if inf:
            _enrich_influencer(inf, email, phone, gender, category, dry_run)
            return inf, "existing_via_phone"

    # Priority 4 -- full_name (unique in DB)
    if full_name:
        inf = Influencer.query.filter_by(full_name=full_name).first()
        if inf:
            _enrich_influencer(inf, email, phone, gender, category, dry_run)
            return inf, "existing_via_name"

    # Priority 5 -- create
    if not full_name:
        print(
            f"  [WARN] Cannot resolve Influencer: no full_name and no existing "
            f"account match (email={email!r}, phone={phone!r}) -- skipping row"
        )
        return None, "skipped"

    inf = Influencer(
        full_name=full_name,
        email=email,
        phone=phone,
        gender=gender,
        category=category,
    )
    db.session.add(inf)
    db.session.flush()  # Assign PK so SocialAccount FK can reference it.
    return inf, "created"


def _enrich_influencer(inf, email, phone, gender, category, dry_run: bool) -> None:
    """Fills NULL fields without overwriting non-NULL existing values."""
    if email and not inf.email:
        inf.email = email
    if phone and not inf.phone:
        inf.phone = phone
    if gender and not inf.gender:
        inf.gender = gender
    if category and not inf.category:
        inf.category = category


# ===========================================================================
# SOCIAL ACCOUNT MATCHING / UPSERT
# ===========================================================================

def find_or_create_social_account(
    platform_id: int,
    username: str,
    influencer,
    followers: Optional[int],
    dry_run: bool,
) -> Tuple[Optional[object], str]:
    """
    Finds an existing SocialAccount by (platform_id, username) or creates one.

    The DB enforces UniqueConstraint('username', 'platform_id') as
    '_username_platform_uc', making this the canonical identity key.

    Returns (account | None, 'existing' | 'created').
    """
    account = SocialAccount.query.filter_by(
        platform_id=platform_id,
        username=username,
    ).first()

    if account:
        # Enrich followers only when stored value is absent or zero.
        if followers is not None and (account.followers is None or account.followers == 0):
            account.followers = followers
        return account, "existing"

    account = SocialAccount(
        influencer_id=influencer.id,
        platform_id=platform_id,
        username=username,
        followers=followers,
    )
    db.session.add(account)
    db.session.flush()  # Assign PK for FK references.
    return account, "created"


# ===========================================================================
# SCAN RESULT IDEMPOTENCY
# ===========================================================================

def _scan_result_exists(socialaccount_id: int, snapshot_date: date) -> bool:
    """
    Returns True when a ScanResult already exists for (socialaccount_id, date).

    ScanResults has no unique constraint, so we implement an explicit existence
    check keyed on (socialaccount_id, creation_date).  Running the migration
    twice produces at most one row per (account, date) combination.
    """
    return db.session.query(
        ScanResults.query.filter_by(
            socialaccount_id=socialaccount_id,
            creation_date=snapshot_date,
        ).exists()
    ).scalar()


# ===========================================================================
# SHEET 1 -- MASTER PROFILES / CONTACT DIRECTORY
# ===========================================================================

def process_sheet1(df: "pd.DataFrame", dry_run: bool) -> None:
    """
    Process Sheet 1.

    Each row represents ONE social account belonging to ONE influencer.
    The same influencer may appear on multiple rows (different platforms).
    We match the influencer first, then create/update the SocialAccount.
    """
    print("\n" + "=" * 60)
    print("SHEET 1 -- Master Profiles / Contact Directory")
    print("=" * 60)

    col = _resolve_columns(df, SHEET1_COL_ALIASES)
    missing_keys = [k for k, v in col.items() if v is None]
    if missing_keys:
        print(f"  [INFO] Sheet 1: no columns found for keys: {missing_keys}")
        print(f"         Available columns: {list(df.columns)}")

    _s1["rows_read"] = len(df)

    for idx, row in df.iterrows():
        row_num = int(idx) + 2  # 1-indexed + header row
        try:
            _process_s1_row(row, row_num, col, dry_run)
        except Exception as exc:
            raise RuntimeError(f"Sheet 1, row {row_num}") from exc


def _process_s1_row(row, row_num: int, col: dict, dry_run: bool) -> None:
    full_name   = _normalize_str(_get(row, col, "full_name"))
    username    = normalize_username(_get(row, col, "username"))
    platform_id = normalize_platform(_get(row, col, "platform"))
    gender      = normalize_gender(_get(row, col, "gender"))
    category    = _normalize_str(_get(row, col, "category"))
    followers   = clean_numeric(_get(row, col, "followers"))
    email       = _normalize_email(_get(row, col, "email"))
    phone       = normalize_phone(_get(row, col, "phone"))

    if not username:
        print(f"  [WARN] S1 row {row_num}: missing username -- skipping (name={full_name!r})")
        _s1["invalid"] += 1
        _s1["skipped"] += 1
        return

    if platform_id is None:
        raw_plat = _get(row, col, "platform")
        print(f"  [WARN] S1 row {row_num}: unknown platform {raw_plat!r} -- skipping "
              f"(username={username!r})")
        _s1["invalid"] += 1
        _s1["skipped"] += 1
        return

    _s1["valid"] += 1

    # Check if the SocialAccount already exists.
    existing_account = SocialAccount.query.filter_by(
        platform_id=platform_id, username=username
    ).first()

    influencer, action = find_or_create_influencer(
        full_name=full_name, email=email, phone=phone,
        gender=gender, category=category,
        dry_run=dry_run, existing_account=existing_account,
    )

    if influencer is None:
        _s1["skipped"] += 1
        return

    if action == "created":
        _s1["influencers_created"] += 1
        print(f"  [S1] Row {row_num}: Created Influencer '{full_name}'")
    elif action.startswith("existing"):
        _s1["influencers_updated"] += 1

    if not dry_run and influencer.id is None:
        db.session.flush()

    account, acc_action = find_or_create_social_account(
        platform_id=platform_id, username=username,
        influencer=influencer, followers=followers, dry_run=dry_run,
    )

    if acc_action == "created":
        _s1["accounts_created"] += 1
        print(f"  [S1] Row {row_num}: Created SocialAccount '{username}' "
              f"(platform_id={platform_id})")
    else:
        _s1["accounts_updated"] += 1


# ===========================================================================
# SHEET 2 -- LEGACY META ENRICHMENT
# ===========================================================================

def process_sheet2(df: "pd.DataFrame", dry_run: bool) -> None:
    """
    Process Sheet 2.

    Enriches existing SocialAccounts with bio_text, profile_picture, and
    external_url from legacy scraped data.

    Rules:
    - NEVER creates new SocialAccounts or Influencers.
    - Updates a field ONLY when the incoming value is non-empty AND the
      current DB value is missing/empty.
    - Matches strictly by (platform_id, normalized_username).
    """
    print("\n" + "=" * 60)
    print("SHEET 2 -- Legacy Meta Enrichment")
    print("=" * 60)

    col = _resolve_columns(df, SHEET2_COL_ALIASES)
    _s2["rows_read"] = len(df)

    for idx, row in df.iterrows():
        row_num = int(idx) + 2
        try:
            _process_s2_row(row, row_num, col, dry_run)
        except Exception as exc:
            raise RuntimeError(f"Sheet 2, row {row_num}") from exc


def _extract_username_from_repr(repr_str: str) -> Optional[str]:
    """Parses username from SocialAccount repr strings like username='zuhoora'."""
    m = re.search(r"""username=['"](.*?)['"]""", repr_str, re.IGNORECASE)
    if m:
        return normalize_username(m.group(1))
    return normalize_username(repr_str)


def _extract_platform_from_repr(repr_str: str) -> Optional[int]:
    """Parses platform_id from SocialAccount repr strings."""
    m = re.search(r"Platform\(id=(\d+)", repr_str, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"""name=['"](.*?)['"]""", repr_str, re.IGNORECASE)
    if m:
        return normalize_platform(m.group(1))
    return None


def _process_s2_row(row, row_num: int, col: dict, dry_run: bool) -> None:
    raw_repr = _get(row, col, "account_repr")
    raw_bio  = _get(row, col, "bio")
    raw_pic  = _get(row, col, "profile_pic")
    raw_url  = _get(row, col, "external_url")

    username    = normalize_username(_get(row, col, "username"))
    platform_id = normalize_platform(_get(row, col, "platform"))

    if (username is None or platform_id is None) and raw_repr:
        repr_str = str(raw_repr).strip()
        if username is None:
            username = _extract_username_from_repr(repr_str)
        if platform_id is None:
            platform_id = _extract_platform_from_repr(repr_str)

    if not username:
        print(f"  [WARN] S2 row {row_num}: cannot determine username -- skipping")
        _s2["invalid"] += 1
        return

    if platform_id is None:
        print(f"  [WARN] S2 row {row_num}: cannot determine platform -- skipping "
              f"(username={username!r})")
        _s2["invalid"] += 1
        return

    account = SocialAccount.query.filter_by(
        platform_id=platform_id, username=username
    ).first()

    if account is None:
        print(f"  [WARN] S2 row {row_num}: no SocialAccount for "
              f"username={username!r}, platform_id={platform_id} -- unmatched")
        _s2["unmatched"] += 1
        return

    bio = _normalize_str(raw_bio)
    pic = _normalize_str(raw_pic)
    url = _normalize_str(raw_url)
    changed = False

    if bio and not account.bio_text:
        account.bio_text = bio
        changed = True

    if pic and not account.profile_picture:
        account.profile_picture = pic
        changed = True

    if url and not account.external_url:
        account.external_url = url
        changed = True

    if changed:
        _s2["enriched"] += 1


# ===========================================================================
# SHEET 3 -- HISTORICAL SCAN RESULTS
# ===========================================================================

def process_sheet3(df: "pd.DataFrame", dry_run: bool) -> None:
    """
    Process Sheet 3.

    Each row is a point-in-time snapshot for one SocialAccount.
    Multiple rows with the same username on different dates are NOT duplicates;
    they are historical data to be preserved in ScanResults.

    After all rows are processed, the latest snapshot per SocialAccount is
    used to update the live SocialAccount metrics (followers, total_likes,
    total_posts).
    """
    print("\n" + "=" * 60)
    print("SHEET 3 -- Historical Scan Results")
    print("=" * 60)

    col = _resolve_columns(df, SHEET3_COL_ALIASES)
    _s3["rows_read"] = len(df)

    # {(platform_id, username): {date, followers, likes, posts}}
    latest_snapshots: dict = {}

    for idx, row in df.iterrows():
        row_num = int(idx) + 2
        try:
            _process_s3_row(row, row_num, col, dry_run, latest_snapshots)
        except Exception as exc:
            raise RuntimeError(f"Sheet 3, row {row_num}") from exc

    # Apply latest snapshots to SocialAccount live metrics.
    for (platform_id, username), snap in latest_snapshots.items():
        account = SocialAccount.query.filter_by(
            platform_id=platform_id, username=username
        ).first()
        if account is None:
            continue

        updated = False
        followers = snap.get("followers")
        likes     = snap.get("likes")
        posts     = snap.get("posts")

        # Always update followers from the latest snapshot.
        if followers is not None:
            account.followers = followers
            updated = True
        # Only fill in likes/posts when currently missing.
        if likes is not None and account.total_likes is None:
            account.total_likes = likes
            updated = True
        if posts is not None and account.total_posts is None:
            account.total_posts = posts
            updated = True

        if updated:
            _s3["accounts_updated"] += 1


def _process_s3_row(row, row_num: int, col: dict, dry_run: bool, latest_snapshots: dict) -> None:
    username    = normalize_username(_get(row, col, "username"))
    platform_id = normalize_platform(_get(row, col, "platform"))
    followers   = clean_numeric(_get(row, col, "followers"))
    likes       = clean_numeric(_get(row, col, "likes"))
    posts       = clean_numeric(_get(row, col, "posts"))
    snap_date   = parse_update_date(_get(row, col, "update_date"))

    if not username:
        print(f"  [WARN] S3 row {row_num}: missing username -- skipping")
        _s3["invalid"] += 1
        return

    if platform_id is None:
        raw_plat = _get(row, col, "platform")
        print(f"  [WARN] S3 row {row_num}: unknown platform {raw_plat!r} -- skipping "
              f"(username={username!r})")
        _s3["invalid"] += 1
        return

    if snap_date is None:
        print(f"  [WARN] S3 row {row_num}: missing/bad date -- skipping "
              f"(username={username!r})")
        _s3["invalid"] += 1
        return

    account = SocialAccount.query.filter_by(
        platform_id=platform_id, username=username
    ).first()

    if account is None:
        print(f"  [WARN] S3 row {row_num}: no SocialAccount for "
              f"username={username!r}, platform_id={platform_id} -- unmatched")
        _s3["unmatched"] += 1
        return

    # Idempotency: skip if (account_id, date) already exists.
    if _scan_result_exists(account.id, snap_date):
        _s3["duplicates_skipped"] += 1
        return

    scan = ScanResults(
            socialaccount_id=account.id,
            followers=followers,
            likes=likes,
            posts=posts,
            creation_date=snap_date,
            # creation_time: DB default (current_time())
            # time_taken: NULL for historical imports (no live scrape time)
        )
    db.session.add(scan)

    _s3["inserted"] += 1

    # Track latest snapshot per account.
    key = (platform_id, username)
    existing = latest_snapshots.get(key)
    if existing is None or snap_date > existing["date"]:
        latest_snapshots[key] = {
            "date": snap_date, "followers": followers, "likes": likes, "posts": posts
        }


# ===========================================================================
# SUMMARY REPORT
# ===========================================================================

def print_summary(dry_run: bool) -> None:
    mode = "[DRY RUN -- NO CHANGES COMMITTED]" if dry_run else "[CHANGES COMMITTED]"
    print("\n" + "=" * 60)
    print(f"MIGRATION SUMMARY  {mode}")
    print("=" * 60)
    print(
        f"\nSheet 1 -- Master Profiles:"
        f"\n  Rows read              : {_s1['rows_read']}"
        f"\n  Valid rows             : {_s1['valid']}"
        f"\n  Invalid / skipped rows : {_s1['invalid'] + _s1['skipped']}"
        f"\n  Influencers created    : {_s1['influencers_created']}"
        f"\n  Influencers enriched   : {_s1['influencers_updated']}"
        f"\n  SocialAccounts created : {_s1['accounts_created']}"
        f"\n  SocialAccounts updated : {_s1['accounts_updated']}"
    )
    print(
        f"\nSheet 2 -- Legacy Meta Enrichment:"
        f"\n  Rows read              : {_s2['rows_read']}"
        f"\n  Enrichments applied    : {_s2['enriched']}"
        f"\n  Unmatched accounts     : {_s2['unmatched']}"
        f"\n  Invalid rows           : {_s2['invalid']}"
    )
    print(
        f"\nSheet 3 -- Historical Scan Results:"
        f"\n  Rows read              : {_s3['rows_read']}"
        f"\n  ScanResults inserted   : {_s3['inserted']}"
        f"\n  Duplicates skipped     : {_s3['duplicates_skipped']}"
        f"\n  SocialAccounts updated : {_s3['accounts_updated']}"
        f"\n  Unmatched accounts     : {_s3['unmatched']}"
        f"\n  Invalid rows           : {_s3['invalid']}"
    )


# ===========================================================================
# ENTRY POINT
# ===========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Onboard historical influencer data from a 3-sheet Excel workbook."
    )
    parser.add_argument(
        "excel_file",
        help="Path to the .xlsx workbook.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report without writing anything to the database.",
    )
    parser.add_argument("--sheet1", default="0",
        help="Sheet 1 name or 0-based index (default: 0).")
    parser.add_argument("--sheet2", default="1",
        help="Sheet 2 name or 0-based index (default: 1).")
    parser.add_argument("--sheet3", default="2",
        help="Sheet 3 name or 0-based index (default: 2).")
    args = parser.parse_args()

    excel_path = os.path.abspath(args.excel_file)
    if not os.path.isfile(excel_path):
        print(f"[ERROR] File not found: {excel_path}")
        sys.exit(1)

    dry_run: bool = args.dry_run
    if dry_run:
        print("\n*** DRY RUN MODE -- database will NOT be modified ***\n")

    def _sheet_idx(val: str):
        try:
            return int(val)
        except ValueError:
            return val

    sheet1_id = _sheet_idx(args.sheet1)
    sheet2_id = _sheet_idx(args.sheet2)
    sheet3_id = _sheet_idx(args.sheet3)

    print(f"Reading workbook: {excel_path}")
    try:
        # dtype=str + keep_default_na=False: prevents pandas from silently
        # converting cell values; we do all type coercion ourselves.
        df1 = pd.read_excel(excel_path, sheet_name=sheet1_id, dtype=str, keep_default_na=False)
        df2 = pd.read_excel(excel_path, sheet_name=sheet2_id, dtype=str, keep_default_na=False)
        df3 = pd.read_excel(excel_path, sheet_name=sheet3_id, dtype=str, keep_default_na=False)
    except Exception as exc:
        print(f"[ERROR] Failed to read Excel file: {exc}")
        sys.exit(1)

    df1.columns = [str(c).strip() for c in df1.columns]
    df2.columns = [str(c).strip() for c in df2.columns]
    df3.columns = [str(c).strip() for c in df3.columns]

    print(f"Sheet 1 ({sheet1_id}): {len(df1)} rows -- columns: {list(df1.columns)}")
    print(f"Sheet 2 ({sheet2_id}): {len(df2)} rows -- columns: {list(df2.columns)}")
    print(f"Sheet 3 ({sheet3_id}): {len(df3)} rows -- columns: {list(df3.columns)}")

    with app.app_context():
        try:
            process_sheet1(df1, dry_run)
            process_sheet2(df2, dry_run)
            process_sheet3(df3, dry_run)

            if dry_run:
                db.session.rollback()
                print("\n[DRY RUN] Transaction rolled back -- no changes persisted.")
            else:
                db.session.commit()
                print("\n[OK] Transaction committed successfully.")

        except Exception as exc:
            db.session.rollback()
            print("\n[FATAL] Migration aborted -- full transaction rolled back.")
            print(f"        Cause: {exc}")
            print(traceback.format_exc())
            sys.exit(1)

    print_summary(dry_run)


if __name__ == "__main__":
    main()
