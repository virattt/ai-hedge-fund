"""Rate limiting configuration for data sources."""

# YFinance rate limiting settings
YFINANCE_CONFIG = {
    # Request delays (in seconds)
    "min_delay": 0.5,  # Minimum delay between requests
    "max_delay": 1.5,  # Maximum delay between requests
    "retry_min_delay": 2.0,  # Minimum delay for retries
    "retry_max_delay": 5.0,  # Maximum delay for retries

    # Retry settings
    "max_retries": 3,
    "exponential_backoff": True,

    # User agents for rotation
    "user_agents": [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0',
    ],

    # Request headers
    "headers": {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
    },
}

# AKShare rate limiting settings
AKSHARE_CONFIG = {
    "min_delay": 0.3,
    "max_delay": 1.0,
    "retry_min_delay": 1.5,
    "retry_max_delay": 3.0,
    "max_retries": 3,
    "exponential_backoff": True,
}
