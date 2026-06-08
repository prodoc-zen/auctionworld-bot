import asyncio
import json
import os
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

from commands.hosting._queue_utils import recover_active_sessions
from database.db import Database
from handlers.command_loader import load_commands
from tasks.weekly_summary import start_weekly_summary_task
from utils.logger import get_logger


BASE_DIR    = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"

logger = get_logger("bot")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config():
    load_dotenv()

    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    config["token"] = os.getenv("DISCORD_TOKEN", config.get("token", ""))
    database = config.setdefault("database", {})
    database["host"]      = os.getenv("DB_HOST",     database.get("host",     "localhost"))
    database["user"]      = os.getenv("DB_USER",     database.get("user",     "root"))
    database["password"]  = os.getenv("DB_PASSWORD", database.get("password", ""))
    database["name"]      = os.getenv("DB_NAME",     database.get("name",     "auctionworld"))
    database["port"]      = int(os.getenv("DB_PORT", database.get("port",     3306)))
    database["echo"]      = env_bool("DB_ECHO",      database.get("echo",     False))
    config["guild_id"]                    = os.getenv("GUILD_ID", config.get("guild_id"))
    config["weekly_quota_hours"]          = int(os.getenv("WEEKLY_QUOTA_HOURS",          "10"))
    config["hosting_session_minutes"]     = int(os.getenv("HOSTING_SESSION_MINUTES",     "60"))
    config["hosting_start_grace_minutes"] = int(os.getenv("HOSTING_START_GRACE_MINUTES",  "5"))
    return config


class AuctionWorldClient(discord.Client):
    def __init__(self, config):
        intents = discord.Intents.default()
        super().__init__(intents=intents)

        self.config   = config
        self.tree     = app_commands.CommandTree(self)
        self.database = Database(config["database"])
        self.commands = {}
        self.logger   = get_logger("bot")

    async def setup_hook(self):
        await self.database.connect()
        self.tree.on_error = self.on_app_command_error
        self.commands = load_commands(
            BASE_DIR / "commands",
            self.tree,
            self.database,
            BASE_DIR / "registry" / "commands.json",
        )

        guild_id = self.config.get("guild_id")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Synced slash commands to guild %s", guild_id)
        else:
            await self.tree.sync()
            logger.info("Synced global slash commands")

        # Start background tasks
        asyncio.create_task(start_weekly_summary_task(self, self.database))

    async def on_ready(self):
        logger.info("Logged in as %s", self.user)
        logger.info("Loaded commands: %s", ", ".join(sorted(self.commands.keys())))
        await recover_active_sessions(self, self.database)

    async def close(self):
        await self.database.close()
        await super().close()

    async def on_app_command_error(self, interaction, error):
        error   = getattr(error, "original", error)
        message = getattr(error, "args", ["Something went wrong while running that command."])[0]
        if interaction.response.is_done():
            await interaction.followup.send(str(message), ephemeral=True)
        else:
            await interaction.response.send_message(str(message), ephemeral=True)


async def main():
    config = load_config()
    client = AuctionWorldClient(config)

    try:
        token = config.get("token")
        if not token or token in {"YOUR_DISCORD_BOT_TOKEN", "your_rotated_bot_token"}:
            raise RuntimeError(
                "Set DISCORD_TOKEN in .env or update config.json before starting the bot."
            )
        await client.start(token)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
