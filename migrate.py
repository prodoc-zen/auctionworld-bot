import asyncio
import argparse
import importlib.util
import json
import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from sqlalchemy import select, text
from database.db import Database
from database.models import Base, SchemaMigration


BASE_DIR = Path(__file__).resolve().parent
MIGRATIONS_DIR = BASE_DIR / "database" / "migrations"


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config():
    load_dotenv()
    with (BASE_DIR / "config.json").open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    database = config.setdefault("database", {})
    database["host"] = os.getenv("DB_HOST", database.get("host", "localhost"))
    database["user"] = os.getenv("DB_USER", database.get("user", "root"))
    database["password"] = os.getenv("DB_PASSWORD", database.get("password", ""))
    database["name"] = os.getenv("DB_NAME", database.get("name", "auctionworld"))
    database["port"] = int(os.getenv("DB_PORT", database.get("port", 3306)))
    database["echo"] = env_bool("DB_ECHO", database.get("echo", False))
    return database


def ensure_database_exists(config):
    database_name = config["name"]
    if not database_name.replace("_", "").isalnum():
        raise ValueError("DB_NAME may only contain letters, numbers, and underscores.")

    connection = pymysql.connect(
        host=config["host"],
        user=config["user"],
        password=config.get("password", ""),
        port=int(config.get("port", 3306)),
        charset="utf8mb4",
        autocommit=True,
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        connection.close()


def load_migration(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def run_migrations():
    config = load_config()
    ensure_database_exists(config)

    database = Database(config)
    await database.connect()

    try:
        async with database.engine.begin() as connection:
            await connection.run_sync(SchemaMigration.__table__.create, checkfirst=True)
            await connection.run_sync(Base.metadata.create_all)

        async with database.session() as session:
            result = await session.execute(select(SchemaMigration.version))
            applied = {row[0] for row in result.all()}

            for migration_path in sorted(MIGRATIONS_DIR.glob("*.py")):
                version = migration_path.stem
                if version in applied or migration_path.name.startswith("_"):
                    continue

                migration = load_migration(migration_path)
                async with database.engine.begin() as connection:
                    await migration.upgrade(connection)

                session.add(SchemaMigration(version=version))
                await session.commit()
                print(f"Applied migration: {version}")
    finally:
        await database.close()


async def refresh_database():
    config = load_config()
    ensure_database_exists(config)

    database = Database(config)
    await database.connect()

    try:
        async with database.engine.begin() as connection:
            await connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            result = await connection.execute(text("SHOW TABLES"))
            table_names = [row[0] for row in result]

            for table_name in table_names:
                escaped_name = table_name.replace("`", "``")
                await connection.execute(text(f"DROP TABLE IF EXISTS `{escaped_name}`"))

            await connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))

        print("Dropped all tables.")
    finally:
        await database.close()

    await run_migrations()


def parse_args():
    parser = argparse.ArgumentParser(description="AuctionWorld database migrations")
    parser.add_argument(
        "command",
        nargs="?",
        default="migrate",
        choices=("migrate", "migrate:refresh"),
        help="Migration command to run.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.command == "migrate:refresh":
        asyncio.run(refresh_database())
    else:
        asyncio.run(run_migrations())
