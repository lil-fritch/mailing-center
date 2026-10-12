# Throttle and pause utilities shared across services.

import asyncio
import random


async def pause_between_emails(seconds: float) -> None:
    """Pause execution for a given number of seconds between email sends.

    This helper centralizes delay logic and is easy to mock in tests.
    """
    await asyncio.sleep(max(0.0, float(seconds)))


async def pause_between_emails_random(min_seconds: float, max_seconds: float) -> float:
    """Pause for a random duration uniformly sampled in [min_seconds, max_seconds].

    Returns the chosen pause value in seconds.
    """
    low = max(0.0, float(min_seconds))
    high = max(low, float(max_seconds))
    chosen = random.uniform(low, high)
    await asyncio.sleep(chosen)
    return chosen 