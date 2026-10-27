#!/usr/bin/env python
"""
Database utility functions for the admin page.
Provides functionality for database backup and export.
"""
import os
import datetime
import subprocess
import tempfile
import pandas as pd
from sqlalchemy import inspect, text
from flask import current_app
from io import BytesIO

def get_db_config():
    """Get database configuration from Flask app config"""
    db_engine = current_app.config.get("DB_ENGINE", "postgresql")
    db_host = current_app.config.get("DB_HOST", "localhost")
    db_port = current_app.config.get("DB_PORT", "5433")
    db_name = current_app.config.get("DB_NAME", "socialscannerdb")
    db_user = current_app.config.get("DB_USERNAME", "admin")
    db_pass = current_app.config.get("DB_PASS", "")

    return {
        "engine": db_engine,
        "host": db_host,
        "port": db_port,
        "name": db_name,
        "user": db_user,
        "pass": db_pass
    }

def create_db_backup():
    """
    Create a database backup and return the file path.
    First tries using pg_dump, then falls back to SQLAlchemy if pg_dump fails.

    Returns:
        tuple: (success, file_path_or_error_message)
    """
    from icecream import ic

    db_config = get_db_config()

    # Create a backup directory in the static folder to ensure it's accessible
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                             'apps', 'static', 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    ic(f"Created backup directory: {backup_dir}")

    # Generate a filename with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{db_config['name']}_{timestamp}.sql"

    # Full path to the backup file
    backup_path = os.path.join(backup_dir, filename)
    ic(f"Backup file path: {backup_path}")

    # Try pg_dump first
    try:
        ic("Attempting to use pg_dump method...")

        # Build the pg_dump command
        pg_dump_cmd = [
            "pg_dump",
            "-h", db_config["host"],
            "-p", str(db_config["port"]),
            "-U", db_config["user"],
            "-d", db_config["name"],
            "-F", "c",  # Custom format (compressed)
            "-f", backup_path
        ]

        ic(f"pg_dump command: {' '.join(pg_dump_cmd)}")

        # Set the PGPASSWORD environment variable for authentication
        env = os.environ.copy()
        env["PGPASSWORD"] = db_config["pass"]

        current_app.logger.info(f"Creating backup of database '{db_config['name']}' using pg_dump...")

        # Run the pg_dump command
        result = subprocess.run(
            pg_dump_cmd,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Check if the file was created and has content
        if os.path.exists(backup_path) and os.path.getsize(backup_path) > 0:
            # Log success with detailed information
            file_size = os.path.getsize(backup_path)
            file_size_mb = file_size / (1024 * 1024)

            success_details = (
                f"pg_dump method successful!\n"
                f"Backup file: {backup_path}\n"
                f"Backup file size: {file_size_mb:.2f} MB ({file_size} bytes)\n"
                f"Backup time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            ic(success_details)
            current_app.logger.info(success_details)

            # Create a marker file to indicate which method was used
            with open(f"{backup_path}.method", "w", encoding='utf-8') as f:
                f.write("pg_dump")

            return True, backup_path
        else:
            ic("pg_dump created an empty or missing file, falling back to SQLAlchemy method")
            return create_db_backup_sqlalchemy(backup_path)

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        # If pg_dump fails or is not found, try SQLAlchemy approach
        error_details = str(e)
        if hasattr(e, 'stderr') and e.stderr:
            error_details += f"\nStderr: {e.stderr}"

        ic(f"pg_dump failed: {error_details}")
        current_app.logger.warning(f"pg_dump failed: {error_details}. Falling back to SQLAlchemy method.")
        return create_db_backup_sqlalchemy(backup_path)

    except Exception as e:
        error_msg = f"Unexpected error with pg_dump: {str(e)}"
        ic(error_msg)
        import traceback
        ic(traceback.format_exc())
        current_app.logger.error(error_msg)
        return False, error_msg


def create_db_backup_sqlalchemy(backup_path):
    """
    Create a database backup using SQLAlchemy instead of pg_dump.

    Args:
        backup_path: Path where to save the backup file

    Returns:
        tuple: (success, file_path_or_error_message)
    """
    try:
        from sqlalchemy import inspect, text
        from flask import current_app
        from icecream import ic
        from apps import db  # Import db directly from apps package

        ic("Using SQLAlchemy method for database backup")
        current_app.logger.info("Creating database backup using SQLAlchemy...")

        with open(backup_path, 'w', encoding='utf-8') as f:
            # Get all table names
            inspector = inspect(db.engine)
            table_names = inspector.get_table_names()
            ic(f"Found {len(table_names)} tables to backup")

            # Write header
            f.write(f"-- Database backup created on {datetime.datetime.now()}\n")
            f.write(f"-- Tables: {', '.join(table_names)}\n")
            f.write(f"-- Backup method: SQLAlchemy\n\n")

            # Process each table
            total_rows = 0
            for table_name in table_names:
                ic(f"Backing up table: {table_name}")
                current_app.logger.info(f"Backing up table: {table_name}")

                # Get table schema (columns)
                columns = inspector.get_columns(table_name)
                column_names = [col['name'] for col in columns]

                f.write(f"\n-- Table: {table_name}\n")
                f.write(f"-- Columns: {', '.join(column_names)}\n\n")

                # Get table data
                # Use double quotes to preserve case in PostgreSQL
                query = text(f'SELECT * FROM "{table_name}"')
                result = db.session.execute(query)
                rows = result.fetchall()

                ic(f"Table {table_name}: {len(rows)} rows")
                total_rows += len(rows)

                if rows:
                    # Write INSERT statements with double quotes for table name and column names
                    column_names_quoted = [f'"{col}"' for col in column_names]
                    f.write(f'INSERT INTO "{table_name}" ({", ".join(column_names_quoted)}) VALUES\n')

                    for i, row in enumerate(rows):
                        values = []
                        for val in row:
                            if val is None:
                                values.append('NULL')
                            elif isinstance(val, (int, float)):
                                values.append(str(val))
                            elif isinstance(val, (datetime.date, datetime.datetime)):
                                values.append(f"'{val.isoformat()}'")
                            elif isinstance(val, dict):
                                # Handle JSON/JSONB data
                                import json
                                json_str = json.dumps(val).replace("'", "''")
                                values.append(f"'{json_str}'")
                            else:
                                # Escape single quotes in string values
                                val_str = str(val).replace("'", "''")
                                values.append(f"'{val_str}'")

                        line = f"({', '.join(values)})"
                        if i < len(rows) - 1:
                            line += ","
                        f.write(line + "\n")

                    f.write(";\n\n")

        # Create a marker file to indicate which method was used
        with open(f"{backup_path}.method", "w", encoding='utf-8') as f:
            f.write("sqlalchemy")

        # Log success with detailed information
        file_size = os.path.getsize(backup_path)
        file_size_mb = file_size / (1024 * 1024)

        success_details = (
            f"SQLAlchemy backup completed successfully: {backup_path}\n"
            f"Total tables: {len(table_names)}\n"
            f"Total rows: {total_rows}\n"
            f"Backup file size: {file_size_mb:.2f} MB ({file_size} bytes)\n"
            f"Backup time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        ic(success_details)
        current_app.logger.info(success_details)

        return True, backup_path

    except Exception as e:
        error_msg = f"Error creating backup with SQLAlchemy: {str(e)}"
        ic(error_msg)
        import traceback
        tb = traceback.format_exc()
        ic(tb)
        current_app.logger.error(error_msg)
        current_app.logger.error(tb)
        return False, error_msg

def export_db_to_excel(db):
    """
    Export all database tables to an Excel workbook.
    Each table will be a separate sheet in the workbook.

    Args:
        db: SQLAlchemy database instance

    Returns:
        tuple: (success, file_or_error_message)
    """
    from icecream import ic

    try:
        # Create a backup directory in the static folder to ensure it's accessible
        export_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                'apps', 'static', 'exports')
        os.makedirs(export_dir, exist_ok=True)
        ic(f"Created export directory: {export_dir}")

        # Generate a filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"database_export_{timestamp}.xlsx"
        export_path = os.path.join(export_dir, filename)
        ic(f"Export file path: {export_path}")

        # Get all table names
        inspector = inspect(db.engine)
        table_names = inspector.get_table_names()
        ic(f"Found {len(table_names)} tables to export")

        # Create an Excel writer object
        with pd.ExcelWriter(export_path, engine='openpyxl') as writer:
            for table_name in table_names:
                current_app.logger.info(f"Exporting table: {table_name}")

                # Read SQL table directly into Pandas DataFrame
                df = pd.read_sql_table(table_name, db.engine)
                
                # Strip timezone information because Excel doesn't support it
                for col in df.select_dtypes(include=['datetimetz', 'datetime64[ns, UTC]']).columns:
                    df[col] = df[col].dt.tz_localize(None)

                # 1. Security: Remove password hashes/memory pointers
                if table_name.lower() == 'users':
                    df = df.drop(columns=['password'], errors='ignore')

                # 2. File Size: Remove raw RapidAPI JSON payloads
                if table_name.lower() == 'social_posts':
                    df = df.drop(columns=['raw_data'], errors='ignore')

                # Write DataFrame to a specific sheet in the Excel file
                # Sheet names in Excel cannot exceed 31 characters
                sheet_name = table_name[:31]
                df.to_excel(writer, sheet_name=sheet_name, index=False)

        # Log success with detailed information
        file_size = os.path.getsize(export_path)
        file_size_mb = file_size / (1024 * 1024)

        success_details = (
            f"Excel export completed successfully!\n"
            f"Export file: {export_path}\n"
            f"Tables exported: {len(table_names)}\n"
            f"Export file size: {file_size_mb:.2f} MB ({file_size} bytes)\n"
            f"Export time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        ic(success_details)
        current_app.logger.info(success_details)

        # Return the full file path
        return True, export_path

    except Exception as e:
        error_msg = f"Error exporting database to CSV: {str(e)}"
        current_app.logger.error(error_msg)
        import traceback
        tb = traceback.format_exc()
        ic(tb)
        return False, error_msg
