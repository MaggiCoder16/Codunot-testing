"""Top.gg voting helper fallback.

If no Top.gg integration is configured in this minimal repo, features should remain usable.
"""

from __future__ import annotations


async def has_voted(_user_id: int) -> bool:
    return True
