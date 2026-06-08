name        = "test-weekly-summary"
description = "Manually trigger the weekly summary (Developer only)"

DEVELOPER_ROLE_ID = 1457710235069186349


def register(tree, database):
    @tree.command(name=name, description=description)
    async def test_weekly_summary(interaction):
        user_role_ids = {role.id for role in interaction.user.roles}
        if DEVELOPER_ROLE_ID not in user_role_ids:
            await interaction.response.send_message(
                "Only Developers can trigger this.", ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        from tasks.weekly_summary import send_weekly_summary
        await send_weekly_summary(interaction.client, database)

        await interaction.followup.send("✅ Weekly summary sent!", ephemeral=True)
