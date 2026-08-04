# Standard Library
import asyncio
import logging
from functools import wraps
from http import HTTPStatus

# Third Party
from aiopenapi3 import RequestError
from esi.exceptions import ESIBucketLimitException, HTTPClientError, HTTPServerError

# Django
from django.utils import timezone

log = logging.getLogger("esi")

# ESI Error Rate Limit Management
_ERROR_FLAG_UNTIL = None


def get_error_flag():
    """Returns timestamp until which ESI is rate-limited, or 0.0 if not rate-limited."""
    return _ERROR_FLAG_UNTIL or 0.0


def set_error_flag(seconds: int):
    """Set ESI rate limit for N seconds."""
    global _ERROR_FLAG_UNTIL  # pylint: disable=global-statement
    _ERROR_FLAG_UNTIL = timezone.now().timestamp() + seconds


def clear_error_flag():
    """Clear ESI rate limit flag."""
    global _ERROR_FLAG_UNTIL  # pylint: disable=global-statement
    _ERROR_FLAG_UNTIL = None


def esi_request_handler(argument: str = None):
    """Handle common ESI request errors and normalize not-found responses.

    Args:
        argument: Optional parameter name to extract ID for logging
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            log_path = func.__name__

            # Extract entity_id for logging (once)
            entity_id = None
            if argument:
                entity_id = kwargs.get(argument) or (args[0] if args else None)
            id_str = f" (ID {entity_id})" if entity_id else ""

            for retry_count in range(3):
                # Check for ESI rate limit
                error_until = get_error_flag()
                if error_until and error_until >= timezone.now().timestamp():
                    sleep_time = error_until - timezone.now().timestamp()
                    log.warning(
                        "ESI rate limit active for %s%s. Waiting %.1fs before retry (%d/3)...",
                        log_path,
                        id_str,
                        sleep_time,
                        retry_count + 1,
                    )
                    await asyncio.sleep(sleep_time + 1)
                    continue

                try:
                    return await func(self, *args, **kwargs) or None
                except HTTPClientError as e:
                    if e.status_code == HTTPStatus.NOT_FOUND:
                        return None
                    if e.status_code in (HTTPStatus.TOO_MANY_REQUESTS, 420):
                        log.warning(
                            "ESI error limit (HTTP %s) for %s%s. Waiting 60s before retry (%d/3)...",
                            e.status_code,
                            log_path,
                            id_str,
                            retry_count + 1,
                        )
                        set_error_flag(60)
                        await asyncio.sleep(61)
                        continue
                    log.error("Client Error fetching %s%s: %s", log_path, id_str, e)
                    return None
                except HTTPServerError as e:
                    status = getattr(e, "status_code", "unknown")
                    log.error(
                        "Server error fetching %s%s (status %s): %s",
                        log_path,
                        id_str,
                        status,
                        e,
                    )
                    return None
                except ESIBucketLimitException as e:
                    log.warning(
                        "ESI bucket limit for %s%s. Waiting %ds before retry (%d/3)...",
                        log_path,
                        id_str,
                        e.reset,
                        retry_count + 1,
                    )
                    await asyncio.sleep(e.reset + 1)
                    continue
                except RequestError as e:
                    log.warning("HTTPX error fetching %s%s: %s", log_path, id_str, e)
                    return None
                except Exception as e:  # pylint: disable=broad-except
                    log.error("Error fetching %s%s: %s", log_path, id_str, e)
                    return None

            log.error("Max retries (3) exceeded for %s%s", log_path, id_str)
            return None

        return wrapper

    return decorator
