"""
SQLite -> PostgreSQL migration script.

Usage (PowerShell):
  $env:SOURCE_SQLITE_PATH="data/experiment.db"
  $env:TARGET_DATABASE_URL="postgresql+psycopg2://user:password@host:5432/dbname"
  python scripts/migrate_sqlite_to_postgres.py

Optional flags:
  --source-sqlite-path <path>
  --target-database-url <url>
  --no-truncate-target

By default, target tables are truncated before importing to keep the migration idempotent.
"""

import argparse
import os
import sys
from typing import Dict, List, Type

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add project root to import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import (  # noqa: E402
    Base,
    User,
    UserTask,
    ChatMessage,
    ExperimentLog,
    UserProfile,
    UserSession,
)


def _mask_url(url: str) -> str:
    if not url:
        return ""
    if "@" not in url:
        return url
    left, right = url.rsplit("@", 1)
    scheme = left.split("://", 1)[0] if "://" in left else left
    return f"{scheme}://***@{right}"


def _rows_to_payloads(rows: List[object], model: Type[Base]) -> List[Dict]:
    payloads = []
    for row in rows:
        data = {}
        for column in model.__table__.columns:
            if column.name == "id":
                continue
            data[column.name] = getattr(row, column.name)
        payloads.append(data)
    return payloads


def migrate(
    source_sqlite_path: str,
    target_database_url: str,
    truncate_target: bool = True,
) -> None:
    source_url = f"sqlite:///{source_sqlite_path}"

    source_engine = create_engine(source_url, pool_pre_ping=True, connect_args={"check_same_thread": False})
    target_engine = create_engine(target_database_url, pool_pre_ping=True)

    SourceSession = sessionmaker(bind=source_engine, autocommit=False, autoflush=False)
    TargetSession = sessionmaker(bind=target_engine, autocommit=False, autoflush=False)

    # Ensure target schema exists.
    Base.metadata.create_all(target_engine)

    # Import order follows FK dependencies.
    import_order: List[Type[Base]] = [
        User,
        UserTask,
        ChatMessage,
        ExperimentLog,
        UserProfile,
        UserSession,
    ]
    truncate_order = list(reversed(import_order))

    src = SourceSession()
    dst = TargetSession()
    try:
        print("=" * 70)
        print("SQLite -> PostgreSQL migration")
        print(f"Source: {source_sqlite_path}")
        print(f"Target: {_mask_url(target_database_url)}")
        print(f"Truncate target: {truncate_target}")
        print("=" * 70)

        if truncate_target:
            print("\n[1/3] Truncating target tables...")
            for model in truncate_order:
                deleted = dst.query(model).delete(synchronize_session=False)
                print(f"  - {model.__tablename__}: deleted {deleted}")
            dst.commit()
            print("  ✓ Target cleanup completed")
        else:
            print("\n[1/3] Skipping truncate step")

        print("\n[2/3] Migrating table data...")
        stats = {}
        for model in import_order:
            rows = src.query(model).all()
            payloads = _rows_to_payloads(rows, model)
            if payloads:
                dst.bulk_insert_mappings(model, payloads)
            stats[model.__tablename__] = len(payloads)
            print(f"  - {model.__tablename__}: inserted {len(payloads)}")
        dst.commit()

        print("\n[3/3] Verifying counts on target...")
        for model in import_order:
            count = dst.query(model).count()
            print(f"  - {model.__tablename__}: {count}")

        print("\nMigration completed successfully.")
    except Exception:
        dst.rollback()
        raise
    finally:
        src.close()
        dst.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate data from SQLite to PostgreSQL")
    parser.add_argument(
        "--source-sqlite-path",
        default=os.environ.get("SOURCE_SQLITE_PATH", "data/experiment.db"),
        help="Path to source SQLite database file (default: data/experiment.db or SOURCE_SQLITE_PATH)",
    )
    parser.add_argument(
        "--target-database-url",
        default=os.environ.get("TARGET_DATABASE_URL") or os.environ.get("DATABASE_URL"),
        help="PostgreSQL SQLAlchemy URL (or set TARGET_DATABASE_URL / DATABASE_URL)",
    )
    parser.add_argument(
        "--no-truncate-target",
        action="store_true",
        help="Do not clear target tables before migration",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.target_database_url:
        print("ERROR: target database URL is required. Set --target-database-url or TARGET_DATABASE_URL.")
        return 1
    if not os.path.exists(args.source_sqlite_path):
        print(f"ERROR: source sqlite file not found: {args.source_sqlite_path}")
        return 1
    if not args.target_database_url.startswith("postgresql"):
        print("ERROR: target database must be a PostgreSQL URL.")
        return 1

    migrate(
        source_sqlite_path=args.source_sqlite_path,
        target_database_url=args.target_database_url,
        truncate_target=not args.no_truncate_target,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
