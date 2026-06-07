from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database.models import Transaction, User

name        = "daily"
description = "Claim a daily Jennies reward"

REWARD_AMOUNT = 100


def register(tree, database):
    @tree.command(name=name, description=description)
    async def daily(interaction):
        discord_id = interaction.user.id
        today      = datetime.now(timezone.utc).date().isoformat()
        reason     = f"daily:{today}"

        async with database.session() as session:
            result = await session.execute(select(User).where(User.discord_id == discord_id))
            user   = result.scalar_one_or_none()

            if user is None:
                user = User(discord_id=discord_id, jennies=0)
                session.add(user)

            user.jennies += REWARD_AMOUNT
            session.add(Transaction(discord_id=discord_id, amount=REWARD_AMOUNT, reason=reason))

            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                await interaction.response.send_message(
                    f"{interaction.user.mention}, you already claimed today's reward.",
                    ephemeral=True,
                )
                return

        await interaction.response.send_message(
            f"{interaction.user.mention}, you claimed {REWARD_AMOUNT} Jennies."
        )
