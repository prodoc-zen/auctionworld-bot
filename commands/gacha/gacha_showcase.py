import discord
from discord import app_commands
from sqlalchemy import select
from database.models import GachaCard, GachaShowcase
from commands.gacha._gacha_utils import STAR_EMOJIS

name        = "gacha-showcase"
description = "Choose up to 3 characters to showcase on your profile"

SHOWCASE_SLOTS = 3


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        slot="Showcase slot (1, 2, or 3)",
        character_name="Character to place in this slot (leave blank to clear slot)",
    )
    async def gacha_showcase(
        interaction,
        slot: int,
        character_name: str = None,
    ):
        if slot < 1 or slot > SHOWCASE_SLOTS:
            await interaction.response.send_message(
                f"Slot must be 1, 2, or 3.", ephemeral=True,
            )
            return

        discord_id = interaction.user.id

        async with database.session() as session:
            # Find or create the showcase slot
            result = await session.execute(
                select(GachaShowcase).where(
                    GachaShowcase.discord_id == discord_id,
                    GachaShowcase.slot == slot,
                )
            )
            showcase = result.scalar_one_or_none()

            if character_name is None:
                # Clear the slot
                if showcase:
                    showcase.card_id = None
                await session.commit()
                await interaction.response.send_message(
                    f"Slot {slot} cleared.", ephemeral=True,
                )
                return

            # Find the card
            card_result = await session.execute(
                select(GachaCard).where(
                    GachaCard.discord_id == discord_id,
                    GachaCard.character_name.ilike(character_name),
                )
            )
            card = card_result.scalar_one_or_none()

            if card is None:
                await interaction.response.send_message(
                    f"You don't own **{character_name}**.", ephemeral=True,
                )
                return

            if showcase is None:
                showcase = GachaShowcase(discord_id=discord_id, slot=slot, card_id=card.id)
                session.add(showcase)
            else:
                showcase.card_id = card.id

            await session.commit()

        stars = STAR_EMOJIS[card.rarity]
        await interaction.response.send_message(
            f"Slot {slot} set to {stars} **{card.character_name}** (Lv.{card.level}).",
            ephemeral=True,
        )
