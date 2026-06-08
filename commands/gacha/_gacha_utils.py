import json
import random
from pathlib import Path

GACHA_POOL_PATH = Path(__file__).resolve().parent.parent.parent / "registry" / "gacha_pool.json"
PULL_COST       = 120
MAX_LEVEL       = 10

STAR_EMOJIS = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐"}
RARITY_COLORS = {1: 0x9e9e9e, 2: 0x4caf50, 3: 0x2196f3, 4: 0xffc107}


def load_pool():
    with GACHA_POOL_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def pull_character():
    pool      = load_pool()
    rarities  = list(pool.keys())
    weights   = [pool[r]["rate"] for r in rarities]
    rarity    = random.choices(rarities, weights=weights, k=1)[0]
    character = random.choice(pool[rarity]["characters"])
    return character, int(rarity)


def pull_many(n: int):
    return [pull_character() for _ in range(n)]
