"""Shared login throttling for /login/ and the custom admin login.

Model:
* HARD lock is keyed by (scope, username, client IP). After MAX_ATTEMPTS
  failures from one IP that IP can't log in as that user for LOCKOUT_SECONDS.
  An attacker on another IP therefore can never lock the real user out.
* A per-username counter (all IPs) is kept only for monitoring: when it gets
  high we log a warning and add a small, capped delay to failed attempts.
  It NEVER blocks a login, so it can't be used as an account-lockout DoS.

State lives in the Django cache (Redis in production).
"""
import hashlib
import logging
import time

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 900          # 15 minutes
USERNAME_ALERT_THRESHOLD = 20  # distributed-attack warning level


def get_client_ip(request):
    """REMOTE_ADDR only (set by the server / trusted proxy, not client headers)."""
    return request.META.get('REMOTE_ADDR') or '0.0.0.0'


def _norm(username):
    return (username or '').strip().lower()


def _h(value):
    # Hash so arbitrary usernames can't create odd cache keys.
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:32]


def ip_key(scope, username, ip):
    return f'login_fail:{scope}:ip:{_h(_norm(username) + "|" + ip)}'


def user_key(scope, username):
    return f'login_fail:{scope}:user:{_h(_norm(username))}'


def _incr(key):
    cache.add(key, 0, LOCKOUT_SECONDS)
    try:
        value = cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.set(key, 1, LOCKOUT_SECONDS)
        value = 1
    # sliding window: lock lasts LOCKOUT_SECONDS after the latest failure
    cache.touch(key, LOCKOUT_SECONDS)
    return value


def failures(scope, username, ip):
    return int(cache.get(ip_key(scope, username, ip)) or 0)


def is_locked(scope, username, ip):
    return failures(scope, username, ip) >= MAX_ATTEMPTS


def remaining_attempts(scope, username, ip):
    return max(0, MAX_ATTEMPTS - failures(scope, username, ip))


def record_failure(scope, username, ip):
    """Record a failed login. Returns attempts remaining for this username+IP."""
    count = _incr(ip_key(scope, username, ip))
    total = _incr(user_key(scope, username))
    if total >= USERNAME_ALERT_THRESHOLD:
        logger.warning('Many failed %s logins for user %r (%s total, latest IP %s)',
                       scope, _norm(username), total, ip)
        delay = float(getattr(settings, 'LOGIN_SOFT_DELAY_SECONDS', 0.5))
        if delay > 0:
            time.sleep(min(delay, 1.0))
    return max(0, MAX_ATTEMPTS - count)


def record_success(scope, username, ip):
    cache.delete(ip_key(scope, username, ip))
