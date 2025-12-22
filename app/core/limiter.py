from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

def get_key_func(request: Request):
    """
    Rate limiting key function.
    Uses X-Device-ID header if present, otherwise falls back to client IP.
    """
    device_id = request.headers.get("X-Device-ID")
    if device_id:
        return device_id
    return get_remote_address(request)

# Default to in-memory storage
limiter = Limiter(key_func=get_key_func)
