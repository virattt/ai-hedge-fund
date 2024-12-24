import time
import requests


def make_request_with_retry(url, headers, max_retries=3):
    """
    Makes a GET request to the given URL with a retry mechanism
    if a 503 status code is encountered.

    Args:
        url (str): The URL to make the request to.
        headers (dict): The headers to send with the request.
        max_retries (int): The maximum number of retries (default is 3).

    Returns:
        response (requests.Response): The response object from the successful request.

    Raises:
        Exception: If the API is unavailable after multiple retries.
    """
    for attempt in range(max_retries):
        response = requests.get(url, headers=headers)
        if response.status_code == 503:
            print(f"Attempt {attempt + 1}: Server unavailable, retrying...")
            time.sleep(5)  # Wait before retrying
        else:
            return response
    raise Exception("API unavailable after multiple retries.")
