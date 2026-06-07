# How To Make Your Own Slash Command

This bot uses one file per command. You do not edit `bot.py` when adding a new command.

## Where To Put The Code

Put new command files inside:

```text
commands/<category>/<command_name>.py
```

Examples:

```text
commands/economy/pay.py
commands/admin/ban.py
commands/attendance/my_hours.py
```

## Basic Command Template

Create a file like:

```text
commands/economy/hello.py
```

Then put this code inside it:

```python
name = "hello"
description = "Say hello"


def register(tree, database):
    @tree.command(name=name, description=description)
    async def hello(interaction):
        await interaction.response.send_message(f"Hello, {interaction.user.mention}!")
```

Then register it in:

```text
registry/commands.json
```

Add:

```json
"hello": {
  "file": "commands/economy/hello.py",
  "description": "Say hello",
  "usage": "/hello",
  "access": {
    "user_ids": [],
        "role_ids": [],
        "groups": []
  }
}
```

Restart the bot. Discord will sync the slash command automatically.

## How Command Access Works

Each command has an `access` block in `registry/commands.json`.

```json
"adminthing": {
  "file": "commands/admin/adminthing.py",
  "description": "Admin-only command",
  "usage": "/adminthing",
  "access": {
    "user_ids": ["123456789012345678"],
        "role_ids": ["987654321098765432"],
        "groups": ["admins"]
  }
}
```

If `user_ids` contains a Discord user ID, that person can run the command. If `role_ids` contains one of their role IDs, they can run it. `groups` lets you reference reusable access groups from `registry/access_groups.json`. If all are empty, everyone can run it.

## How The Bot Imports Your Command

You do not add an import to `bot.py`.

The file:

```text
handlers/command_loader.py
```

automatically scans every `.py` file inside:

```text
commands/
```

Then it imports each file and calls:

```python
register(tree, database)
```

That is why every command file must export:

```python
name = "yourcommand"
description = "What your command does"


def register(tree, database):
    ...
```

## How To Import And Use Database Models

Database models live in:

```text
database/models.py
```

This project uses SQLAlchemy ORM, which is the Python equivalent of an Eloquent-style model layer. You work with models like `User(...)` instead of building unsafe SQL strings.

Example command that adds Jennies:

```python
from datetime import datetime, timezone

from sqlalchemy import select

from database.models import Transaction, User


name = "bonus"
description = "Give yourself a small Jennies bonus"


def register(tree, database):
    @tree.command(name=name, description=description)
    async def bonus(interaction):
        discord_id = interaction.user.id

        async with database.session() as session:
            result = await session.execute(select(User).where(User.discord_id == discord_id))
            user = result.scalar_one_or_none()

            if user is None:
                user = User(discord_id=discord_id, jennies=0)
                session.add(user)

            reason = f"bonus:{datetime.now(timezone.utc).isoformat()}"
            user.jennies += 25
            session.add(Transaction(discord_id=discord_id, amount=25, reason=reason))
            await session.commit()

        await interaction.response.send_message(
            f"{interaction.user.mention}, you received 25 Jennies."
        )
```

## How Slash Command Options Work

Use function parameters to create slash command inputs.

```python
from discord import app_commands


name = "say"
description = "Make the bot say something"


def register(tree, database):
    @tree.command(name=name, description=description)
    @app_commands.describe(text="The message to send")
    async def say(interaction, text: str):
        await interaction.response.send_message(text)
```

Discord will show a `/say` command with a `text` box.

## How To Make A Migration

Migrations live in:

```text
database/migrations/
```

Create a new file with the next number, for example:

```text
database/migrations/002_add_shop_items.py
```

Example migration:

```python
from sqlalchemy import BigInteger, Column, MetaData, String, Table


metadata = MetaData()

shop_items = Table(
    "shop_items",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("name", String(100), nullable=False),
    Column("price", BigInteger, nullable=False),
)


async def upgrade(connection):
    await connection.run_sync(metadata.create_all)
```

Run migrations with:

```powershell
python migrate.py
```

The bot stores completed migrations in the `schema_migrations` table, so each migration runs only once.

## Why This Prevents SQL Injection

Do this:

```python
await session.execute(select(User).where(User.discord_id == interaction.user.id))
```

Do not do this:

```python
f"SELECT * FROM users WHERE discord_id = {interaction.user.id}"
```

The ORM sends values as parameters to MySQL instead of pasting user input into SQL text.
