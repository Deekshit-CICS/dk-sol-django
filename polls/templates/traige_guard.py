"""
triage_guard.py - protects the downstream triage service (FastAPI/uvicorn, few workers) from request bursts.

Drop this file into your Django app and put @triage_guard on the view that FORWARDS the
"start triage" call to FastAPI. FastAPI is not touched.

    from .triage_guard import triage_guard, note_session_status

    @login_required
    @never_cache
    @csrf_exempt
    @triage_guard                                 # <- innermost: anonymous users are redirected first, 429s are never cached
    def trigger_triage(request):
        ...                                   # your existing code that calls FastAPI and returns JsonResponse(session_row)

    def session_status(request):
        ...                                   # your existing code
        note_session_status(session_id, triage_status)    # frees the slot when the run finishes

What it enforces, in this order, BEFORE any request is forwarded:
  1. Duplicate: the same incident is already running  -> return THAT run (200, X-Triage-Deduplicated: true);
                nothing is forwarded.
  2. Rate limit: too many triggers from one user/IP in a short window -> 429 + Retry-After.
  3. Concurrency: at most TRIAGE_GUARD_MAX_ACTIVE triages running at once, system-wide -> 429 + Retry-After.
A slot is held from the moment a trigger is accepted until the run finishes (note_session_status /
release_for_session) or TRIAGE_GUARD_ACTIVE_TTL seconds pass, so a crashed run can never block the system forever.

IMPORTANT: the lock lives in Django's cache. It only works across processes if CACHES['default'] (or the alias
in TRIAGE_GUARD_CACHE_ALIAS) is SHARED: Redis, Memcached, the database or file cache. With the default LocMemCache
every gunicorn/uwsgi worker has its own copy and the limits would be per process, i.e. useless.

Settings (all optional):
    TRIAGE_GUARD_MAX_ACTIVE   = 1     concurrent running triages. FastAPI has 2 workers: 1 leaves one free for status calls.
    TRIAGE_GUARD_ACTIVE_TTL   = 900   seconds before an unreleased slot frees itself
    TRIAGE_GUARD_RATE_LIMIT   = 6     triggers per client per window
    TRIAGE_GUARD_RATE_WINDOW  = 60    seconds
    TRIAGE_GUARD_RETRY_AFTER  = 15    seconds advertised when the system is busy
    TRIAGE_GUARD_CACHE_ALIAS  = 'default'
    TRIAGE_GUARD_INCIDENT_PARAM = 'incident_number'
"""
from __future__ import annotations

import functools
import json
import logging
import time
from typing import Any, Callable, Optional

from django.conf import settings
from django.core.cache import caches
from django.http import HttpRequest, HttpResponse, JsonResponse

log = logging.getLogger(__name__)

_now: Callable[[], float] = time.time           # patched in tests
_PREFIX = "triage_guard:"
FINISHED_STATUSES = {"completed", "complete", "success", "successful", "failed", "error"}


def _cfg(name: str, default: Any) -> Any:
    return getattr(settings, f"TRIAGE_GUARD_{name}", default)


def _cache():
    return caches[_cfg("CACHE_ALIAS", "default")]


def _incident_key(number: str) -> str:
    return f"{_PREFIX}incident:{number.upper()}"


def _slot_key(i: int) -> str:
    return f"{_PREFIX}slot:{i}"


def _session_key(session_id: str) -> str:
    return f"{_PREFIX}session:{session_id}"


# --------------------------------------------------------------------------- responses
def _busy(message: str, retry_after: int, reason: str) -> JsonResponse:
    retry_after = max(1, int(retry_after))
    resp = JsonResponse({"status": "busy", "reason": reason, "error": message, "retry_after": retry_after}, status=429)
    resp["Retry-After"] = str(retry_after)
    return resp


# --------------------------------------------------------------------------- helpers
def _incident_of(request: HttpRequest) -> str:
    """The incident number from the query string, a form post, or a JSON body."""
    name = _cfg("INCIDENT_PARAM", "incident_number")
    found = request.GET.get(name) or request.POST.get(name)
    if not found and "json" in (request.content_type or ""):
        try:
            body = json.loads(request.body.decode(request.encoding or "utf-8") or "null")
            found = body.get(name) if isinstance(body, dict) else None
        except Exception:
            found = None
    return str(found or "").strip()


def _client_of(request: HttpRequest) -> str:
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return f"user:{user.pk}"
    # NOTE: behind a proxy make sure REMOTE_ADDR is the real client (e.g. django-xff / trusted proxy setup).
    return f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"


def _rate_limited(client: str) -> Optional[int]:
    """Returns seconds to wait if `client` exceeded the limit, else None. Fixed-window counter."""
    limit, window = int(_cfg("RATE_LIMIT", 6)), int(_cfg("RATE_WINDOW", 60))
    if limit <= 0:
        return None
    cache = _cache()
    now = _now()
    bucket = int(now // window)
    key = f"{_PREFIX}rate:{client}:{bucket}"
    cache.add(key, 0, window + 1)
    try:
        count = cache.incr(key)
    except ValueError:                                   # the key expired between add and incr
        cache.add(key, 1, window + 1)
        count = 1
    if count > limit:
        return int(window - (now % window)) + 1
    return None


def _acquire_slot(number: str) -> Optional[int]:
    cache, ttl = _cache(), int(_cfg("ACTIVE_TTL", 900))
    for i in range(int(_cfg("MAX_ACTIVE", 1))):
        if cache.add(_slot_key(i), {"incident": number.upper(), "ts": _now()}, ttl):    # atomic: exactly one caller wins a slot
            return i
    return None


def _release(number: str) -> None:
    cache = _cache()
    state = cache.get(_incident_key(number))
    if isinstance(state, dict):
        if state.get("slot") is not None:
            cache.delete(_slot_key(state["slot"]))
        if state.get("session_id"):
            cache.delete(_session_key(str(state["session_id"])))
    cache.delete(_incident_key(number))


# --------------------------------------------------------------------------- public API
def release_for_incident(number: str) -> None:
    """Free the slot held by this incident (idempotent)."""
    _release(number)


def release_for_session(session_id: str) -> None:
    """Free the slot of the run with this session id (idempotent)."""
    number = _cache().get(_session_key(str(session_id)))
    if number:
        _release(number)


def note_session_status(session_id: str, triage_status: str) -> bool:
    """Call from the session-status view. Frees the slot once the run has finished; returns True if it did."""
    if (triage_status or "").strip().lower() in FINISHED_STATUSES:
        release_for_session(session_id)
        return True
    return False


def triage_guard(view: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    @functools.wraps(view)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if request.method != "POST":
            return view(request, *args, **kwargs)
        number = _incident_of(request)
        if not number:
            return view(request, *args, **kwargs)            # not a trigger we can reason about: the view answers (e.g. 400)

        cache, ttl = _cache(), int(_cfg("ACTIVE_TTL", 900))
        retry = int(_cfg("RETRY_AFTER", 15))
        inc_key = _incident_key(number)

        # 1. duplicate: the same incident is already running -> hand back THAT run, forward nothing
        running = cache.get(inc_key)
        if isinstance(running, dict) and running.get("payload") is not None:
            log.info("triage_guard: duplicate trigger for %s deduplicated", number)
            resp = JsonResponse(running["payload"], safe=False, status=200)
            resp["X-Triage-Deduplicated"] = "true"
            return resp

        # 2. per-client burst limit
        wait = _rate_limited(_client_of(request))
        if wait is not None:
            log.warning("triage_guard: rate limit hit by %s", _client_of(request))
            return _busy("Too many triage requests in a short time.", wait, "rate_limit")

        # 3. claim the incident (a second request for it that is still being forwarded must not forward again) ...
        if not cache.add(inc_key, {"state": "starting", "ts": _now()}, ttl):
            return _busy(f"A triage for {number} is already being started.", 2, "already_starting")
        # ... and a global slot
        slot = _acquire_slot(number)
        if slot is None:
            cache.delete(inc_key)
            log.warning("triage_guard: no free slot for %s", number)
            return _busy("The triage service is busy with other incidents. Please try again shortly.", retry, "max_active")

        # 4. forward. Anything but a clean 2xx frees everything again so the user can retry immediately.
        try:
            response = view(request, *args, **kwargs)
        except BaseException:
            _release_claim(number, slot)
            raise
        if not (200 <= response.status_code < 300):
            _release_claim(number, slot)
            return response

        payload, session_id = None, None
        try:
            payload = json.loads(response.content.decode(response.charset or "utf-8"))
            if isinstance(payload, dict):
                session_id = payload.get("session_id") or payload.get("id_trg_ssin") or payload.get("id")
        except Exception:
            payload = None
        # If the start call already returned a FINISHED run (the backend did all the work inside the request),
        # there is nothing left to protect: free the slot now instead of waiting for the TTL.
        if isinstance(payload, dict) and _is_finished(payload):
            _release_claim(number, slot)
            return response
        cache.set(inc_key, {"state": "running", "slot": slot, "session_id": session_id, "payload": payload, "ts": _now()}, ttl)
        if session_id:
            cache.set(_session_key(str(session_id)), number.upper(), ttl)
        return response

    return wrapper


def _is_finished(payload: dict) -> bool:
    for key in ("status", "triage_status", "name_trg_ssin_sts_type"):
        v = payload.get(key)
        if isinstance(v, str) and v.strip().lower() in FINISHED_STATUSES:
            return True
    return False


def _release_claim(number: str, slot: int) -> None:
    cache = _cache()
    cache.delete(_slot_key(slot))
    cache.delete(_incident_key(number))
