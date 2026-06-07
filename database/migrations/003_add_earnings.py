from sqlalchemy import text


async def upgrade(connection):
    await connection.execute(text(
        "ALTER TABLE attendance_records ADD COLUMN IF NOT EXISTS earnings VARCHAR(255) NULL"
    ))
