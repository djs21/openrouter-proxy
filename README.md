# OpenRouter Proxy

A simple proxy server for OpenRouter API that helps bypass rate limits on free API keys
by rotating through multiple API keys in a round-robin fashion.

## Features

- **HTTP Compliance**: Full HTTP/1.1 spec compliance with proper chunked encoding
- **Enhanced Metrics Dashboard**: Detailed monitoring at `/metrics` showing:
  - Token statistics (sent/received)
  - Model endpoint caching status
  - Key status (active/in cooldown)
  - System resource usage (CPU/Memory)
  - All standard Prometheus metrics
  - Raw metrics available at `/metrics/raw`
- **Request Tracing**: Unique request IDs for end-to-end logging (X-Request-ID)
- **Configurable Metrics**: Toggle system metrics and token counting in config
- **Health Checks**: Extended endpoint monitoring with `/health` endpoint
- **Key Validation**: Strict API key format enforcement ("sk-or-" prefix, invalid keys rejected at startup)
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

## Optional Dependencies

For system resource monitoring (CPU/Memory metrics), install psutil when needed:

```bash
pip install psutil
```

This is only required if you enable `enable_system_metrics: true` in config.yml

## Configuration

The `config.yml` file supports these settings with new production-ready options:

```yaml
# Server settings
server:
  host: "0.0.0.0" # Interface to bind to
  port: 5555 # Port to listen on
  access_key: "your_local_access_key_here" # Authentication key
  log_level: "INFO" # Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  http_log_level: "INFO" # HTTP access logs level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

# OpenRouter API settings
openrouter:
  keys:
    - "sk-or-v1-your-first-api-key"
    - "sk-or-v1-your-second-api-key"
    - "sk-or-v1-your-third-api-key"

  # Cache settings for free models endpoint
  enable_cache: true # Enable response caching
  cache_ttl: 300 # Cache lifetime in seconds (5 minutes)

  base_url: "https://openrouter.ai/api/v1" # OpenRouter API endpoint
  public_endpoints: ["/api/v1/models"] # No auth required

  # Key selection strategy: "round-robin" (default), "first" or "random".
  key_selection_strategy: "round-robin"
  # Options: ["same"] to prefer last used key
  key_selection_opts: []

  # When keys get rate limited
  rate_limit_cooldown: 14400 # 4 hours
  free_only: false # Only show free models
  google_rate_delay: 0 # Delay for Google API issues

# Outgoing proxy configuration
requestProxy:
  enabled: false # Enable to use proxy
  url: "socks5://user:pass@proxy.com:1080" # Proxy URL with credentials
```

## Usage

### Running Manually

To run the OpenRouter Proxy, you now need to start two separate services:

1.  **Key Management Service (KMS)**:
    This service manages API keys and rate limits.
    ```bash
    python key_management_service.py
    ```
    It will typically run on `http://localhost:5556` (configurable in `config.yml`).

2.  **OpenRouter API Gateway**:
    This is the main proxy endpoint that clients connect to.
    ```bash
    python main.py
    ```
    The API Gateway will be available at `http://localhost:5555/api/v1` (or the host/port configured in your config file).
    It communicates with the KMS internally.

### Installing as a Systemd Service

For Linux systems with systemd, you can install the proxy as a system service:

1. Make sure you've created and configured your `config.yml` file
2. Run the installation script:

`sudo ./service_install.sh` or `sudo ./service_install_venv.sh` for venv.

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

## Why

Forked from [Aculeasis openrouter-proxy](https://github.com/Aculeasis/openrouter-proxy). It is my attempt to fix :

1. Conflicting HTTP Headers.
   The http proxy is sending mutually exclusive headers simultaneously:

```
   Transfer-Encoding: chunked
   Content-Length: 407769
```

This violates HTTP/1.1 specification (RFC 7230 Section 3.3.3) which prohibits sending both headers together.

2. Duplicate Headers.
   Invalid duplicate headers appear in the http response:

```
   date: Fri, 13 Jun 2025 01:42:55 GMT
   date: Fri, 13 Jun 2025 01:42:56 GMT  # Duplicate!
   server: uvicorn
   server: cloudflare  # Duplicate!
```

Thus making it unusable in Big-AGI [big-AGI](https://github.com/enricoros/big-AGI).
