"""
Shared helpers for the hosting queue commands.
Import from here — never duplicate this logic across command files.
"""
import asyncio
from datetime import timedelta

import discord
from sqlalchemy import select

from database.models import HostingQueueEntry, utc_now

QUEUES = ("Left", "Mid", "Right")

WAITING = "waiting"
ACTIVE  = "active"
DONE    = "done"
SKIPPED = "skipped"

# In-memory task registries (live for the process lifetime)
_session_tasks: dict = {}
_grace_tasks:   dict = {}

QUEUE_EMOJIS = {
    "Left": "🔵",
    "Mid": "🟣",
    "Right": "🟢",
}


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def get_active(session, queue_name: str):
    result = await session.execute(
        select(HostingQueueEntry)
        .where(
            HostingQueueEntry.queue_name == queue_name,
            HostingQueueEntry.status == ACTIVE,
        )
        .order_by(HostingQueueEntry.started_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_next_waiting(session, queue_name: str):
    result = await session.execute(
        select(HostingQueueEntry)
        .where(
            HostingQueueEntry.queue_name == queue_name,
            HostingQueueEntry.status == WAITING,
        )
        .order_by(HostingQueueEntry.joined_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_waiting(session, queue_name: str):
    result = await session.execute(
        select(HostingQueueEntry)
        .where(
            HostingQueueEntry.queue_name == queue_name,
            HostingQueueEntry.status == WAITING,
        )
        .order_by(HostingQueueEntry.joined_at.asc())
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Startup recovery — call this in bot.py on_ready
# ---------------------------------------------------------------------------

async def recover_active_sessions(client, database):
    """
    On bot restart, find any sessions that were ACTIVE or had a pending
    grace timer and reschedule their end/skip tasks based on expires_at.
    This prevents sessions from getting permanently stuck after a crash.
    """
    now = utc_now()

    async with database.session() as session:
        # Recover active sessions
        result = await session.execute(
            select(HostingQueueEntry).where(
                HostingQueueEntry.status == ACTIVE,
            )
        )
        active_entries = result.scalars().all()

        for entry in active_entries:
            if entry.expires_at is None:
                continue

            remaining_seconds = (entry.expires_at - now).total_seconds()
            announce_channel_id = resolve_announce_channel_id(client, entry.channel_id)
            if announce_channel_id is None:
                continue

            if remaining_seconds <= 0:
                # Already expired — mark as done immediately
                entry.status       = DONE
                entry.completed_at = now
            else:
                # Reschedule the session end timer for remaining time
                remaining_minutes = remaining_seconds / 60
                schedule_session_end(
                    client, database,
                    entry.queue_name, entry.id,
                    announce_channel_id, remaining_minutes,
                )

        await session.commit()

    if active_entries:
        recovered = len(active_entries)
        client.logger.info("Recovered %d active hosting session(s) after restart.", recovered)


# ---------------------------------------------------------------------------
# Embed builder
# ---------------------------------------------------------------------------

async def build_queue_embed(database) -> discord.Embed:
    embed = discord.Embed(
        title="🚦 Hosting Queue",
        description="Join a lane, then press **Start** when it's your turn. Timers are shown in `MM:SS`.",
        color=discord.Color.green(),
    )

    async with database.session() as session:
        now = utc_now()
        lines = [
            "╔════════════════════════════════════════╗",
            "║             HOSTING STATUS            ║",
            "╚════════════════════════════════════════╝",
            "",
        ]

        for queue_name in QUEUES:
            active  = await get_active(session, queue_name)
            waiting = await get_waiting(session, queue_name)
            emoji = QUEUE_EMOJIS.get(queue_name, "🔹")

            if active:
                host_text = f"<@{active.discord_id}>"
                left_text = remaining_clock(now, active.expires_at)
            else:
                host_text = "Available"
                left_text = "--:--"

            lines.append(f"{emoji} {queue_name.upper()} HOST")
            lines.append(f"└─ {host_text}")
            lines.append(f"⏳ Time Left: {left_text}")
            lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")

        for queue_name in QUEUES:
            waiting = await get_waiting(session, queue_name)
            lines.append(f"📋 {queue_name.upper()} QUEUE ({len(waiting)})")
            if waiting:
                for i, e in enumerate(waiting[:8], start=1):
                    lines.append(f"{i}. <@{e.discord_id}>")
                if len(waiting) > 8:
                    lines.append(f"...and {len(waiting) - 8} more")
            else:
                lines.append("(empty)")
            lines.append("")

        embed.description = "\n".join(lines)

    embed.set_footer(text="Use Join/Start/Leave below. Press Refresh if this panel is stale.")

    return embed


async def refresh_panel(interaction, database):
    embed = await build_queue_embed(database)
    view  = HostingQueueView(database)
    await interaction.message.edit(embed=embed, view=view)


# ---------------------------------------------------------------------------
# Timer helpers
# ---------------------------------------------------------------------------

def format_minutes(minutes: int) -> str:
    return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"


def remaining_clock(now, expires_at) -> str:
    if expires_at is None:
        return "--:--"
    remaining = max(0, int((expires_at - now).total_seconds()))
    mm, ss = divmod(remaining, 60)
    return f"{mm:02d}:{ss:02d}"


def resolve_announce_channel_id(client, fallback_channel_id: int | None = None) -> int | None:
    configured = client.config.get("hosting_announce_channel_id")
    if configured:
        return int(configured)
    return fallback_channel_id


def resolve_timeup_channel_id(client, fallback_channel_id: int | None = None) -> int | None:
    configured = client.config.get("hosting_timeup_channel_id")
    if configured:
        return int(configured)
    return resolve_announce_channel_id(client, fallback_channel_id)


def cancel_task(tasks: dict, key):
    task = tasks.pop(key, None)
    if task and not task.done():
        task.cancel()


async def send_channel_message(client, channel_id: int, message: str):
    if channel_id is None:
        return
    channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
    await channel.send(message)


def schedule_session_end(client, database, queue_name, entry_id, channel_id, minutes):
    cancel_task(_session_tasks, (queue_name, entry_id))
    _session_tasks[(queue_name, entry_id)] = asyncio.create_task(
        _finish_session_after_delay(client, database, queue_name, entry_id, channel_id, minutes)
    )


def schedule_start_grace(client, database, queue_name, entry_id, channel_id, minutes):
    cancel_task(_grace_tasks, (queue_name, entry_id))
    _grace_tasks[(queue_name, entry_id)] = asyncio.create_task(
        _skip_after_grace(client, database, queue_name, entry_id, channel_id, minutes)
    )


async def _finish_session_after_delay(client, database, queue_name, entry_id, channel_id, minutes):
    await asyncio.sleep(minutes * 60)

    next_entry = None
    finished_discord_id = None
    async with database.session() as session:
        entry = await session.get(HostingQueueEntry, entry_id)
        if entry is None or entry.status != ACTIVE:
            return

        entry.status       = DONE
        entry.completed_at = utc_now()
        finished_discord_id = entry.discord_id
        await session.commit()

        next_entry = await get_next_waiting(session, queue_name)
        if next_entry is not None:
            next_entry.channel_id = channel_id
            await session.commit()

    timeup_channel_id = resolve_timeup_channel_id(client, channel_id)
    await send_channel_message(
        client, timeup_channel_id,
        f"<@{finished_discord_id}>, your {queue_name} hosting session is done.",
    )

    if next_entry is not None:
        grace = int(client.config.get("hosting_start_grace_minutes", 5))
        schedule_start_grace(client, database, queue_name, next_entry.id, channel_id, grace)
        await send_channel_message(
            client, channel_id,
            f"<@{next_entry.discord_id}>, it is your turn for {queue_name}. "
            f"Press **Start {queue_name}** within {format_minutes(grace)}.",
        )


async def _skip_after_grace(client, database, queue_name, entry_id, channel_id, minutes):
    await asyncio.sleep(minutes * 60)

    async with database.session() as session:
        if await get_active(session, queue_name) is not None:
            return

        entry = await session.get(HostingQueueEntry, entry_id)
        if entry is None or entry.status != WAITING:
            return

        entry.status       = SKIPPED
        entry.completed_at = utc_now()
        await session.commit()

        next_entry = await get_next_waiting(session, queue_name)
        if next_entry is not None:
            next_entry.channel_id = channel_id
            await session.commit()

    await send_channel_message(
        client, channel_id,
        f"<@{entry.discord_id}> did not start {queue_name} in time and was removed from the queue.",
    )

    if next_entry is not None:
        schedule_start_grace(client, database, queue_name, next_entry.id, channel_id, minutes)
        await send_channel_message(
            client, channel_id,
            f"<@{next_entry.discord_id}>, it is your turn for {queue_name}. "
            f"Press **Start {queue_name}** within {format_minutes(minutes)}.",
        )


# ---------------------------------------------------------------------------
# Shared UI View
# ---------------------------------------------------------------------------

class JoinQueueButton(discord.ui.Button):
    def __init__(self, queue_name, row):
        super().__init__(
            label=f"Join {queue_name}",
            emoji="➕",
            style=discord.ButtonStyle.primary,
            row=row,
        )
        self.queue_name = queue_name

    async def callback(self, interaction):
        discord_id          = interaction.user.id
        now                 = utc_now()
        should_prompt_start = False
        next_entry_id       = None
        announce_channel_id = resolve_announce_channel_id(interaction.client, interaction.channel_id)

        async with self.view.database.session() as session:
            result = await session.execute(
                select(HostingQueueEntry).where(
                    HostingQueueEntry.queue_name == self.queue_name,
                    HostingQueueEntry.discord_id == discord_id,
                    HostingQueueEntry.status.in_([WAITING, ACTIVE]),
                )
            )
            if result.scalar_one_or_none() is not None:
                await interaction.response.send_message(
                    f"{interaction.user.mention}, you are already in {self.queue_name}.",
                    ephemeral=True,
                )
                return

            entry = HostingQueueEntry(
                queue_name=self.queue_name,
                discord_id=discord_id,
                channel_id=announce_channel_id,
                joined_at=now,
            )
            session.add(entry)
            await session.flush()

            active        = await get_active(session, self.queue_name)
            first_waiting = await get_next_waiting(session, self.queue_name)
            should_prompt_start = (
                active is None and first_waiting and first_waiting.id == entry.id
            )
            next_entry_id = entry.id
            await session.commit()

        await interaction.response.send_message(
            f"{interaction.user.mention}, you joined the {self.queue_name} hosting queue.",
            ephemeral=True,
        )
        await refresh_panel(interaction, self.view.database)

        if should_prompt_start:
            grace = int(interaction.client.config.get("hosting_start_grace_minutes", 5))
            schedule_start_grace(
                interaction.client, self.view.database,
                self.queue_name, next_entry_id,
                announce_channel_id, grace,
            )
            await send_channel_message(
                interaction.client,
                announce_channel_id,
                f"{interaction.user.mention}, {self.queue_name} is ready. "
                f"Press **Start {self.queue_name}** within {format_minutes(grace)}."
            )


class StartQueueButton(discord.ui.Button):
    def __init__(self, queue_name, row):
        super().__init__(
            label=f"Start {queue_name}",
            emoji="▶️",
            style=discord.ButtonStyle.success,
            row=row,
        )
        self.queue_name = queue_name

    async def callback(self, interaction):
        discord_id      = interaction.user.id
        now             = utc_now()
        session_minutes = int(interaction.client.config.get("hosting_session_minutes", 60))
        announce_channel_id = resolve_announce_channel_id(interaction.client, interaction.channel_id)

        async with self.view.database.session() as session:
            active = await get_active(session, self.queue_name)
            if active is not None:
                await interaction.response.send_message(
                    f"{self.queue_name} is already being hosted by <@{active.discord_id}>.",
                    ephemeral=True,
                )
                return

            next_entry = await get_next_waiting(session, self.queue_name)
            if next_entry is None:
                await interaction.response.send_message(
                    f"The {self.queue_name} queue is empty.", ephemeral=True,
                )
                return

            if next_entry.discord_id != discord_id:
                await interaction.response.send_message(
                    f"It is <@{next_entry.discord_id}>'s turn for {self.queue_name}.",
                    ephemeral=True,
                )
                return

            next_entry.status     = ACTIVE
            next_entry.started_at = now
            next_entry.expires_at = now + timedelta(minutes=session_minutes)
            next_entry.channel_id = announce_channel_id
            await session.commit()
            entry_id = next_entry.id

        cancel_task(_grace_tasks, (self.queue_name, entry_id))
        schedule_session_end(
            interaction.client, self.view.database,
            self.queue_name, entry_id,
            announce_channel_id, session_minutes,
        )

        await interaction.response.send_message(
            f"{interaction.user.mention} started {self.queue_name} hosting. "
            f"Session length: {format_minutes(session_minutes)}.",
            ephemeral=True,
        )
        await send_channel_message(
            interaction.client,
            announce_channel_id,
            f"{interaction.user.mention} started {self.queue_name} hosting. "
            f"Time left: {session_minutes:02d}:00",
        )
        await refresh_panel(interaction, self.view.database)


class LeaveHostingButton(discord.ui.Button):
    def __init__(self, row):
        super().__init__(label="Leave Hosting", emoji="⏹️", style=discord.ButtonStyle.danger, row=row)

    async def callback(self, interaction):
        discord_id = interaction.user.id
        now = utc_now()
        ended = []

        async with self.view.database.session() as session:
            result = await session.execute(
                select(HostingQueueEntry).where(
                    HostingQueueEntry.discord_id == discord_id,
                    HostingQueueEntry.status == ACTIVE,
                )
            )
            active_entries = result.scalars().all()

            if not active_entries:
                await interaction.response.send_message("You are not currently hosting.", ephemeral=True)
                return

            for entry in active_entries:
                entry.status = DONE
                entry.completed_at = now
                ended.append((entry.queue_name, entry.id, resolve_announce_channel_id(interaction.client, entry.channel_id)))

            await session.commit()

        for queue_name, entry_id, announce_channel_id in ended:
            cancel_task(_session_tasks, (queue_name, entry_id))

            next_entry = None
            async with self.view.database.session() as session:
                next_entry = await get_next_waiting(session, queue_name)
                if next_entry is not None:
                    next_entry.channel_id = announce_channel_id
                    await session.commit()

            await send_channel_message(
                interaction.client,
                announce_channel_id,
                f"<@{discord_id}> ended {queue_name} hosting early.",
            )

            if next_entry is not None:
                grace = int(interaction.client.config.get("hosting_start_grace_minutes", 5))
                schedule_start_grace(interaction.client, self.view.database, queue_name, next_entry.id, announce_channel_id, grace)
                await send_channel_message(
                    interaction.client,
                    announce_channel_id,
                    f"<@{next_entry.discord_id}>, it is your turn for {queue_name}. "
                    f"Press **Start {queue_name}** within {format_minutes(grace)}.",
                )

        await interaction.response.send_message("Stopped your active hosting session(s).", ephemeral=True)
        await refresh_panel(interaction, self.view.database)


class LeaveQueueButton(discord.ui.Button):
    def __init__(self, row):
        super().__init__(label="Leave Queue", emoji="➖", style=discord.ButtonStyle.danger, row=row)

    async def callback(self, interaction):
        discord_id = interaction.user.id
        removed    = 0

        async with self.view.database.session() as session:
            result = await session.execute(
                select(HostingQueueEntry).where(
                    HostingQueueEntry.discord_id == discord_id,
                    HostingQueueEntry.status == WAITING,
                )
            )
            for entry in result.scalars().all():
                entry.status       = SKIPPED
                entry.completed_at = utc_now()
                removed += 1

            await session.commit()

        await interaction.response.send_message(
            f"{interaction.user.mention}, removed you from {removed} waiting queue(s).",
            ephemeral=True,
        )
        await refresh_panel(interaction, self.view.database)


class RefreshQueueButton(discord.ui.Button):
    def __init__(self, row):
        super().__init__(label="Refresh", emoji="🔄", style=discord.ButtonStyle.secondary, row=row)

    async def callback(self, interaction):
        await interaction.response.defer(ephemeral=True)
        await refresh_panel(interaction, self.view.database)
        await interaction.followup.send("Queue panel refreshed.", ephemeral=True)


class HostingQueueView(discord.ui.View):
    def __init__(self, database):
        super().__init__(timeout=None)
        self.database = database

        for index, queue_name in enumerate(QUEUES):
            self.add_item(JoinQueueButton(queue_name,  row=index))
            self.add_item(StartQueueButton(queue_name, row=index))

        self.add_item(LeaveQueueButton(row=3))
        self.add_item(LeaveHostingButton(row=3))
        self.add_item(RefreshQueueButton(row=4))
