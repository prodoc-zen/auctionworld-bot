import discord
from discord import app_commands
from commands.gacha._gacha_utils import load_pool, save_pool

name        = "set-character-image"
description = "Set or update a character's image (Developer only)"

DEVELOPER_ROLE_ID = 1457710235069186349


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        character_name="Name of the character",
        image_url="New image URL (leave blank to remove image)",
    )
    async def set_character_image(
        interaction,
        character_name: str,
        image_url: str = None,
    ):
        if DEVELOPER_ROLE_ID not in {role.id for role in interaction.user.roles}:
            await interaction.response.send_message("Only Developers can use this.", ephemeral=True)
            return

        pool    = load_pool()
        updated = False

        for rarity_key, data in pool.items():
            for char in data["characters"]:
                if char["name"].lower() == character_name.lower():
                    char["image"] = image_url
                    updated       = True
                    break
            if updated:
                break

        if not updated:
            await interaction.response.send_message(
                f"**{character_name}** not found in the gacha pool.", ephemeral=True,
            )
            return

        save_pool(pool)

        embed = discord.Embed(title="✅ Character Image Updated", color=discord.Color.blurple())
        embed.add_field(name="Character", value=character_name, inline=False)
        embed.add_field(name="Image",     value=image_url or "Removed", inline=False)
        if image_url:
            embed.set_image(url=image_url)

        await interaction.response.send_message(embed=embed)
