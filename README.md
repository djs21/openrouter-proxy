# OpenRouter Proxy

A simple proxy server for OpenRouter API that helps bypass rate limits on free API keys 
by rotating through multiple API keys in a round-robin fashion.

## Features

- **HTTP Compliance**: Full HTTP/1.1 spec compliance with proper chunked encoding
- **Performance Monitoring**: Response metrics via Prometheus at `/metrics`
- **Request Tracing**: Unique request IDs for end-to-end logging (X-Request-ID)
- **Health Checks**: Extended endpoint monitoring with `/health` endpoint
- **Key Validation**: Strict API key format enforcement ("sk-or-" prefix)
- **Response Caching**: Built-in caching for /models endpoint with TTL control
- **Streaming Support**: Optimized streaming responses with HTTP/1.1 compliance
- **Environment Support**: API keys can be set via OPENROUTER_KEYS environment variable
- **Production Ready**: Structured logging, performance tracking headers, and graceful shutdown

## Setup

1. Clone the repository
2. Create a virtual environment and install dependencies:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install --upgrade pip wheel setuptools
    pip install -r requirements.txt
    ```

    **Important Note:** Arch Linux and similar distributions manage Python packages through the system package manager. Never install Python packages system-wide! Always use a virtual environment as shown above.
3. Create a configuration file:
    ```
    cp config.yml.example config.yml
    ```
4. Edit `config.yml` to add your OpenRouter API keys and configure the server

## Configuration

The `config.yml` file supports these settings with new production-ready options:

```yaml
# Server settings
server:
  host: "0.0.0.0"  # Interface to bind to
  port: 5555       # Port to listen on
  access_key: "your_local_access_key_here"  # Authentication key
  log_level: "INFO"  # Logging level
  http_log_level: "INFO"  # HTTP access logs level

# OpenRouter API settings
openrouter:
  keys:
    - "sk-or-v1-example-api-key-1" # Keys must start with 'sk-or-'
    - "sk-or-v1-example-api-key-2"

  # Can also set via env: OPENROUTER_KEYS=key1,key2

  # Cache settings for free models endpoint
  enable_cache: true  # Enable response caching
  cache_ttl: 300     # Cache lifetime in seconds (5 minutes)

  # Key selection strategy: "round-robin" (default), "first" or "random".
  key_selection_strategy: "round-robin"
  # List of key selection options:
  #   "same": Always use the last used key as long as it is possible.
  key_selection_opts: []

  # OpenRouter API base URL
  base_url: "https://openrouter.ai/api/v1"

  # Public endpoints that don't require authentication
  public_endpoints:
    - "/api/v1/models"

  # Time in seconds to temporarily disable a key when rate limit is reached by default
  rate_limit_cooldown: 14400  # 4 hours
  free_only: false # try to show only free models
  # Google sometimes returns 429 RESOURCE_EXHAUSTED errors repeatedly, which can cause Roo Code to stop.
  # This prevents repeated failures by introducing a delay before retrying.
  # google_rate_delay: 10 # in sec
  google_rate_delay: 0

# Proxy settings for outgoing requests to OpenRouter
requestProxy:
  enabled: false  # Set to true to enable proxy
  url: "socks5://username:password@example.com:1080"  # Proxy URL with optional credentials embedded
```

```yaml
# Server settings
server:
  host: "0.0.0.0"  # Interface to bind to
  port: 5555       # Port to listen on
  access_key: "your_local_access_key_here"  # Authentication key
  log_level: "INFO"  # Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  http_log_level: "INFO"  # HTTP access logs level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

# OpenRouter API keys
openrouter:
  keys:
    - "sk-or-v1-your-first-api-key"
    - "sk-or-v1-your-second-api-key"
    - "sk-or-v1-your-third-api-key"

  # Key selection strategy: "round-robin" (default), "first" or "random".
  key_selection_strategy: "round-robin"
  # List of key selection options:
  #   "same": Always use the last used key as long as it is possible.
  key_selection_opts: []

  # OpenRouter API base URL
  base_url: "https://openrouter.ai/api/v1"

  # Public endpoints that don't require authentication
  public_endpoints:
    - "/api/v1/models"

  # Time in seconds to temporarily disable a key when rate limit is reached by default
  rate_limit_cooldown: 14400  # 4 hours
  free_only: false # try to show only free models
  # Google sometimes returns 429 RESOURCE_EXHAUSTED errors repeatedly, which can cause Roo Code to stop.
  # This prevents repeated failures by introducing a delay before retrying.
  # google_rate_delay: 10 # in sec
  google_rate_delay: 0

# Proxy settings for outgoing requests to OpenRouter
requestProxy:
  enabled: false    # Set to true to enable proxy
  url: "socks5://username:password@example.com:1080"  # Proxy URL with optional credentials embedded
```

## Usage

### Running Manually

Start the server:
```
python main.py
```

The proxy will be available at `http://localhost:5555/api/v1` (or the host/port configured in your config file).

### Installing as a Systemd Service

For Linux systems with systemd, you can install the proxy as a system service:

1. Make sure you've created and configured your `config.yml` file
2. Run the installation script:

```sudo ./service_install.sh``` or ```sudo ./service_install_venv.sh``` for venv.

This will create a systemd service that starts automatically on boot.

To check the service status:
```
sudo systemctl status openrouter-proxy
```

To view logs:
```
sudo journalctl -u openrouter-proxy -f
```

To uninstall the service:
```
sudo ./service_uninstall.sh
```

### Authentication

Add your local access key to requests:
```
Authorization: Bearer your_local_access_key_here
```

## API Endpoints

The proxy supports all OpenRouter API v1 endpoints through the following endpoint:

- `/api/v1/{path}` - Proxies all requests to OpenRouter API v1

It also provides a health check endpoint:

- `/health` - Health check endpoint that returns `{"status": "ok"}`
