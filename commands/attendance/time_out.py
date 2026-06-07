from sqlalchemy import select

from database.models import AttendanceRecord, utc_now

name        = "timeout"
description = "Record a time-out attendance log"


def register(tree, database):
    @tree.command(name=name, description=description)
    async def timeout(interaction):
        discord_id = interaction.user.id

        async with database.session() as session:
            result = await session.execute(
                select(AttendanceRecord)
                .where(
                    AttendanceRecord.discord_id == discord_id,
                    AttendanceRecord.time_out_at.is_(None),
                )
                .order_by(AttendanceRecord.time_in_at.desc())
                .limit(1)
            )
            record = result.scalar_one_or_none()

            if record is None:
                await interaction.response.send_message(
                    f"{interaction.user.mention}, you do not have an active time-in.",
                    ephemeral=True,
                )
                return

            record.time_out_at = utc_now()
            await session.commit()

        await interaction.response.send_message(
            f"{interaction.user.mention}, your time-out has been recorded."
        )
