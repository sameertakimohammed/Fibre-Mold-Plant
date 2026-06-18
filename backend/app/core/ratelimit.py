"""Shared slowapi Limiter.

Defined in its own module so both main.py (which registers the middleware and
exception handler) and the routers (which decorate endpoints) can import the
SAME limiter without a circular import through main.

In-memory storage is fine for this single-host deployment (no Redis). The
key_func is the client IP, so the limit is per source address.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
