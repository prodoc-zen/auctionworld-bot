-- ============================================================
-- AuctionWorld Database Schema
-- ============================================================
-- NOTE: Do NOT run this file directly to set up the database.
-- Use the migration system instead:
--
--   python migrate.py migrate
--
-- This file is for reference only, so you can see the full
-- table structure without reading the Python models.
-- ============================================================

CREATE DATABASE IF NOT EXISTS auctionworld
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE auctionworld;

-- Users: every Discord member who interacts with the bot
CREATE TABLE IF NOT EXISTS users (
  discord_id  BIGINT UNSIGNED NOT NULL,
  jennies     BIGINT          NOT NULL DEFAULT 0,
  created_at  DATETIME        NOT NULL,
  updated_at  DATETIME        NOT NULL,
  PRIMARY KEY (discord_id)
);

-- Transactions: one row per economy event (daily reward, etc.)
-- The unique key on (discord_id, reason) prevents double-claiming.
CREATE TABLE IF NOT EXISTS transactions (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  discord_id  BIGINT UNSIGNED NOT NULL,
  amount      BIGINT          NOT NULL,
  reason      VARCHAR(255)    NOT NULL,
  created_at  DATETIME        NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY  uq_transactions_discord_reason (discord_id, reason),
  INDEX       idx_transactions_discord_id (discord_id),
  CONSTRAINT  fk_transactions_user
    FOREIGN KEY (discord_id) REFERENCES users (discord_id)
    ON DELETE CASCADE
);

-- Admin users: Discord members with admin privileges
CREATE TABLE IF NOT EXISTS admin_users (
  discord_id  BIGINT UNSIGNED NOT NULL,
  is_active   TINYINT(1)      NOT NULL DEFAULT 1,
  created_at  DATETIME        NOT NULL,
  updated_at  DATETIME        NOT NULL,
  PRIMARY KEY (discord_id),
  CONSTRAINT  fk_admin_users_user
    FOREIGN KEY (discord_id) REFERENCES users (discord_id)
    ON DELETE CASCADE
);

-- Attendance records: paired time-in / time-out sessions per admin
CREATE TABLE IF NOT EXISTS attendance_records (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  discord_id  BIGINT UNSIGNED NOT NULL,
  time_in_at  DATETIME        NOT NULL,
  time_out_at DATETIME            NULL,
  created_at  DATETIME        NOT NULL,
  updated_at  DATETIME        NOT NULL,
  PRIMARY KEY (id),
  INDEX       idx_attendance_discord_id (discord_id),
  CONSTRAINT  fk_attendance_user
    FOREIGN KEY (discord_id) REFERENCES users (discord_id)
    ON DELETE CASCADE
);

-- Hosting queue entries: one row per queue slot (Left / Mid / Right)
-- status: waiting | active | done | skipped
CREATE TABLE IF NOT EXISTS hosting_queue_entries (
  id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  queue_name   VARCHAR(20)     NOT NULL,
  discord_id   BIGINT UNSIGNED NOT NULL,
  channel_id   BIGINT UNSIGNED     NULL,
  status       VARCHAR(20)     NOT NULL DEFAULT 'waiting',
  joined_at    DATETIME        NOT NULL,
  started_at   DATETIME            NULL,
  expires_at   DATETIME            NULL,
  completed_at DATETIME            NULL,
  created_at   DATETIME        NOT NULL,
  updated_at   DATETIME        NOT NULL,
  PRIMARY KEY (id),
  INDEX        idx_hqe_queue_name (queue_name),
  INDEX        idx_hqe_discord_id (discord_id),
  INDEX        idx_hqe_status (status)
);

-- Schema migrations: tracks which migration files have been applied
CREATE TABLE IF NOT EXISTS schema_migrations (
  version    VARCHAR(255) NOT NULL,
  applied_at DATETIME     NOT NULL,
  PRIMARY KEY (version)
);
