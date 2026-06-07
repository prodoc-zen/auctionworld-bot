from datetime import datetime, timezone

import discord
from discord import app_commands

from database.models import AdminUser, AttendanceRecord, User, utc_now

name        = "submithosting"
description = "Submit a hosting session log"

HOSTING_SESSIONS_CHANNEL_ID = 1447015434959327292
MIN_ATTACHMENTS = 3
MAX_ATTACHMENTS = 10


def parse_time(time_str: str) -> datetime | None:
    time_str = time_str.strip()
    formats  = ["%H:%M", "%I:%M %p", "%I:%M%p", "%H:%M:%S", "%I:%M:%S %p"]
    for fmt in formats:
        try:
            parsed = datetime.strptime(time_str, fmt)
            now    = datetime.now(timezone.utc)
            return now.replace(
                hour=parsed.hour,
                minute=parsed.minute,
                second=parsed.second,
                microsecond=0,
            )
        except ValueError:
            continue
    return None


def format_duration(total_seconds: float) -> str:
    total_minutes = max(0, int(total_seconds // 60))
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    elif hours:
        return f"{hours}h"
    return f"{minutes}m"


def is_image(attachment: discord.Attachment) -> bool:
    return attachment.content_type is not None and attachment.content_type.startswith("image/")


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        time_in="Time you started hosting (e.g. 14:00 or 2:00 PM)",
        time_out="Time you finished hosting (e.g. 15:30 or 3:30 PM)",
        earnings="What you earned (e.g. 1 BGLs 27 WLs)",
        screenshot1="Screenshot 1 (required)",
        screenshot2="Screenshot 2 (required)",
        screenshot3="Screenshot 3 (required)",
        screenshot4="Screenshot 4",
        screenshot5="Screenshot 5",
        screenshot6="Screenshot 6",
        screenshot7="Screenshot 7",
        screenshot8="Screenshot 8",
        screenshot9="Screenshot 9",
        screenshot10="Screenshot 10",
        member="Who hosted (leave blank to submit for yourself)",
    )
    async def submithosting(
        interaction,
        time_in:     str,
        time_out:    str,
        earnings:    str,
        screenshot1: discord.Attachment,
        screenshot2: discord.Attachment,
        screenshot3: discord.Attachment,
        screenshot4: discord.Attachment = None,
        screenshot5: discord.Attachment = None,
        screenshot6: discord.Attachment = None,
        screenshot7: discord.Attachment = None,
        screenshot8: discord.Attachment = None,
        screenshot9: discord.Attachment = None,
        screenshot10:discord.Attachment = None,
        member:      discord.Member     = None,
    ):
        target     = member or interaction.user
        discord_id = target.id

        all_attachments = [
            a for a in [
                screenshot1, screenshot2, screenshot3, screenshot4,
                screenshot5, screenshot6, screenshot7, screenshot8,
                screenshot9, screenshot10,
            ] if a is not None
        ]

        non_images = [a.filename for a in all_attachments if not is_image(a)]
        if non_images:
            await interaction.response.send_message(
                f"These files are not images: {', '.join(non_images)}.",
                ephemeral=True,
            )
            return

        time_in_dt  = parse_time(time_in)
        time_out_dt = parse_time(time_out)

        if time_in_dt is None:
            await interaction.response.send_message(
                f"Could not parse time-in `{time_in}`. Use formats like `14:00` or `2:00 PM`.",
                ephemeral=True,
            )
            return

        if time_out_dt is None:
            await interaction.response.send_message(
                f"Could not parse time-out `{time_out}`. Use formats like `15:30` or `3:30 PM`.",
                ephemeral=True,
            )
            return

        if time_out_dt <= time_in_dt:
            await interaction.response.send_message(
                "Time-out must be after time-in.", ephemeral=True,
            )
            return

        duration_text = format_duration((time_out_dt - time_in_dt).total_seconds())

        async with database.session() as session:
            if await session.get(User, discord_id) is None:
                session.add(User(discord_id=discord_id, jennies=0))
                await session.flush()

            if await session.get(AdminUser, discord_id) is None:
                session.add(AdminUser(discord_id=discord_id, is_active=True))
                await session.flush()

            record = AttendanceRecord(
                discord_id=discord_id,
                time_in_at=time_in_dt,
                time_out_at=time_out_dt,
                earnings=earnings,
            )
            session.add(record)
            await session.flush()
            hosting_id = record.id
            await session.commit()

        embed = discord.Embed(title="Hosting Session", color=discord.Color.green())
        embed.add_field(name="Hosting ID",  value=str(hosting_id),                          inline=False)
        embed.add_field(name="Discord",     value=target.mention,                            inline=False)
        embed.add_field(name="Earnings",    value=earnings,                                  inline=False)
        embed.add_field(name="Time Worked", value=duration_text,                             inline=False)
        embed.add_field(name="Date",        value=time_in_dt.strftime("%d %b %Y %H:%M UTC"), inline=False)
        embed.set_image(url=all_attachments[0].url)

        channel = interaction.client.get_channel(HOSTING_SESSIONS_CHANNEL_ID)
        if channel is None:
            channel = await interaction.client.fetch_channel(HOSTING_SESSIONS_CHANNEL_ID)

        await channel.send(embed=embed)

        if len(all_attachments) > 1:
            extra_embeds = []
            for attachment in all_attachments[1:]:
                extra_embed = discord.Embed(color=discord.Color.green())
                extra_embed.set_image(url=attachment.url)
                extra_embeds.append(extra_embed)
            await channel.send(embeds=extra_embeds)

        await interaction.response.send_message(
            f"✅ Hosting session submitted! Check <#{HOSTING_SESSIONS_CHANNEL_ID}>.",
            ephemeral=True,
        )
