import discord
from sqlalchemy import select
from database.models import GachaCard, GachaPity, User
from commands.gacha._gacha_utils import pull_character, PULL_COST, STAR_EMOJIS, RARITY_COLORS, MAX_LEVEL, PITY_4STAR

name        = "gacha-single"
description = "Pull 1 gacha character (120 Jennies)"


def register(tree, database):
    @tree.command(name=name, description=description)
    async def gacha_single(interaction):
        discord_id = interaction.user.id

        async with database.session() as session:
            result = await session.execute(select(User).where(User.discord_id == discord_id))
            user   = result.scalar_one_or_none()
            if user is None:
                user = User(discord_id=discord_id, jennies=2000)
                session.add(user)
                await session.flush()

            if user.jennies < PULL_COST:
                await interaction.response.send_message(
                    f"You need **{PULL_COST} Jennies** to pull. You have **{user.jennies}**.",
                    ephemeral=True,
                )
                return

            pity = await session.get(GachaPity, discord_id)
            if pity is None:
                pity = GachaPity(discord_id=discord_id)
                session.add(pity)
                await session.flush()

            character, rarity, image = pull_character(pity.pulls_since_4star, pity.pulls_since_3star)
            user.jennies -= PULL_COST

            if rarity == 4:
                pity.pulls_since_4star = 0
                pity.pulls_since_3star = 0
            elif rarity >= 3:
                pity.pulls_since_3star = 0
                pity.pulls_since_4star += 1
            else:
                pity.pulls_since_4star += 1
                pity.pulls_since_3star += 1

            dup_result = await session.execute(
                select(GachaCard).where(
                    GachaCard.discord_id == discord_id,
                    GachaCard.character_name == character,
                )
            )
            existing = dup_result.scalar_one_or_none()

            if existing is not None and existing.level < MAX_LEVEL:
                existing.level += 1
                level  = existing.level
                is_new = False
            elif existing is None:
                card = GachaCard(discord_id=discord_id, character_name=character, rarity=rarity)
                session.add(card)
                level  = 1
                is_new = True
            else:
                level  = existing.level
                is_new = False

            pity_text = f"{pity.pulls_since_4star}/{PITY_4STAR} to guaranteed ⭐⭐⭐⭐"
            await session.commit()

        stars  = STAR_EMOJIS[rarity]
        color  = RARITY_COLORS[rarity]
        status = "🆕 **New!**" if is_new else f"✨ **Duplicate!** Level → **{level}**"

        embed = discord.Embed(title="🎴 Gacha Pull!", color=color)
        embed.add_field(name="Character", value=f"**{character}**", inline=True)
        embed.add_field(name="Rarity",    value=stars,              inline=True)
        embed.add_field(name="Status",    value=status,             inline=False)
        if image:
            embed.set_image(url=image)
        embed.set_footer(text=f"Cost: {PULL_COST} Jennies | Balance: {user.jennies} Jennies | Pity: {pity_text}")

        await interaction.response.send_message(embed=embed)
