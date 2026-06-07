import importlib.util
import json
from pathlib import Path

from utils.access import build_command_access_check


class LoadedCommand:
    def __init__(self, name, description, register, path):
        self.name = name
        self.description = description
        self.register = register
        self.path = path


def load_commands(commands_dir, tree, database, registry_path=None):
    commands = {}
    commands_dir = Path(commands_dir)
    registry = load_registry(registry_path) if registry_path is not None else {}

    for command_file in commands_dir.rglob("*.py"):
        if command_file.name.startswith("_"):
            continue

        module_name = ".".join(command_file.with_suffix("").parts[-3:])
        spec = importlib.util.spec_from_file_location(module_name, command_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        name = getattr(module, "name", None)
        description = getattr(module, "description", None)
        register = getattr(module, "register", None)

        if not name or not description or not callable(register):
            raise ValueError(f"{command_file} must export name, description, and register().")

        command_name = name.lower()
        if command_name in commands:
            raise ValueError(f"Duplicate command name: {command_name}")

        register(tree, database)
        command = tree.get_command(command_name)
        if command is not None and command_name in registry:
            access_check = build_command_access_check(command_name, registry[command_name])
            if hasattr(command, "add_check"):
                command.add_check(access_check)
            else:
                command.checks.append(access_check)
        commands[command_name] = LoadedCommand(command_name, description, register, command_file)

    if registry_path is not None:
        validate_registry(commands, commands_dir, registry_path, registry)

    return commands


def load_registry(registry_path):
    registry_path = Path(registry_path)
    with registry_path.open("r", encoding="utf-8") as registry_file:
        return json.load(registry_file)


def validate_registry(commands, commands_dir, registry_path, registry=None):
    registry_path = Path(registry_path)
    project_root = commands_dir.parent

    if registry is None:
        registry = load_registry(registry_path)

    registered_names = set(registry.keys())
    loaded_names = set(commands.keys())

    missing_from_registry = loaded_names - registered_names
    missing_from_files = registered_names - loaded_names

    if missing_from_registry:
        raise ValueError(f"Commands missing from registry: {sorted(missing_from_registry)}")

    if missing_from_files:
        raise ValueError(f"Registry entries missing command files: {sorted(missing_from_files)}")

    for command_name, metadata in registry.items():
        expected_path = (project_root / metadata["file"]).resolve()
        actual_path = commands[command_name].path.resolve()

        if expected_path != actual_path:
            raise ValueError(
                f"Registry path for {command_name} points to {expected_path}, "
                f"but loaded {actual_path}."
            )
