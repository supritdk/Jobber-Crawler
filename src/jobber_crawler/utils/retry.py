import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

scrape_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectTimeout, httpx.ReadTimeout)),
    reraise=True,
)
