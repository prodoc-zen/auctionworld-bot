import json
import random
from pathlib import Path

GACHA_POOL_PATH     = Path(__file__).resolve().parent.parent.parent / "registry" / "gacha_pool.json"
GACHA_SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "registry" / "gacha_settings.json"


def _load_settings():
    with GACHA_SETTINGS_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        "pull_cost":   int(data.get("pull_cost", 120)),
        "max_level":   int(data.get("max_level", 10)),
        "pity_4star":  int(data.get("pity_4star", 90)),
        "pity_3star":  int(data.get("pity_3star", 10)),
        "star_emojis": {int(k): v for k, v in data.get("star_emojis", {}).items()},
        "rarity_colors": {int(k): int(v) for k, v in data.get("rarity_colors", {}).items()},
        "elements":    tuple(data.get("elements", ["fire", "water", "earth", "wind", "light", "dark"])),
        "default_character_stats": data.get("default_character_stats", {}),
    }


_SETTINGS = _load_settings()

PULL_COST    = _SETTINGS["pull_cost"]
MAX_LEVEL    = _SETTINGS["max_level"]
PITY_4STAR   = _SETTINGS["pity_4star"]
PITY_3STAR   = _SETTINGS["pity_3star"]
STAR_EMOJIS  = _SETTINGS["star_emojis"]  or {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐"}
RARITY_COLORS = _SETTINGS["rarity_colors"] or {1: 0x9e9e9e, 2: 0x4caf50, 3: 0x2196f3, 4: 0xffc107}
ELEMENT_TYPES = _SETTINGS["elements"] or ("fire", "water", "earth", "wind", "light", "dark")

DEFAULT_CHARACTER_STATS = _SETTINGS["default_character_stats"] or {
    "health": 100,
    "element": "fire",
    "normal_attack":    {"name": "Basic Strike", "damage": 12, "cooldown": 0},
    "secondary_attack": {"name": "Skill",        "damage": 24, "cooldown": 2},
    "power_attack":     {"name": "Ultimate",     "damage": 40, "cooldown": 4},
}


def load_pool():
    with GACHA_POOL_PATH.open("r", encoding="utf-8") as f:
        pool = json.load(f)
    for rarity_data in pool.values():
        for char in rarity_data.get("characters", []):
            normalize_character_data(char)
    return pool


def save_pool(pool):
    with GACHA_POOL_PATH.open("w", encoding="utf-8") as f:
        json.dump(pool, f, indent=2)


def normalize_character_data(char: dict) -> dict:
    char.setdefault("image", None)
    char.setdefault("health", DEFAULT_CHARACTER_STATS["health"])

    element = str(char.get("element", DEFAULT_CHARACTER_STATS["element"])).lower()
    if element not in ELEMENT_TYPES:
        element = DEFAULT_CHARACTER_STATS["element"]
    char["element"] = element

    for key in ("normal_attack", "secondary_attack", "power_attack"):
        base   = DEFAULT_CHARACTER_STATS[key]
        attack = char.get(key) or {}
        char[key] = {
            "name":     str(attack.get("name",     base["name"])),
            "damage":   int(attack.get("damage",   base["damage"])),
            "cooldown": int(attack.get("cooldown", base["cooldown"])),
        }

    char["health"] = int(char.get("health", DEFAULT_CHARACTER_STATS["health"]))
    return char


def find_character(pool: dict, name: str):
    for rarity, rarity_data in pool.items():
        for char in rarity_data.get("characters", []):
            if char["name"].lower() == name.lower():
                return rarity, normalize_character_data(char)
    return None, None


def get_character_image(name: str):
    pool = load_pool()
    _, char = find_character(pool, name)
    if char:
        return char.get("image")
    return None


async def get_character_image_for_session(session, name: str):
    """Get character image — reads from gacha_pool.json only."""
    return get_character_image(name)


def get_character_data(name: str):
    pool = load_pool()
    rarity, char = find_character(pool, name)
    if rarity is None:
        return None, None
    return int(rarity), char


def pull_character(pulls_since_4star=0, pulls_since_3star=0):
    pool = load_pool()

    if pulls_since_4star >= PITY_4STAR - 1:
        char_data = random.choice(pool["4"]["characters"])
        return char_data["name"], 4, char_data.get("image")

    if pulls_since_3star >= PITY_3STAR - 1:
        rarity    = random.choice(["3", "4"])
        char_data = random.choice(pool[rarity]["characters"])
        return char_data["name"], int(rarity), char_data.get("image")

    rarities  = list(pool.keys())
    weights   = [pool[r]["rate"] for r in rarities]
    rarity    = random.choices(rarities, weights=weights, k=1)[0]
    char_data = random.choice(pool[rarity]["characters"])
    return char_data["name"], int(rarity), char_data.get("image")


def pull_many(n: int, pulls_since_4star=0, pulls_since_3star=0):
    results = []
    p4 = pulls_since_4star
    p3 = pulls_since_3star

    for _ in range(n):
        char, rarity, image = pull_character(p4, p3)
        results.append((char, rarity, image))

        if rarity == 4:
            p4 = 0
            p3 = 0
        elif rarity >= 3:
            p3 = 0
            p4 += 1
        else:
            p4 += 1
            p3 += 1

    return results, p4, p3
