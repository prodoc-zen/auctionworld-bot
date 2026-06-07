from datetime import datetime, timezone

import discord
from discord import app_commands

from database.models import AdminUser, AttendanceRecord, User, utc_now

name        = "submithosting"
description = "Submit a hosting session log"

HOSTING_SESSIONS_CHANNEL_ID = 1447015434959327292


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


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(
        time_in="Time you started hosting (e.g. 14:00 or 2:00 PM)",
        time_out="Time you finished hosting (e.g. 15:30 or 3:30 PM)",
        earnings="What you earned (e.g. 1 BGLs 27 WLs)",
        member="Who hosted (leave blank to submit for yourself)",
    )
    async def submithosting(
        interaction,
        time_in:  str,
        time_out: str,
        earnings: str,
        member:   discord.Member = None,
    ):
        target     = member or interaction.user
        discord_id = target.id

        # Parse times
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
                "Time-out must be after time-in.",
                ephemeral=True,
            )
            return

        duration_text = format_duration((time_out_dt - time_in_dt).total_seconds())

        async with database.session() as session:
            # Ensure user row exists
            if await session.get(User, discord_id) is None:
                session.add(User(discord_id=discord_id, jennies=0))
                await session.flush()

            # Auto-register as admin if not already
            if await session.get(AdminUser, discord_id) is None:
                session.add(AdminUser(discord_id=discord_id, is_active=True))
                await session.flush()

            # Save attendance record and flush to get the auto-incremented ID
            record = AttendanceRecord(
                discord_id=discord_id,
                time_in_at=time_in_dt,
                time_out_at=time_out_dt,
            )
            session.add(record)
            await session.flush()
            hosting_id = record.id
            await session.commit()

        # Build the embed
        embed = discord.Embed(
            title="Hosting Session",
            color=discord.Color.green(),
        )
        embed.add_field(name="Hosting ID", value=str(hosting_id),         inline=False)
        embed.add_field(name="Discord",    value=target.mention,           inline=False)
        embed.add_field(name="Earnings",   value=earnings,                 inline=False)
        embed.add_field(name="Time Worked",value=duration_text,            inline=False)
        embed.add_field(
            name="Date",
            value=time_in_dt.strftime("%d %b %Y %H:%M") + " UTC",
            inline=False,
        )

        # Post to #hosting-sessions channel
        channel = interaction.client.get_channel(HOSTING_SESSIONS_CHANNEL_ID)
        if channel is None:
            channel = await interaction.client.fetch_channel(HOSTING_SESSIONS_CHANNEL_ID)

        await channel.send(embed=embed)

        # Confirm to the user
        await interaction.response.send_message(
            f"✅ Hosting session submitted! Check <#{HOSTING_SESSIONS_CHANNEL_ID}>.",
            ephemeral=True,
        )
