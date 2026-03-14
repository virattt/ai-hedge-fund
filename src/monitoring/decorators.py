"""Decorators for monitoring data source operations."""

from functools import wraps
import time
import logging
from .metrics import metrics_collector


logger = logging.getLogger(__name__)


def monitor_request(source_name: str):
    """Decorator to monitor data source requests.

    This decorator automatically tracks request success/failure and latency
    for any function that fetches data from a source.

    Args:
        source_name: Name of the data source being monitored

    Returns:
        Decorated function

    Example:
        >>> from src.monitoring.decorators import monitor_request
        >>>
        >>> class MyDataSource:
        ...     @monitor_request("MyDataSource")
        ...     def get_prices(self, ticker, start_date, end_date):
        ...         # Fetch data logic here
        ...         return data
        >>>
        >>> # Metrics are automatically collected
        >>> source = MyDataSource()
        >>> data = source.get_prices("AAPL", "2024-01-01", "2024-01-02")
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = False

            try:
                result = func(*args, **kwargs)
                success = True
                return result

            except Exception as e:
                logger.error(f"{source_name}.{func.__name__} failed: {e}")
                raise

            finally:
                latency = (time.time() - start_time) * 1000  # Convert to ms
                metrics_collector.record_request(source_name, success, latency)

                if success:
                    logger.debug(
                        f"{source_name}.{func.__name__} completed successfully "
                        f"in {latency:.2f}ms"
                    )

        return wrapper
    return decorator


def monitor_class_methods(source_name: str = None):
    """Class decorator to monitor all public methods.

    This decorator automatically applies monitoring to all public methods
    of a class (methods not starting with underscore).

    Args:
        source_name: Name of the data source (uses class name if None)

    Returns:
        Decorated class

    Example:
        >>> from src.monitoring.decorators import monitor_class_methods
        >>>
        >>> @monitor_class_methods()
        ... class MyDataSource:
        ...     def get_prices(self, ticker, start_date, end_date):
        ...         return []
        ...
        ...     def get_metrics(self, ticker):
        ...         return {}
        >>>
        >>> # All methods are automatically monitored
        >>> source = MyDataSource()
    """
    def decorator(cls):
        # Use class name if source_name not provided
        name = source_name or cls.__name__

        # Get all public methods
        for attr_name in dir(cls):
            # Skip private/protected methods and special methods
            if attr_name.startswith('_'):
                continue

            attr = getattr(cls, attr_name)

            # Only decorate callable methods
            if callable(attr):
                # Apply monitoring decorator
                monitored_method = monitor_request(name)(attr)
                setattr(cls, attr_name, monitored_method)

        return cls

    return decorator


def conditional_monitor(condition_func):
    """Decorator that conditionally monitors based on a function.

    This decorator only records metrics if the condition function returns True.
    Useful for monitoring only specific types of requests.

    Args:
        condition_func: Function that takes the same arguments as the decorated
                       function and returns True/False

    Returns:
        Decorated function

    Example:
        >>> def should_monitor(ticker, *args, **kwargs):
        ...     # Only monitor for specific tickers
        ...     return ticker in ["AAPL", "GOOGL"]
        >>>
        >>> class MyDataSource:
        ...     @conditional_monitor(should_monitor)
        ...     @monitor_request("MyDataSource")
        ...     def get_prices(self, ticker, start_date, end_date):
        ...         return []
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Check if we should monitor this call
            if condition_func(*args, **kwargs):
                return func(*args, **kwargs)
            else:
                # Execute without monitoring
                original_func = func.__wrapped__ if hasattr(func, '__wrapped__') else func
                return original_func(*args, **kwargs)

        return wrapper
    return decorator


def retry_with_monitoring(source_name: str, max_retries: int = 3, backoff_factor: float = 1.0):
    """Decorator that retries failed requests and monitors each attempt.

    Args:
        source_name: Name of the data source
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff (seconds)

    Returns:
        Decorated function

    Example:
        >>> @retry_with_monitoring("MyDataSource", max_retries=3, backoff_factor=2.0)
        ... def get_prices(ticker, start_date, end_date):
        ...     # Fetch data logic that might fail
        ...     return data
        >>>
        >>> # Will retry up to 3 times with exponential backoff
        >>> data = get_prices("AAPL", "2024-01-01", "2024-01-02")
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                start_time = time.time()
                success = False

                try:
                    result = func(*args, **kwargs)
                    success = True
                    latency = (time.time() - start_time) * 1000
                    metrics_collector.record_request(source_name, success, latency)
                    return result

                except Exception as e:
                    last_exception = e
                    latency = (time.time() - start_time) * 1000
                    metrics_collector.record_request(source_name, success, latency)

                    if attempt < max_retries:
                        sleep_time = backoff_factor * (2 ** attempt)
                        logger.warning(
                            f"{source_name}.{func.__name__} attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {sleep_time}s..."
                        )
                        time.sleep(sleep_time)
                    else:
                        logger.error(
                            f"{source_name}.{func.__name__} failed after {max_retries + 1} attempts"
                        )

            # All retries exhausted
            raise last_exception

        return wrapper
    return decorator
