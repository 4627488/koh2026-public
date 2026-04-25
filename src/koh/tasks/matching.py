"""Round-robin style pairing utilities.

This module provides real, no-bye matching:
- each pair of users plays once per round
- no virtual matches are created
"""

from koh.db.models import User


def pair_users_all_vs_all(users: list[User]) -> list[tuple[User, User]]:
    """Generate all unique user pairs.

    For n users, this yields n*(n-1)/2 pairs.
    """
    pairs: list[tuple[User, User]] = []
    for i in range(len(users)):
        for j in range(i + 1, len(users)):
            pairs.append((users[i], users[j]))
    return pairs
