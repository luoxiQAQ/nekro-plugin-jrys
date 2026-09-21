"""运势抽签逻辑（权重、节假日、每日固定）"""

import random
from datetime import datetime
from typing import Any, Dict, List, Tuple

GOOD_MIN_SCORE = 70
NORMAL_MIN_SCORE = 56


def _classify(keys: List[str]) -> Tuple[List[str], List[str], List[str]]:
    good = [k for k in keys if int(k) > GOOD_MIN_SCORE]
    normal = [k for k in keys if NORMAL_MIN_SCORE <= int(k) <= GOOD_MIN_SCORE]
    bad = [k for k in keys if int(k) < NORMAL_MIN_SCORE]
    return good, normal, bad


def draw_fortune(
    deck: Dict[str, List[Dict[str, Any]]],
    user_id: str,
    *,
    fixed_daily: bool,
    holiday_enabled: bool,
    holidays: List[str],
    normal_rates: Dict[str, int],
    holiday_rates: Dict[str, int],
    now: datetime | None = None,
) -> Tuple[Dict[str, Any], bool]:
    """抽取一条运势文案，返回 (文案条目, 是否命中节假日权重)"""
    now = now or datetime.now()
    rng = random.Random()
    if fixed_daily:
        rng.seed(f"{user_id}-{now.strftime('%Y-%m-%d')}")

    valid_keys = [k for k in deck if not k.startswith("_")]
    if not valid_keys:
        raise ValueError("运势文案库为空")

    is_holiday = holiday_enabled and now.strftime("%m-%d") in holidays
    rates = holiday_rates if is_holiday else normal_rates

    good_keys, normal_keys, bad_keys = _classify(valid_keys)
    weights = []
    for key in valid_keys:
        score = int(key)
        if score > GOOD_MIN_SCORE:
            weights.append(rates.get("good", 40) / max(len(good_keys), 1))
        elif score >= NORMAL_MIN_SCORE:
            weights.append(rates.get("normal", 40) / max(len(normal_keys), 1))
        else:
            weights.append(rates.get("bad", 20) / max(len(bad_keys), 1))

    # 权重全被配置为 0 时退化为均匀随机
    if sum(weights) <= 0:
        weights = [1] * len(valid_keys)

    chosen_key = rng.choices(valid_keys, weights=weights, k=1)[0]
    entries = deck[chosen_key]
    if not entries:
        raise ValueError(f"运势文案库 {chosen_key} 下没有条目")
    return rng.choice(entries), is_holiday
