"""Dev-mode bootstrap (SQLite, no Docker): create missing tables, add missing
columns non-destructively, seed demo data. Production uses alembic + TimescaleDB."""
from sqlalchemy import inspect, text

from app.core.database import Base, engine
from app import models  # noqa: F401
from app.simulation.seed import seed


def _add_missing_columns() -> None:
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                ddl = col.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN "{col.name}" {ddl}'))
                print(f"  added column {table.name}.{col.name}")


def main() -> None:
    print(f"schema at {engine.url}")
    Base.metadata.create_all(engine)
    _add_missing_columns()
    seed()
    from app.core.database import SessionLocal
    from app.services import rotation_store
    with SessionLocal() as db:
        print("  rotation rules:", rotation_store.sync_rules(db))
        print("  rotation data moved to tables:", rotation_store.migrate_legacy(db))
    print("dev bootstrap complete")


if __name__ == "__main__":
    main()
