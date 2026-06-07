from sqlalchemy import select

from database.models import AttendanceRecord, User

name        = "timein"
description = "Record a time-in attendance log"


def register(tree, database):
    @tree.command(name=name, description=description)
    async def timein(interaction):
        discord_id = interaction.user.id

        async with database.session() as session:
            result = await session.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.discord_id == discord_id,
                    AttendanceRecord.time_out_at.is_(None),
                )
            )
            if result.scalar_one_or_none() is not None:
                await interaction.response.send_message(
                    f"{interaction.user.mention}, you are already timed in.",
                    ephemeral=True,
                )
                return

            if await session.get(User, discord_id) is None:
                session.add(User(discord_id=discord_id, jennies=0))

            session.add(AttendanceRecord(discord_id=discord_id))
            await session.commit()

        await interaction.response.send_message(
            f"{interaction.user.mention}, your time-in has been recorded."
        )
