import discord
from discord import app_commands
from sqlalchemy import select

from commands.gacha._gacha_utils import load_pool, save_pool
from database.models import GachaCharacterAsset

name        = "set-character-image"
description = "Set or update a character's image (Developer only)"

DEVELOPER_ROLE_ID = 1457710235069186349


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        character_name="Name of the character",
        image_url="New image URL (leave blank to remove image)",
        image_file="Upload image file (optional)",
    )
    async def set_character_image(
        interaction,
        character_name: str,
        image_url: str = None,
        image_file: discord.Attachment = None,
    ):
        if DEVELOPER_ROLE_ID not in {role.id for role in interaction.user.roles}:
            await interaction.response.send_message("Only Developers can use this.", ephemeral=True)
            return

        pool    = load_pool()
        updated = False

        image_blob = None
        image_mime = None
        if image_file is not None:
            if image_file.content_type is None or not image_file.content_type.startswith("image/"):
                await interaction.response.send_message("Uploaded file must be an image.", ephemeral=True)
                return
            image_blob = await image_file.read()
            image_mime = image_file.content_type
            image_url = image_url or image_file.url

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

        embed = discord.Embed(title="✅ Character Image Updated", color=discord.Color.blurple())
        embed.add_field(name="Character", value=character_name, inline=False)
        embed.add_field(name="Image",     value=image_url or "Removed", inline=False)
        if image_url:
            embed.set_image(url=image_url)

        await interaction.response.send_message(embed=embed)
