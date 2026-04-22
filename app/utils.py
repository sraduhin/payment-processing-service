import asyncio
import random

DELAY_MIN = 2
DELAY_MAX = 5
SUCCESS_RATE = 0.9


async def emulate_payment_processing() -> bool:
    delay = random.uniform(DELAY_MIN, DELAY_MAX)
    await asyncio.sleep(delay)
    return random.random() < SUCCESS_RATE
