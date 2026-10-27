#!/usr/bin/env python
"""
Database backup utility for SocialScannerWeb.
This script creates a backup of the PostgreSQL database and saves it locally.
"""
import os
import sys
import datetime
import subprocess
import argparse
from dotenv import load_dotenv

def load_environment():
    """Load environment variables from .env file"""
    # Determine the environment and load the appropriate .env file
    basedir = os.path.dirname(os.path.abspath(__file__))
    if os.getenv("FLASK_ENV") == "production":
        dotenv_path = os.path.join(basedir, ".env.prod")
    else:
        dotenv_path = os.path.join(basedir, ".env.dev")
    
    load_dotenv(dotenv_path)
    
    # Get database connection details
    db_engine = os.getenv("DB_ENGINE", "postgresql")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5433")
    db_name = os.getenv("DB_NAME", "socialscannerdb")
    db_user = os.getenv("DB_USERNAME", "admin")
    db_pass = os.getenv("DB_PASS", "")
    
    return {
        "engine": db_engine,
        "host": db_host,
        "port": db_port,
        "name": db_name,
        "user": db_user,
        "pass": db_pass
    }

def create_backup(output_dir=None, filename=None):
    # Load database configuration
    db_config = load_environment()
    """Create a PostgreSQL database backup using pg_dump"""
    if not output_dir:
        # Default to a 'backups' directory in the current folder
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
    
    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate a filename with timestamp if not provided
    if not filename:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{db_config['name']}_{timestamp}.sql"
    
    # Full path to the backup file
    backup_path = os.path.join(output_dir, filename)
    
    # Build the pg_dump command
    pg_dump_cmd = [
        "pg_dump",
        "-h", db_config["host"],
        "-p", db_config["port"],
        "-U", db_config["user"],
        "-d", db_config["name"],
        "-F", "c",  # Custom format (compressed)
        "-f", backup_path
    ]
    
    # Set the PGPASSWORD environment variable for authentication
    env = os.environ.copy()
    env["PGPASSWORD"] = db_config["pass"]
    
    try:
        print(f"Creating backup of database '{db_config['name']}' to {backup_path}...")
        process = subprocess.run(
            pg_dump_cmd,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(f"Backup completed successfully: {backup_path}")
        return backup_path
    except subprocess.CalledProcessError as e:
        print(f"Error creating backup: {e}")
        print(f"stderr: {e.stderr.decode('utf-8')}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

def main():
    """Main function to run the backup script"""
    parser = argparse.ArgumentParser(description="Create a backup of the PostgreSQL database")
    parser.add_argument("--output-dir", help="Directory to save the backup file")
    parser.add_argument("--filename", help="Name of the backup file")
    args = parser.parse_args()
    
    # Create the backup
    backup_path = create_backup(output_dir=args.output_dir, filename=args.filename)
    
    if backup_path:
        print(f"Backup saved to: {backup_path}")
        return 0
    else:
        print("Backup failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
