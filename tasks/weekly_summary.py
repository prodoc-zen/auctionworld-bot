"""
Weekly summary task — posts a Week in Review message every Sunday at 00:00 UTC
to the management announcements channel.
"""
import asyncio
from datetime import timedelta

from sqlalchemy import select

from database.models import AdminProfile, AttendanceRecord, to_wls, from_wls, format_earnings, utc_now

SUMMARY_CHANNEL_ID = 1429422003458412594
ADMIN_ROLE_ID      = 1429303490471264400


def week_start(now):
    start = now - timedelta(days=now.weekday())
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def format_duration(total_seconds: float) -> str:
    total_minutes = max(0, int(total_seconds // 60))
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    elif hours:
        return f"{hours}h"
    return f"{minutes}m"


async def send_weekly_summary(client, database):
    now        = utc_now()
    # The week that just ended
    end        = week_start(now)
    start      = end - timedelta(days=7)

    async with database.session() as session:
        # Get all attendance records for the past week
        result = await session.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.time_in_at >= start,
                AttendanceRecord.time_in_at < end,
            )
        )
        records = result.scalars().all()

        # New admins this week
        new_admins_result = await session.execute(
            select(AdminProfile).where(
                AdminProfile.created_at >= start,
                AdminProfile.created_at < end,
            )
        )
        new_admins = new_admins_result.scalars().all()

        # All time records for total earnings
        all_records_result = await session.execute(select(AttendanceRecord))
        all_records = all_records_result.scalars().all()

    # Weekly stats
    weekly_total_wls  = 0
    weekly_total_secs = 0
    earnings_by_user  = {}
    time_by_user      = {}

    for record in records:
        session_end  = record.time_out_at or now
        duration     = max(0, (session_end - record.time_in_at).total_seconds())
        earn_wls     = to_wls(record.bgls, record.dls, record.wls)

        weekly_total_wls  += earn_wls
        weekly_total_secs += duration

        earnings_by_user[record.discord_id] = earnings_by_user.get(record.discord_id, 0) + earn_wls
        time_by_user[record.discord_id]     = time_by_user.get(record.discord_id, 0) + duration

    # All time total earnings
    all_time_wls = sum(
        to_wls(r.bgls, r.dls, r.wls) for r in all_records
    )

    # All time total time worked
    all_time_secs = sum(
        max(0, ((r.time_out_at or now) - r.time_in_at).total_seconds())
        for r in all_records
    )

    # Top earner and top time worker this week
    top_earner   = max(earnings_by_user, key=earnings_by_user.get) if earnings_by_user else None
    top_timer    = max(time_by_user,     key=time_by_user.get)     if time_by_user     else None

    weekly_earn_text   = format_earnings(*from_wls(weekly_total_wls))
    alltime_earn_text  = format_earnings(*from_wls(all_time_wls))
    week_label         = f"{start.strftime('%b %d')} – {(end - timedelta(days=1)).strftime('%b %d')}"

    lines = [
        f"<@&{ADMIN_ROLE_ID}> **Week in Review**\n",
        f"📅 The week **{week_label}** has ended!\n",
    ]

    if top_earner and top_timer:
        top_earn_fmt = format_earnings(*from_wls(earnings_by_user[top_earner]))
        top_time_fmt = format_duration(time_by_user[top_timer])
        lines.append(
            f"🥇 Congratulations to <@{top_earner}> for topping the Earnings Leaderboard "
            f"with **{top_earn_fmt}** and <@{top_timer}> for topping the Time Worked Leaderboard "
            f"with **{top_time_fmt}**!\n"
        )

    lines.append(
        f"💸 Our admins collectively made **{weekly_earn_text}** last week, "
        f"bringing the total earnings to **{alltime_earn_text}**!\n"
    )
    lines.append(
        f"⏰ Our admins collectively worked **{format_duration(weekly_total_secs)}** last week, "
        f"bringing the total time worked to **{format_duration(all_time_secs)}**!\n"
    )

    if new_admins:
        lines.append(
            f"💪 We had **{len(new_admins)}** new admin{'s' if len(new_admins) > 1 else ''} "
            f"join us last week. We hope you enjoy your time here!\n"
        )

    lines.append("🙏 Thanks for being amazing **AUCTIONWORLD** admins! Keep up the good work!")

    channel = client.get_channel(SUMMARY_CHANNEL_ID)
    if channel is None:
        channel = await client.fetch_channel(SUMMARY_CHANNEL_ID)

    if not records:
        client.logger.info("No hosting data this week, skipping weekly summary.")
        return

    await channel.send("\n".join(lines))


async def start_weekly_summary_task(client, database):
    """Wait until next Sunday 00:00 UTC then post every 7 days."""
    await client.wait_until_ready()

    while not client.is_closed():
        now   = utc_now()
        # Days until next Monday (start of new week) = days until next weekday 0
        days_until_sunday = (6 - now.weekday()) % 7
        next_sunday = week_start(now + timedelta(days=days_until_sunday + 7))
        wait_seconds = (next_sunday - now).total_seconds()

        client.logger.info("Weekly summary scheduled in %.0f seconds.", wait_seconds)
        await asyncio.sleep(wait_seconds)

        try:
            await send_weekly_summary(client, database)
        except Exception as e:
            client.logger.error("Failed to send weekly summary: %s", e)

        # Wait a minute before looping to avoid double-posting
        await asyncio.sleep(60)
