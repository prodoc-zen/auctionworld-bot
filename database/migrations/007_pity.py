from database.models import Base


async def upgrade(connection):
    await connection.run_sync(Base.metadata.create_all)
