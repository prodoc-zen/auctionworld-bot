import json
import random
from pathlib import Path

GACHA_POOL_PATH = Path(__file__).resolve().parent.parent.parent / "registry" / "gacha_pool.json"
PULL_COST       = 120
MAX_LEVEL       = 10
PITY_4STAR      = 90
PITY_3STAR      = 10

STAR_EMOJIS   = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐"}
RARITY_COLORS = {1: 0x9e9e9e, 2: 0x4caf50, 3: 0x2196f3, 4: 0xffc107}


def load_pool():
    with GACHA_POOL_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_pool(pool):
    with GACHA_POOL_PATH.open("w", encoding="utf-8") as f:
        json.dump(pool, f, indent=2)


def get_character_image(name: str) -> str | None:
    """Get image URL for a character by name."""
    pool = load_pool()
    for rarity_data in pool.values():
        for char in rarity_data["characters"]:
            if char["name"].lower() == name.lower():
                return char.get("image")
    return None


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
