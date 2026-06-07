import json
from functools import lru_cache
from pathlib import Path

from discord import app_commands


def normalize_ids(values):
    return {int(value) for value in values or [] if str(value).strip()}


def normalize_names(values):
    return [str(value).strip() for value in values or [] if str(value).strip()]


@lru_cache(maxsize=1)
def load_access_groups():
    base_dir = Path(__file__).resolve().parent.parent
    groups_path = base_dir / "registry" / "access_groups.json"

    if not groups_path.exists():
        return {}

    with groups_path.open("r", encoding="utf-8") as groups_file:
        groups = json.load(groups_file)

    if not isinstance(groups, dict):
        raise ValueError("registry/access_groups.json must contain a JSON object.")

    return groups


def resolve_access_from_groups(access):
    groups = load_access_groups()
    resolved_user_ids = normalize_ids(access.get("user_ids"))
    resolved_role_ids = normalize_ids(access.get("role_ids"))
    group_names = normalize_names(access.get("groups"))

    visited = set()

    def add_group(group_name):
        if group_name in visited:
            return

        visited.add(group_name)
        group = groups.get(group_name)
        if group is None:
            raise ValueError(f"Unknown access group: {group_name}")

        resolved_user_ids.update(normalize_ids(group.get("user_ids")))
        resolved_role_ids.update(normalize_ids(group.get("role_ids")))

        for included_group in normalize_names(group.get("include_groups")):
            add_group(included_group)

    for group_name in group_names:
        add_group(group_name)

    return resolved_user_ids, resolved_role_ids


def build_command_access_check(command_name, metadata):
    access = metadata.get("access", {})
    allowed_user_ids, allowed_role_ids = resolve_access_from_groups(access)

    async def predicate(interaction):
        if not allowed_user_ids and not allowed_role_ids:
            return True

        if interaction.user.id in allowed_user_ids:
            return True

        if allowed_role_ids and interaction.guild is None:
            raise app_commands.CheckFailure(
                f"/{command_name} can only check role access inside a server."
            )

        user_roles = getattr(interaction.user, "roles", [])
        user_role_ids = {role.id for role in user_roles}

        if user_role_ids.intersection(allowed_role_ids):
            return True

        raise app_commands.CheckFailure(
            f"You do not have access to /{command_name}."
        )

    return predicate
