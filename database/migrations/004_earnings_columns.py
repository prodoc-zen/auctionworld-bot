from sqlalchemy import text


async def upgrade(connection):
    # Remove old earnings text column, add separate BGL/DL/WL columns
    await connection.execute(text(
        "ALTER TABLE attendance_records "
        "DROP COLUMN IF EXISTS earnings, "
        "ADD COLUMN IF NOT EXISTS bgls BIGINT NOT NULL DEFAULT 0, "
        "ADD COLUMN IF NOT EXISTS dls  BIGINT NOT NULL DEFAULT 0, "
        "ADD COLUMN IF NOT EXISTS wls  BIGINT NOT NULL DEFAULT 0"
    ))
