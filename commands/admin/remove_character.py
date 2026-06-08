import discord
from discord import app_commands
from sqlalchemy import delete

from commands.gacha._gacha_utils import load_pool, save_pool
from database.models import GachaCharacterAsset

name        = "remove-character"
description = "Remove a character from the gacha pool (Developer only)"

DEVELOPER_ROLE_ID = 1457710235069186349


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(character_name="Name of the character to remove")
    async def remove_character(interaction, character_name: str):
        if DEVELOPER_ROLE_ID not in {role.id for role in interaction.user.roles}:
            await interaction.response.send_message("Only Developers can use this.", ephemeral=True)
            return

        pool    = load_pool()
        removed = False
        rarity_found = None

        for rarity_key, data in pool.items():
            for char in data["characters"]:
                if char["name"].lower() == character_name.lower():
                    data["characters"].remove(char)
                    rarity_found = rarity_key
                    removed      = True
                    break
            if removed:
                break

        if not removed:
            await interaction.response.send_message(
                f"**{character_name}** not found in the gacha pool.", ephemeral=True,
            )
            return

        save_pool(pool)

        async with database.session() as session:
            await session.execute(
                delete(GachaCharacterAsset).where(GachaCharacterAsset.character_name.ilike(character_name))
            )
            await session.commit()

        embed = discord.Embed(title="✅ Character Removed", color=discord.Color.red())
        embed.add_field(name="Name",   value=character_name,              inline=True)
        embed.add_field(name="Rarity", value="⭐" * int(rarity_found),   inline=True)

        await interaction.response.send_message(embed=embed)
