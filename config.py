#!/usr/bin/env python3
"""
Configuration module for OpenRouter API Proxy.
Loads settings from a YAML file and initializes logging with Pydantic validation.
"""

import os
import sys
import logging
from typing import Dict, Any, List, Optional

import yaml
from pydantic import BaseModel, ValidationError

CONFIG_FILE = "config.yml"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 5555
    access_key: str
    log_level: str = "INFO"
    http_log_level: str = "INFO"


class OpenRouterConfig(BaseModel):
    keys: List[str] = []
    base_url: str = "https://openrouter.ai/api/v1"
    public_endpoints: List[str] = ["/api/v1/models"]
    rate_limit_cooldown: int = 14400
    key_selection_strategy: str = "round-robin"
    key_selection_opts: List[str] = []
    free_only: bool = False
    google_rate_delay: int = 0


class RequestProxyConfig(BaseModel):
    enabled: bool = False
    url: Optional[str] = None


def load_config() -> Dict[str, Any]:
    """Load and validate configuration with Pydantic models."""
    try:
        with open(CONFIG_FILE, encoding="utf-8") as file:
            config_data = yaml.safe_load(file) or {}
        
        # Environment variable override for API keys
        if "OPENROUTER_KEYS" in os.environ:
            env_keys = os.environ["OPENROUTER_KEYS"].split(",")
            config_data.setdefault("openrouter", {})["keys"] = env_keys
        
        # Validate each configuration section
        config_data["server"] = ServerConfig(**config_data.get("server", {})).dict()
        config_data["openrouter"] = OpenRouterConfig(**config_data.get("openrouter", {})).dict()
        config_data["requestProxy"] = RequestProxyConfig(**config_data.get("requestProxy", {})).dict()
        
        return config_data
    except FileNotFoundError:
        print(f"Configuration file {CONFIG_FILE} not found. "
              "Please create it based on config.yml.example.")
        sys.exit(1)
    except (yaml.YAMLError, ValidationError) as e:
        print(f"Error in configuration: {e}")
        sys.exit(1)


def setup_logging(config_: Dict[str, Any]) -> logging.Logger:
    """Configure logging based on validated configuration."""
    log_level = config_["server"]["log_level"]
    log_level_int = getattr(logging, log_level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level_int,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    logger_ = logging.getLogger("openrouter-proxy")
    logger_.info("Logging level set to %s", log_level)
    return logger_


# Load and validate configuration once at startup
config = load_config()
logger = setup_logging(config)

# Ensure extra fields are allowed (for forward compatibility with config.yml)
ServerConfig.Config.extra = "allow"
OpenRouterConfig.Config.extra = "allow"
RequestProxyConfig.Config.extra = "allow"

# Clear the config after any previous runs
config = None
logger = None
