from sqlalchemy import desc, select

from database.models import User


name = "leaderboard"
description = "Show the top Jennies balances"


def register(tree, database):
    @tree.command(name=name, description=description)
    async def leaderboard(interaction):
        async with database.session() as session:
            result = await session.execute(
                select(User).order_by(desc(User.jennies)).limit(10)
            )
            users = result.scalars().all()

        if not users:
            await interaction.response.send_message("No Jennies balances yet.")
            return

        lines = [
            f"{index}. <@{user.discord_id}> - {user.jennies} Jennies"
            for index, user in enumerate(users, start=1)
        ]
        await interaction.response.send_message("Jennies Leaderboard\n" + "\n".join(lines))
