import discord
from discord import app_commands
from sqlalchemy import select
from database.models import GachaCard
from commands.gacha._gacha_utils import STAR_EMOJIS, RARITY_COLORS, get_character_data, get_character_image_for_session

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
            image = await get_character_image_for_session(session, card.character_name)
            _, data = get_character_data(card.character_name)

        embed = discord.Embed(title=card.character_name, color=color)
        embed.add_field(name="Rarity",     value=stars,                                      inline=True)
        embed.add_field(name="Level",      value=str(card.level),                            inline=True)
        embed.add_field(name="Owned Since",value=card.created_at.strftime("%d %b %Y"),       inline=True)
        if data is not None:
            embed.add_field(name="Element", value=data["element"].title(), inline=True)
            embed.add_field(name="Health", value=str(data["health"]), inline=True)
            embed.add_field(
                name="Normal",
                value=(
                    f"{data['normal_attack']['name']}\n"
                    f"DMG {data['normal_attack']['damage']} | CD {data['normal_attack']['cooldown']}"
                ),
                inline=False,
            )
            embed.add_field(
                name="Secondary",
                value=(
                    f"{data['secondary_attack']['name']}\n"
                    f"DMG {data['secondary_attack']['damage']} | CD {data['secondary_attack']['cooldown']}"
                ),
                inline=False,
            )
            embed.add_field(
                name="Power",
                value=(
                    f"{data['power_attack']['name']}\n"
                    f"DMG {data['power_attack']['damage']} | CD {data['power_attack']['cooldown']}"
                ),
                inline=False,
            )
        if image:
            embed.set_image(url=image)

        await interaction.response.send_message(embed=embed)
