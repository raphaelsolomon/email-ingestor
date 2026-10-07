#!/usr/bin/env python3
"""
Reset utility for Executive Email Intelligence system.

Usage:
  python3 src/reset.py                 # Interactive confirmation
  python3 src/reset.py --dry-run       # Preview what would be deleted
  python3 src/reset.py --force         # Skip confirmation
  python3 src/reset.py --force --dry-run  # Dry-run without confirmation
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

def get_db_path():
    """Get the database path."""
    return str(Path(__file__).resolve().parent.parent / "data" / "mailing.db")

def get_data_dir():
    """Get the data directory."""
    return str(Path(__file__).resolve().parent.parent / "data")

def calculate_size(path):
    """Calculate size of a file or directory in MB."""
    if not os.path.exists(path):
        return 0

    if os.path.isfile(path):
        return os.path.getsize(path) / (1024 * 1024)

    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.exists(filepath):
                total += os.path.getsize(filepath)
    return total / (1024 * 1024)

def preview_deletion():
    """Preview what will be deleted."""
    db_path = get_db_path()
    data_dir = get_data_dir()

    items_to_delete = []
    total_size_mb = 0

    # Database
    if os.path.exists(db_path):
        size_mb = calculate_size(db_path)
        items_to_delete.append(("Database", db_path, size_mb))
        total_size_mb += size_mb

    # Data directory (if it exists and has files other than .gitkeep)
    if os.path.exists(data_dir):
        for item in os.listdir(data_dir):
            if item == '.gitkeep':
                continue
            item_path = os.path.join(data_dir, item)
            if os.path.isfile(item_path):
                size_mb = calculate_size(item_path)
                items_to_delete.append(("Data file", item_path, size_mb))
                total_size_mb += size_mb

    return items_to_delete, total_size_mb

def confirm_deletion():
    """Ask user to confirm deletion."""
    items_to_delete, total_size_mb = preview_deletion()

    if not items_to_delete:
        print("✓ Nothing to delete (system already clean)")
        return False

    print("\n" + "="*60)
    print("RESET UTILITY - PREVIEW")
    print("="*60)
    print("\nThe following will be PERMANENTLY DELETED:\n")

    for category, path, size_mb in items_to_delete:
        print(f"  [{category}] {path}")
        print(f"             Size: {size_mb:.2f} MB")

    print(f"\nTotal data to be deleted: {total_size_mb:.2f} MB")
    print("\n" + "="*60)
    print("WARNING: This action cannot be undone!")
    print("="*60 + "\n")

    # Ask for confirmation
    response = input("Are you sure you want to delete all records? (type 'yes' to confirm): ")

    if response.lower() != 'yes':
        print("✗ Cancelled - no data was deleted")
        return False

    return True

def perform_reset(dry_run=False):
    """Perform the reset operation."""
    db_path = get_db_path()
    data_dir = get_data_dir()

    deleted_items = []

    # Delete database
    if os.path.exists(db_path):
        if dry_run:
            deleted_items.append(("Database", db_path))
        else:
            os.remove(db_path)
            deleted_items.append(("Database", db_path))

    # Delete data files (but keep .gitkeep)
    if os.path.exists(data_dir):
        for item in os.listdir(data_dir):
            if item == '.gitkeep':
                continue
            item_path = os.path.join(data_dir, item)
            if os.path.isfile(item_path):
                if dry_run:
                    deleted_items.append(("Data file", item_path))
                else:
                    os.remove(item_path)
                    deleted_items.append(("Data file", item_path))

    return deleted_items

def main():
    parser = argparse.ArgumentParser(
        description="Reset Executive Email Intelligence system"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be deleted without deleting"
    )

    args = parser.parse_args()

    # Check if there's anything to delete
    items_to_delete, total_size_mb = preview_deletion()

    if not items_to_delete:
        print("✓ System already clean - nothing to delete")
        sys.exit(0)

    # Get confirmation
    if args.force:
        confirmed = True
        if args.dry_run:
            print("DRY RUN MODE - Preview only (no data will be deleted)\n")
    else:
        confirmed = confirm_deletion()

    if not confirmed:
        sys.exit(1)

    # Perform reset
    if args.dry_run:
        print("\n[DRY RUN] The following would be deleted:\n")
        deleted_items = perform_reset(dry_run=True)
    else:
        print("\n⏳ Deleting system data...")
        deleted_items = perform_reset(dry_run=False)

    # Report results
    if deleted_items:
        print(f"\n{'='*60}")
        if args.dry_run:
            print("DRY RUN SUMMARY")
        else:
            print("RESET COMPLETE")
        print(f"{'='*60}\n")

        for category, path in deleted_items:
            status = "[PREVIEW]" if args.dry_run else "[DELETED]"
            print(f"  {status} {category}: {path}")

        print(f"\nTotal items: {len(deleted_items)}")

        if not args.dry_run:
            print("\n✓ System reset successfully")
            print("✓ Database cleared")
            print("✓ All records removed")
            print("\nYou can now run: python3 src/ingest.py <path_to_emails>")
    else:
        if args.dry_run:
            print("✓ Nothing would be deleted")
        else:
            print("✓ Nothing was deleted")

    print()

if __name__ == "__main__":
    main()
