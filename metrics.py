#!/usr/bin/env python3
"""
Metrics definitions for OpenRouter API Proxy.
"""

import prometheus_client

TOKENS_SENT = prometheus_client.Counter('openrouter_tokens_sent_total', 'Total tokens sent to OpenRouter')
TOKENS_RECEIVED = prometheus_client.Counter('openrouter_tokens_received_total', 'Total tokens received from OpenRouter')
ACTIVE_KEYS = prometheus_client.Gauge('openrouter_active_keys', 'Number of active API keys')
COOLDOWN_KEYS = prometheus_client.Gauge('openrouter_keys_in_cooldown', 'Number of keys in cooldown')
CPU_USAGE = prometheus_client.Gauge('system_cpu_usage_percent', 'Current CPU usage percentage')
MEMORY_USAGE = prometheus_client.Gauge('system_memory_usage_percent', 'Current memory usage percentage')
