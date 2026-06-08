from sqlalchemy import text


async def upgrade(connection):
    # 1) Remove duplicate admin_users table usage; admin_profiles is canonical.
    await connection.execute(text("DROP TABLE IF EXISTS admin_users"))

    # 2) Add table for gacha image assets (URL + binary blob for MySQL uploads).
    await connection.execute(text(
        """
        CREATE TABLE IF NOT EXISTS gacha_character_assets (
            id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
            character_name VARCHAR(100) NOT NULL,
            image_url VARCHAR(500) NULL,
            image_blob LONGBLOB NULL,
            image_mime VARCHAR(100) NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            PRIMARY KEY (id),
            UNIQUE KEY uq_gacha_character_assets_character_name (character_name),
            INDEX idx_gacha_character_assets_character_name (character_name)
        )
        """
    ))
