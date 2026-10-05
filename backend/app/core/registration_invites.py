"""One-time, email-bound registration invitations backed by shared Redis."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.redis import get_redis_client


INVITE_KEY_PREFIX = "nexpulse:registration-invite:"
_CONSUME_INVITE_SCRIPT = """
local email = redis.call('GET', KEYS[1])
if not email then return 0 end
if string.lower(email) ~= string.lower(ARGV[1]) then return -1 end
redis.call('DEL', KEYS[1])
return 1
"""


class InvitationStoreUnavailable(RuntimeError):
    """Raised when Redis cannot safely store or consume an invitation."""


def _key_for(code: str) -> str:
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    return f"{INVITE_KEY_PREFIX}{digest}"


async def create_registration_invite(email: str) -> tuple[str, datetime]:
    client = get_redis_client()
    if client is None:
        raise InvitationStoreUnavailable

    code = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.REGISTRATION_INVITE_TTL_SECONDS)
    try:
        created = await client.set(
            _key_for(code), email.strip().lower(), ex=settings.REGISTRATION_INVITE_TTL_SECONDS, nx=True
        )
    except Exception as exc:
        raise InvitationStoreUnavailable from exc
    if not created:
        raise InvitationStoreUnavailable
    return code, expires_at


async def consume_registration_invite(code: str, email: str) -> bool:
    client = get_redis_client()
    if client is None:
        raise InvitationStoreUnavailable

    try:
        result = await client.eval(_CONSUME_INVITE_SCRIPT, 1, _key_for(code), email.strip().lower())
    except Exception as exc:
        raise InvitationStoreUnavailable from exc
    return int(result) == 1
