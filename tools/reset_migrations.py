#!/usr/bin/env python
"""
Script to reset migrations by creating a new initial migration based on current schema.
This should be run locally, not on production.
"""
import os
import shutil
import subprocess
from pathlib import Path

def main():
    """Reset migrations and create a new initial migration."""
    # Get the migrations directory
    migrations_dir = Path("migrations")
    
    if not migrations_dir.exists():
        print("Migrations directory not found. Make sure you're in the project root.")
        return
    
    # Backup the migrations directory
    backup_dir = Path("migrations_backup")
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    
    shutil.copytree(migrations_dir, backup_dir)
    print(f"Backed up migrations to {backup_dir}")
    
    # Remove all migration files except the directory structure and __init__.py files
    versions_dir = migrations_dir / "versions"
    if versions_dir.exists():
        for file_path in versions_dir.glob("*.py"):
            if file_path.name != "__init__.py":
                file_path.unlink()
                print(f"Removed {file_path}")
    
    # Initialize a new migration
    print("Initializing new migration...")
    subprocess.run(["flask", "db", "init"], check=False)
    
    # Create a new initial migration
    print("Creating new migration...")
    subprocess.run(["flask", "db", "migrate", "-m", "Initial migration after reset"], check=False)
    
    print("Migration reset complete. Review the new migration file before applying it.")
    print("To apply the migration, run: flask db upgrade")

if __name__ == "__main__":
    main()
