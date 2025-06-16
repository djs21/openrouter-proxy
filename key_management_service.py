#!/usr/bin/env python3
"""
Key Management Service (KMS) for OpenRouter API Proxy.
Manages API key rotation and rate limit handling as a separate service.
"""

import asyncio
import sys
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationError
from fastapi.responses import Response
import prometheus_client
import httpx
import uvicorn

from config import config, logger
from utils import mask_key

# Initialize FastAPI app for KMS
app = FastAPI(
    title="Key Management Service",
    description="Manages OpenRouter API keys and rate limits.",
    version="1.0.0",
)

# Initialize KeyManager instance
key_manager = None

class KeyManager:
    """Manages OpenRouter API keys, including rotation and rate limit handling."""
    def __init__(self, keys: List[str], cooldown_seconds: int, strategy: str, opts: list[str]):
        self.keys = keys
        self.cooldown_seconds = cooldown_seconds
        self.current_index = 0
        self.disabled_until: Dict[str, datetime] = {}
        self.strategy = strategy
        self.use_last_key = "same" in opts
        self.last_key = None
        self.lock = asyncio.Lock()
        self.update_metrics()

    def update_metrics(self):
        """Update Prometheus metrics for keys"""
        now_ = datetime.now()
        active_keys = [k for k in self.keys if k not in self.disabled_until or self.disabled_until[k] <= now_]
        cooldown_keys = [k for k in self.keys if k in self.disabled_until and self.disabled_until[k] > now_]
        ACTIVE_KEYS.set(len(active_keys))
        COOLDOWN_KEYS.set(len(cooldown_keys))

    async def get_next_key(self) -> str:
        """Get the next available API key using round-robin selection."""
        async with self.lock:
            now_ = datetime.now()
            available_keys = set()
            expired_keys = []
            for key in self.keys:
                if key in self.disabled_until:
                    if now_ >= self.disabled_until[key]:
                        expired_keys.append(key)
                    else:
                        continue
                available_keys.add(key)
                
            for key in expired_keys:
                if key in self.disabled_until:
                    del self.disabled_until[key]
                    logger.info("API key %s is now enabled again.", mask_key(key))

            if not available_keys:
                soonest_available = min(self.disabled_until.values())
                wait_seconds = (soonest_available - now_).total_seconds()
                logger.error(
                    "All API keys are currently disabled. The next key will be available in %.2f seconds.", 
                    wait_seconds,
                )
                raise HTTPException(
                    status_code=503,
                    detail="All API keys are currently disabled due to rate limits. Please try again later."
                )

            if self.use_last_key and self.last_key in available_keys:
                selected_key = self.last_key
            elif self.strategy == "round-robin":
                for _ in range(len(self.keys)):
                    key = self.keys[self.current_index]
                    self.current_index = (self.current_index + 1) % len(self.keys)
                    if key in available_keys:
                        selected_key = key
                        break
            elif self.strategy == "first":
                selected_key = next(iter(available_keys))
            elif self.strategy == "random":
                selected_key = random.choice(list(available_keys))
            else:
                raise RuntimeError(f"Unknown key selection strategy: {self.strategy}")
            self.last_key = selected_key
            self.update_metrics()
            return selected_key

    async def disable_key(self, key: str, reset_time_ms: Optional[int] = None):
        """
        Disable a key until reset time or for the configured cooldown period.

        Args:
            key: The API key to disable
            reset_time_ms: Optional reset time in milliseconds since epoch. If provided,
                           the key will be disabled until this time. Otherwise, the default
                           cooldown period will be used.
        """
        async with self.lock:
            now_ = datetime.now()
            if reset_time_ms:
                try:
                    reset_datetime = datetime.fromtimestamp(reset_time_ms / 1000)
                    if reset_datetime > now_:
                        disabled_until = reset_datetime
                        logger.info("Using server-provided reset time: %s", str(disabled_until))
                    else:
                        disabled_until = now_ + timedelta(seconds=self.cooldown_seconds)
                        logger.warning(
                            "Server-provided reset time is in the past, using default cooldown of %s seconds", self.cooldown_seconds)
                except Exception as e:
                    disabled_until = now_ + timedelta(seconds=self.cooldown_seconds)
                    logger.error(
                        "Error processing reset time %s, using default cooldown: %s", reset_time_ms, e)
            else:
                disabled_until = now_ + timedelta(seconds=self.cooldown_seconds)
                logger.info(
                    "No reset time provided, using default cooldown of %s seconds", self.cooldown_seconds)

            self.disabled_until[key] = disabled_until
            self.update_metrics()
            logger.warning(
                "API key %s has been disabled until %s.", mask_key(key), disabled_until)

# Pydantic model for disable_key request body
class DisableKeyRequest(BaseModel):
    key: str
    reset_time_ms: Optional[int] = None

# Prometheus metrics for KMS
ACTIVE_KEYS = prometheus_client.Gauge('kms_active_keys', 'Number of active API keys in KMS')
COOLDOWN_KEYS = prometheus_client.Gauge('kms_cooldown_keys', 'Number of keys in cooldown in KMS')

@app.on_event("startup")
async def startup_event():
    global key_manager
    keys = config["openrouter"]["keys"]
    if not keys:
        logger.error("No API keys provided in configuration for KMS.")
        sys.exit(1)
    key_manager = KeyManager(
        keys=keys,
        cooldown_seconds=config["openrouter"]["rate_limit_cooldown"],
        strategy=config["openrouter"]["key_selection_strategy"],
        opts=config["openrouter"]["key_selection_opts"],
    )
    logger.info("KMS initialized with %d keys.", len(keys))

@app.get("/get_next_key")
async def get_next_key_endpoint():
    """API endpoint to get the next available API key."""
    try:
        key = await key_manager.get_next_key()
        return {"key": key}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error("Internal KMS error: %s", str(e))
        raise HTTPException(500, "Internal Key Management Service error")

@app.post("/disable_key")
async def disable_key_endpoint(request: DisableKeyRequest):
    """API endpoint to disable an API key."""
    await key_manager.disable_key(request.key, request.reset_time_ms)
    return {"status": "ok"}

@app.get("/metrics")
async def metrics_endpoint():
    """Exposes Prometheus metrics for KMS."""
    if key_manager:
        key_manager.update_metrics()
    return Response(
        content=prometheus_client.generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

CONTENT_TYPE_LATEST = 'text/plain; version=0.0.4; charset=utf-8'

