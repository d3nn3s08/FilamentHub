#!/usr/bin/env python3
"""
Migration: Add is_open column to spool table
Preserves all existing data with is_open=True as default
"""
import sqlite3
import os

DB_PATH = os.environ.get("FILAMENTHUB_DB_PATH", "data/filamenthub.db")

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found. Creating new database...")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if is_open column already exists
        cursor.execute("PRAGMA table_info(spool)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "is_open" in columns:
            print("✓ Column 'is_open' already exists in spool table")
            conn.close()
            return True
        
        # Add is_open column with default True (1)
        print("Adding 'is_open' column to spool table...")
        cursor.execute("ALTER TABLE spool ADD COLUMN is_open BOOLEAN NOT NULL DEFAULT 1")
        conn.commit()
        
        # Verify
        cursor.execute("PRAGMA table_info(spool)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "is_open" in columns:
            print("✓ Migration successful!")
            print(f"  Added 'is_open' column (default: True)")
            print(f"  All existing spools marked as opened")
            conn.close()
            return True
        else:
            print("✗ Migration failed - column not added")
            conn.close()
            return False
            
    except Exception as e:
        print(f"✗ Migration error: {e}")
        return False

if __name__ == "__main__":
    success = migrate()
    exit(0 if success else 1)
