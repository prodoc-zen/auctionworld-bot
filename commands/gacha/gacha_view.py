import discord
from discord import app_commands
from sqlalchemy import select
from database.models import GachaCard
from commands.gacha._gacha_utils import STAR_EMOJIS, RARITY_COLORS, get_character_image

name        = "gacha-view"
description = "View a specific character you own"


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(character_name="Name of the character to view")
    async def gacha_view(interaction, character_name: str):
        discord_id = interaction.user.id

        async with database.session() as session:
            result = await session.execute(
                select(GachaCard).where(
                    GachaCard.discord_id == discord_id,
                    GachaCard.character_name.ilike(character_name),
                )
            )
            card = result.scalar_one_or_none()

        if card is None:
            await interaction.response.send_message(
                f"You don't own a character named **{character_name}**.", ephemeral=True,
            )
            return

        stars = STAR_EMOJIS[card.rarity]
        color = RARITY_COLORS[card.rarity]
        image = get_character_image(card.character_name)

        embed = discord.Embed(title=card.character_name, color=color)
        embed.add_field(name="Rarity",     value=stars,                                      inline=True)
        embed.add_field(name="Level",      value=str(card.level),                            inline=True)
        embed.add_field(name="Owned Since",value=card.created_at.strftime("%d %b %Y"),       inline=True)
        if image:
            embed.set_image(url=image)

        await interaction.response.send_message(embed=embed)
