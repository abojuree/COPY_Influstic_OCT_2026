#!/usr/bin/env python
"""
Script to fix migration issues by merging multiple heads.
This should be run locally, not on production.
"""
import os
import subprocess
from pathlib import Path
import sys

def main():
    """Merge multiple migration heads."""
    print("This script will help fix migration issues by merging multiple heads.")
    print("WARNING: Make sure you have a backup of your database before proceeding.")
    
    # Check if Flask is installed
    try:
        import flask
    except ImportError:
        print("Flask is not installed. Please install it first.")
        return
    
    # Check if Flask-Migrate is installed
    try:
        import flask_migrate
    except ImportError:
        print("Flask-Migrate is not installed. Please install it first.")
        return
    
    # Get the current migration heads
    print("Checking current migration heads...")
    result = subprocess.run(["flask", "db", "heads"], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error checking migration heads: {result.stderr}")
        return
    
    heads = result.stdout.strip().split("\n")
    print(f"Found {len(heads)} migration heads:")
    for head in heads:
        print(f"  - {head}")
    
    if len(heads) <= 1:
        print("No multiple heads detected. No action needed.")
        return
    
    # Ask for confirmation
    confirm = input("Do you want to merge these heads? (y/n): ")
    if confirm.lower() != "y":
        print("Operation cancelled.")
        return
    
    # Merge the heads
    print("Merging migration heads...")
    merge_result = subprocess.run(["flask", "db", "merge", "heads", "-m", "merge_heads"], capture_output=True, text=True)
    
    if merge_result.returncode != 0:
        print(f"Error merging migration heads: {merge_result.stderr}")
        return
    
    print("Migration heads merged successfully.")
    print("You can now run 'flask db upgrade' to apply the merged migration.")

if __name__ == "__main__":
    main()
