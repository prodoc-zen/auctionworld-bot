import discord
from discord import app_commands
from commands.gacha._gacha_utils import load_pool, save_pool

name        = "add-character"
description = "Add a new character to the gacha pool (Developer only)"

DEVELOPER_ROLE_ID = 1457710235069186349

RARITY_CHOICES = [
    app_commands.Choice(name="1 Star", value=1),
    app_commands.Choice(name="2 Star", value=2),
    app_commands.Choice(name="3 Star", value=3),
    app_commands.Choice(name="4 Star", value=4),
]


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        character_name="Name of the character",
        rarity="Star rarity (1-4)",
        image_url="Image URL for the character (optional)",
    )
    @app_commands.choices(rarity=RARITY_CHOICES)
    async def add_character(
        interaction,
        character_name: str,
        rarity: app_commands.Choice[int],
        image_url: str = None,
    ):
        if DEVELOPER_ROLE_ID not in {role.id for role in interaction.user.roles}:
            await interaction.response.send_message("Only Developers can use this.", ephemeral=True)
            return

        pool       = load_pool()
        rarity_key = str(rarity.value)

        # Check for duplicate
        for r, data in pool.items():
            for char in data["characters"]:
                if char["name"].lower() == character_name.lower():
                    await interaction.response.send_message(
                        f"**{character_name}** already exists as a {r}★ character.", ephemeral=True,
                    )
                    return

        pool[rarity_key]["characters"].append({
            "name":  character_name,
            "image": image_url,
        })
        save_pool(pool)

        stars = "⭐" * rarity.value
        embed = discord.Embed(title="✅ Character Added", color=discord.Color.green())
        embed.add_field(name="Name",   value=character_name, inline=True)
        embed.add_field(name="Rarity", value=stars,          inline=True)
        if image_url:
            embed.set_image(url=image_url)

        await interaction.response.send_message(embed=embed)
