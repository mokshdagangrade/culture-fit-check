"""
Shared HTTP helper for every extractor. Three jobs:

  1. THROTTLE - Keep a minimum gap between two requests to the same host (GDELT asks for roughly 1 request per 5 seconds).
  2. RETRY - On 429 / 5xx, wait and retry, honoring the server's Retry-After header when it sends one, otherwise backing off exponentially.
  3. GIVE UP - If a host is still returning 429 after the retries (or asks us to wait longer than MAX_WAIT_SECONDS, e.g. a monthly quota), stop calling that host for the rest of the run instead of burning minutes on every state.
"""

import time
from urllib.parse import urlparse

import requests

# Minimum seconds between two requests to the same host.
MIN_INTERVAL_SECONDS = {
    "api.gdeltproject.org": 6.0,  
}
DEFAULT_MIN_INTERVAL_SECONDS = 0.5

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 3                    
BACKOFF_BASE_SECONDS = 10          
MAX_WAIT_SECONDS = 120             

_last_call: dict[str, float] = {}
_blocked_hosts: set[str] = set()


class RateLimited(Exception):
    """A host kept returning 429, so it is skipped for the rest of the run."""


def reset():
    """Clear throttle and blocked-host state (used by the tests)."""
    _last_call.clear()
    _blocked_hosts.clear()


def _throttle(host: str) -> None:
    gap = MIN_INTERVAL_SECONDS.get(host, DEFAULT_MIN_INTERVAL_SECONDS)
    last = _last_call.get(host)
    if last is not None:
        wait = gap - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
    _last_call[host] = time.monotonic()


def throttle_host(host: str) -> None:
    _throttle(host)


def _retry_delay(resp, attempt: int):
    """Seconds to wait before retrying, or None if the server wants us to wait too long."""
    header = resp.headers.get("Retry-After")
    if header:
        try:
            seconds = float(header)
        except ValueError:
            seconds = None
        if seconds is not None:
            return seconds if seconds <= MAX_WAIT_SECONDS else None
    return min(BACKOFF_BASE_SECONDS * 2 ** attempt, MAX_WAIT_SECONDS)


def _request(method: str, url: str, **kwargs):
    host = urlparse(url).netloc
    if host in _blocked_hosts:
        raise RateLimited(f"{host} was rate-limited earlier in this run; skipping.")

    send = requests.get if method == "GET" else requests.post

    for attempt in range(MAX_RETRIES + 1):
        _throttle(host)
        resp = send(url, **kwargs)

        if resp.status_code not in RETRYABLE_STATUS:
            return resp
        if attempt == MAX_RETRIES:
            break

        delay = _retry_delay(resp, attempt)
        if delay is None:
            break
        print(f"  [retry] {host} returned {resp.status_code}; waiting {delay:.0f}s "
              f"(retry {attempt + 1}/{MAX_RETRIES})")
        time.sleep(delay)

    if resp.status_code == 429:
        _blocked_hosts.add(host)
        raise RateLimited(
            f"{host} is still returning 429 after retries; skipping it for the rest "
            f"of this run. Wait a few minutes before running again."
        )
    resp.raise_for_status()   # 5xx that never recovered: raises requests.HTTPError
    return resp


def polite_get(url: str, **kwargs):
    return _request("GET", url, **kwargs)


def polite_post(url: str, **kwargs):
    return _request("POST", url, **kwargs)
