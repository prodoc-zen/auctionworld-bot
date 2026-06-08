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


def pull_character(pulls_since_4star=0, pulls_since_3star=0):
    pool = load_pool()

    if pulls_since_4star >= PITY_4STAR - 1:
        rarity    = "4"
        character = random.choice(pool["4"]["characters"])
        return character, 4

    if pulls_since_3star >= PITY_3STAR - 1:
        rarity    = random.choice(["3", "4"])
        character = random.choice(pool[rarity]["characters"])
        return character, int(rarity)

    rarities  = list(pool.keys())
    weights   = [pool[r]["rate"] for r in rarities]
    rarity    = random.choices(rarities, weights=weights, k=1)[0]
    character = random.choice(pool[rarity]["characters"])
    return character, int(rarity)


def pull_many(n: int, pulls_since_4star=0, pulls_since_3star=0):
    """Pull n characters, correctly updating pity between each pull."""
    results = []
    p4 = pulls_since_4star
    p3 = pulls_since_3star

    for _ in range(n):
        char, rarity = pull_character(p4, p3)
        results.append((char, rarity))

        # Update pity counters after each pull
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
