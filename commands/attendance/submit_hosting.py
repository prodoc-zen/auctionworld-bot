from datetime import datetime, timezone
from uuid import uuid4

import discord
from discord import app_commands
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database.models import AdminUser, AttendanceRecord, Transaction, User, format_earnings, utc_now

name        = "submithosting"
description = "Submit a hosting session log"

HOSTING_SESSIONS_CHANNEL_ID = 1447015434959327292
JENNIES_PER_MINUTE          = 8


def parse_time(time_str: str) -> datetime | None:
    time_str = time_str.strip()
    formats  = ["%H:%M", "%I:%M %p", "%I:%M%p", "%H:%M:%S", "%I:%M:%S %p"]
    for fmt in formats:
        try:
            parsed = datetime.strptime(time_str, fmt)
            now    = datetime.now(timezone.utc)
            return now.replace(hour=parsed.hour, minute=parsed.minute, second=parsed.second, microsecond=0)
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
        bgls="BGLs earned (leave blank if none)",
        dls="DLs earned (leave blank if none)",
        wls="WLs earned (leave blank if none)",
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
        screenshot1: discord.Attachment,
        screenshot2: discord.Attachment,
        screenshot3: discord.Attachment,
        bgls:        int = 0,
        dls:         int = 0,
        wls:         int = 0,
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
                f"These files are not images: {', '.join(non_images)}.", ephemeral=True,
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
            await interaction.response.send_message("Time-out must be after time-in.", ephemeral=True)
            return

        total_seconds  = (time_out_dt - time_in_dt).total_seconds()
        total_minutes  = int(total_seconds // 60)
        jennies_earned = total_minutes * JENNIES_PER_MINUTE
        duration_text  = format_duration(total_seconds)
        earnings_text  = format_earnings(bgls, dls, wls)

        async with database.session() as session:
            # Ensure user exists
            if await session.get(User, discord_id) is None:
                session.add(User(discord_id=discord_id, jennies=2000))
                await session.flush()

            # Ensure admin_user exists for weeklyhours tracking
            if await session.get(AdminUser, discord_id) is None:
                session.add(AdminUser(discord_id=discord_id, is_active=True))
                await session.flush()

            # Add jennies
            user = await session.get(User, discord_id)
            user.jennies += jennies_earned

            # Unique reason using UUID to prevent duplicate key errors
            reason = f"hosting:{int(time_in_dt.timestamp())}:{discord_id}:{uuid4().hex[:8]}"
            session.add(Transaction(discord_id=discord_id, amount=jennies_earned, reason=reason))

            # Save attendance record
            record = AttendanceRecord(
                discord_id=discord_id,
                time_in_at=time_in_dt,
                time_out_at=time_out_dt,
                bgls=bgls,
                dls=dls,
                wls=wls,
            )
            session.add(record)
            await session.flush()
            hosting_id = record.id

            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                await interaction.response.send_message(
                    "Submission failed due to a duplicate entry. Please try again.",
                    ephemeral=True,
                )
                return

        # Build main embed
        embed = discord.Embed(title="Hosting Session", color=discord.Color.green())
        embed.add_field(name="Hosting ID",    value=str(hosting_id),                          inline=True)
        embed.add_field(name="Discord",       value=target.mention,                            inline=True)
        embed.add_field(name="Date",          value=time_in_dt.strftime("%d %b %Y %H:%M UTC"), inline=True)
        embed.add_field(name="Earnings",      value=earnings_text,                             inline=True)
        embed.add_field(name="Time Worked",   value=duration_text,                             inline=True)
        embed.add_field(name="Jennies Earned",value=f"+{jennies_earned} ({total_minutes}m × {JENNIES_PER_MINUTE})", inline=True)

        # Send screenshots as a grid — up to 4 embeds per message (Discord limit)
        channel = interaction.client.get_channel(HOSTING_SESSIONS_CHANNEL_ID)
        if channel is None:
            channel = await interaction.client.fetch_channel(HOSTING_SESSIONS_CHANNEL_ID)

        # First message: main info embed + first screenshot
        embed.set_image(url=all_attachments[0].url)
        screenshot_embeds = [embed]

        # Add remaining screenshots as additional embeds in the same message (up to 4 total)
        for attachment in all_attachments[1:3]:
            e = discord.Embed(color=discord.Color.green())
            e.set_image(url=attachment.url)
            screenshot_embeds.append(e)

        await channel.send(embeds=screenshot_embeds)

        # If more than 3 extra screenshots, send in batches of 4
        remaining = all_attachments[3:]
        for i in range(0, len(remaining), 4):
            batch = remaining[i:i+4]
            batch_embeds = []
            for attachment in batch:
                e = discord.Embed(color=discord.Color.green())
                e.set_image(url=attachment.url)
                batch_embeds.append(e)
            await channel.send(embeds=batch_embeds)

        await interaction.response.send_message(
            f"✅ Submitted! You earned **{jennies_earned} Jennies** for {duration_text} of hosting. Check <#{HOSTING_SESSIONS_CHANNEL_ID}>.",
            ephemeral=True,
        )
