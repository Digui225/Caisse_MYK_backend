"""UUIDv7 (RFC 9562) : ordonnables dans le temps, donc bons pour les index B-tree.

`uuid.uuid7` n'existe qu'à partir de Python 3.14 ; on garde notre implémentation.
"""

import os
import time
import uuid


def uuid7() -> uuid.UUID:
    unix_ms = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10), "big")
    value = (unix_ms & 0xFFFF_FFFF_FFFF) << 80
    value |= 0x7 << 76  # version
    value |= ((rand >> 62) & 0xFFF) << 64  # rand_a (12 bits)
    value |= 0b10 << 62  # variante RFC 4122
    value |= rand & 0x3FFF_FFFF_FFFF_FFFF  # rand_b (62 bits)
    return uuid.UUID(int=value)
