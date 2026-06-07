# AWS Deployment Checklist

This bot is easiest to host on one small EC2 instance with MySQL on Amazon RDS.

## 1. Prepare AWS

1. Create an RDS MySQL database.
2. Create an EC2 instance.
3. Put EC2 and RDS in the same VPC/security group path.
4. Allow EC2 to connect to RDS on port `3306`.
5. Do not expose MySQL to the public internet.

## 2. Install Server Packages

On the EC2 instance, install:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

## 3. Upload The Bot

Clone or upload this project to the instance:

```bash
git clone <your-repo-url> auctionworld-bot
cd auctionworld-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4. Configure `.env`

Create `.env` on the server:

```text
DISCORD_TOKEN=your_rotated_bot_token
GUILD_ID=your_server_id
DB_HOST=your-rds-endpoint.amazonaws.com
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=auctionworld
DB_PORT=3306
DB_ECHO=false
WEEKLY_QUOTA_HOURS=10
HOSTING_SESSION_MINUTES=60
HOSTING_START_GRACE_MINUTES=5
```

## 5. Run Migrations

```bash
source .venv/bin/activate
python migrate.py migrate
```

Use `python migrate.py migrate:refresh` only when you intentionally want to drop and rebuild every table in the configured database.

## 6. Run With systemd

Create `/etc/systemd/system/auctionworld-bot.service`:

```ini
[Unit]
Description=AuctionWorld Discord Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/ubuntu/auctionworld-bot
ExecStart=/home/ubuntu/auctionworld-bot/.venv/bin/python bot.py
Restart=always
RestartSec=10
User=ubuntu

[Install]
WantedBy=multi-user.target
```

Enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable auctionworld-bot
sudo systemctl start auctionworld-bot
sudo systemctl status auctionworld-bot
```

Logs:

```bash
journalctl -u auctionworld-bot -f
```

## 7. Deployment Notes

- Keep `.env` out of git.
- Rotate the Discord token if it was ever committed or shared.
- Use RDS backups before running destructive migrations.
- Keep only one running bot instance unless you add distributed queue timers.
