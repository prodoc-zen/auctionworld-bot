from sqlalchemy import select

from database.models import User


name = "balance"
description = "Check your Jennies balance"


def register(tree, database):
    @tree.command(name=name, description=description)
    async def balance(interaction):
        discord_id = interaction.user.id

        async with database.session() as session:
            result = await session.execute(select(User).where(User.discord_id == discord_id))
            user = result.scalar_one_or_none()

            if user is None:
                user = User(discord_id=discord_id, jennies=0)
                session.add(user)
                await session.commit()

            await interaction.response.send_message(
                f"{interaction.user.mention}, you have {user.jennies} Jennies."
            )
