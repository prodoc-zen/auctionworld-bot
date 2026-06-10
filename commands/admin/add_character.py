import discord
from discord import app_commands
from sqlalchemy import select

from commands.gacha._gacha_utils import ELEMENT_TYPES, load_pool, normalize_character_data, save_pool
from database.models import GachaCharacterAsset

name        = "add-character"
description = "Add a new character to the gacha pool (Developer only)"

DEVELOPER_ROLE_ID = 1457710235069186349

RARITY_CHOICES = [
    app_commands.Choice(name="1 Star", value=1),
    app_commands.Choice(name="2 Star", value=2),
    app_commands.Choice(name="3 Star", value=3),
    app_commands.Choice(name="4 Star", value=4),
]

ELEMENT_CHOICES = [
    app_commands.Choice(name="Fire", value="fire"),
    app_commands.Choice(name="Water", value="water"),
    app_commands.Choice(name="Earth", value="earth"),
    app_commands.Choice(name="Wind", value="wind"),
    app_commands.Choice(name="Light", value="light"),
    app_commands.Choice(name="Dark", value="dark"),
]


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        character_name="Name of the character",
        rarity="Star rarity (1-4)",
        image_url="Image URL for the character (optional)",
        image_file="Upload character image file (optional)",
        health="Character health (default 100)",
        element="Element type",
        normal_attack_name="Normal attack name",
        normal_attack_damage="Normal attack damage",
        normal_attack_cooldown="Normal attack cooldown",
        secondary_attack_name="Secondary attack name",
        secondary_attack_damage="Secondary attack damage",
        secondary_attack_cooldown="Secondary attack cooldown",
        power_attack_name="Power attack name",
        power_attack_damage="Power attack damage",
        power_attack_cooldown="Power attack cooldown",
    )
    @app_commands.choices(rarity=RARITY_CHOICES)
    @app_commands.choices(element=ELEMENT_CHOICES)
    async def add_character(
        interaction,
        character_name: str,
        rarity: app_commands.Choice[int],
        image_url: str = None,
        image_file: discord.Attachment = None,
        health: int = 100,
        element: app_commands.Choice[str] = None,
        normal_attack_name: str = "Basic Strike",
        normal_attack_damage: int = 12,
        normal_attack_cooldown: int = 0,
        secondary_attack_name: str = "Skill",
        secondary_attack_damage: int = 24,
        secondary_attack_cooldown: int = 2,
        power_attack_name: str = "Ultimate",
        power_attack_damage: int = 40,
        power_attack_cooldown: int = 4,
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

        if health <= 0:
            await interaction.response.send_message("Health must be greater than 0.", ephemeral=True)
            return

        for dmg in [normal_attack_damage, secondary_attack_damage, power_attack_damage]:
            if dmg <= 0:
                await interaction.response.send_message("Attack damage must be greater than 0.", ephemeral=True)
                return

        for cd in [normal_attack_cooldown, secondary_attack_cooldown, power_attack_cooldown]:
            if cd < 0:
                await interaction.response.send_message("Cooldown cannot be negative.", ephemeral=True)
                return

        image_blob = None
        image_mime = None
        if image_file is not None:
            if image_file.content_type is None or not image_file.content_type.startswith("image/"):
                await interaction.response.send_message("Uploaded file must be an image.", ephemeral=True)
                return
            image_blob = await image_file.read()
            image_mime = image_file.content_type
            image_url = image_url or image_file.url

        char_payload = normalize_character_data({
            "name":  character_name,
            "image": image_url,
            "health": health,
            "element": (element.value if element else ELEMENT_TYPES[0]),
            "normal_attack": {
                "name": normal_attack_name,
                "damage": normal_attack_damage,
                "cooldown": normal_attack_cooldown,
            },
            "secondary_attack": {
                "name": secondary_attack_name,
                "damage": secondary_attack_damage,
                "cooldown": secondary_attack_cooldown,
            },
            "power_attack": {
                "name": power_attack_name,
                "damage": power_attack_damage,
                "cooldown": power_attack_cooldown,
            },
        })
        pool[rarity_key]["characters"].append(char_payload)
        save_pool(pool)

        async with database.session() as session:
            result = await session.execute(
                select(GachaCharacterAsset).where(GachaCharacterAsset.character_name.ilike(character_name))
            )
            asset = result.scalar_one_or_none()
            if asset is None:
                asset = GachaCharacterAsset(character_name=character_name)
                session.add(asset)

            asset.image_url = image_url
            if image_blob is not None:
                asset.image_blob = image_blob
                asset.image_mime = image_mime

            await session.commit()

        stars = "⭐" * rarity.value
        embed = discord.Embed(title="✅ Character Added", color=discord.Color.green())
        embed.add_field(name="Name",   value=character_name, inline=True)
        embed.add_field(name="Rarity", value=stars,          inline=True)
        embed.add_field(name="Element", value=char_payload["element"].title(), inline=True)
        embed.add_field(name="Health", value=str(char_payload["health"]), inline=True)
        embed.add_field(
            name="Normal",
            value=(
                f"{char_payload['normal_attack']['name']}\n"
                f"DMG {char_payload['normal_attack']['damage']} | CD {char_payload['normal_attack']['cooldown']}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Secondary",
            value=(
                f"{char_payload['secondary_attack']['name']}\n"
                f"DMG {char_payload['secondary_attack']['damage']} | CD {char_payload['secondary_attack']['cooldown']}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Power",
            value=(
                f"{char_payload['power_attack']['name']}\n"
                f"DMG {char_payload['power_attack']['damage']} | CD {char_payload['power_attack']['cooldown']}"
            ),
            inline=False,
        )
        if image_url:
            embed.set_image(url=image_url)

        await interaction.response.send_message(embed=embed)
