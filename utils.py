#!/usr/bin/env python3
"""
Utility functions for OpenRouter API Proxy.
"""

import asyncio
import json
import socket
from typing import Optional, Tuple

from fastapi import Header, HTTPException

from config import config, logger
from constants import RATE_LIMIT_ERROR_CODE

def mask_key(key: str) -> str:
    """Mask an API key for logging purposes."""
    if not key:
        return key
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


def get_local_ip() -> str:
    """Get local IP address for displaying in logs."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception as e:
        logger.error("Failed to get local IP, using fallback", extra={"error": str(e)})
        return "127.0.0.1"


async def verify_access_key(
    authorization: Optional[str] = Header(None),
) -> bool:
    """
    Verify the local access key for authentication.

    Args:
        authorization: Authorization header

    Returns:
        True if authentication is successful

    Raises:
        HTTPException: If authentication fails
    """

    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authentication scheme")

    if token != config["server"]["access_key"]:
        raise HTTPException(status_code=401, detail="Invalid access key")

    return True


async def is_google_error(data: str) -> bool:
    # data = {
    #     'error': {
    #         'code': 429,
    #         'message': 'You exceeded your current quota, please check your plan and billing details.',
    #         'status': 'RESOURCE_EXHAUSTED',
    #         'details': [
    #             {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [
    #                 {'quotaMetric': 'generativelanguage.googleapis.com/generate_content_paid_tier_input_token_count',
    #                  'quotaId': 'GenerateContentPaidTierInputTokensPerModelPerMinute',
    #                  'quotaDimensions': {'model': 'gemini-2.0-pro-exp', 'location': 'global'},
    #                  'quotaValue': '10000000'}
    #             ]},
    #             {'@type': 'type.googleapis.com/google.rpc.Help', 'links': [
    #                 {'description': 'Learn more about Gemini API quotas',
    #                  'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}
    #             ]},
    #             {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '5s'}
    #         ]
    #     }
    # }
    if data:
        try:
            data = json.loads(data)
        except Exception as e:
            logger.info("Json.loads error %s", e)
        else:
            if data["error"].get("status", "") == "RESOURCE_EXHAUSTED":
                if config["openrouter"]["google_rate_delay"]:
                    # I think this is global rate limit, so 'retryDelay' is useless
                    # try:
                    #     retry_info = next(
                    #         (item for item in data['error']['details']
                    #          if item.get('@type') == 'type.googleapis.com/google.rpc.RetryInfo'), {}
                    #     )
                    #     retry_delay = retry_info['retryDelay']
                    #     retry_delay_s = int(''.join(c for c in retry_delay if c.isdigit()))
                    # except (TypeError, KeyError, ValueError) as _:
                    #     retry_delay_s = GOOGLE_DELAY
                    logger.info("Google returned RESOURCE_EXHAUSTED, wait %s sec",
                                config["openrouter"]["google_rate_delay"])
                    await asyncio.sleep(config["openrouter"]["google_rate_delay"])
                return True
    return False


async def check_rate_limit(data: str or bytes) -> Tuple[bool, Optional[int]]:
    """
    Check for rate limit error.

    Args:
        data: response line

    Returns:
        Tuple (has_rate_limit_error, reset_time_ms)
    """
    has_rate_limit_error = False
    reset_time_ms = None
    try:
        err = json.loads(data)
    except Exception as e:
        logger.warning('Json.loads error %s', e)
    else:
        if isinstance(err, dict) and "error" in err:
            code = err["error"].get("code", 0)
            try:
                x_rate_limit = int(err["error"]["metadata"]["headers"]["X-RateLimit-Reset"])
            except (TypeError, KeyError):
                if (code == RATE_LIMIT_ERROR_CODE and
                        await is_google_error(err["error"].get("metadata", {}).get("raw", ""))):
                    return False, None
                x_rate_limit = 0

            if x_rate_limit > 0:
                has_rate_limit_error = True
                reset_time_ms = x_rate_limit
            elif code == RATE_LIMIT_ERROR_CODE:
                has_rate_limit_error = True

    return has_rate_limit_error, reset_time_ms
