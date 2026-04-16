#!/usr/bin/env python3
"""Generate a Django-compatible secret key without requiring Django."""

from __future__ import annotations

import secrets

ALPHABET = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'
KEY_LENGTH = 50


def main() -> int:
    print(''.join(secrets.choice(ALPHABET) for _ in range(KEY_LENGTH)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
