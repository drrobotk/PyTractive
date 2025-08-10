"""
Simple requests-based HTTP client for Tractive API communication.

This is a lightweight alternative to the main http_client.py that focuses 
on simplicity and easy customization using only the requests library.
"""

import logging
import time
from typing import Dict, Any, Optional
import requests
import json

from .exceptions import APIError, AuthenticationError


logger = logging.getLogger(__name__)


class SimpleHTTPClient:
    """
    Simple HTTP client using only requests library.
    
    Features:
    - Basic request/response handling
    - Simple error handling
    - Authentication token management
    - Request logging
    - Easy to understand and modify
    """
    
    def __init__(self, timeout: int = 30, retries: int = 3):
        """
        Initialize simple HTTP client.
        
        Args:
            timeout: Request timeout in seconds
            retries: Number of retry attempts
        """
        self.timeout = timeout
        self.retries = retries
        self.auth_token: Optional[str] = None
        self.request_count = 0
        self.start_time = time.time()
        
        # Create session for connection reuse
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PyTractive-Simple/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    def set_auth_token(self, token: str) -> None:
        """Set authorization token for API requests."""
        if not token or not token.strip():
            raise ValueError("Invalid token provided")
        
        self.auth_token = token.strip()
        self.session.headers['Authorization'] = f'Bearer {self.auth_token}'
        logger.debug("Authorization token set")
    
    def clear_auth_token(self) -> None:
        """Clear authorization token."""
        self.auth_token = None
        self.session.headers.pop('Authorization', None)
        logger.debug("Authorization token cleared")
    
    def request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with basic retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            data: JSON data for request body
            params: URL query parameters
            headers: Additional headers
            
        Returns:
            Parsed JSON response
            
        Raises:
            APIError: For API-related errors
            AuthenticationError: For authentication failures
        """
        self.request_count += 1
        
        # Prepare request
        request_headers = self.session.headers.copy()
        if headers:
            request_headers.update(headers)
        
        # Retry logic
        last_exception = None
        for attempt in range(1, self.retries + 1):
            try:
                logger.debug(f"Making {method} request to {url} (attempt {attempt}/{self.retries})")
                
                response = self.session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    headers=request_headers,
                    timeout=self.timeout
                )
                
                return self._handle_response(response, method, url)
                
            except requests.exceptions.Timeout:
                last_exception = APIError(f"Request timeout after {self.timeout}s")
                if attempt == self.retries:
                    logger.error(f"Final timeout on attempt {attempt}: {method} {url}")
                    raise last_exception
                else:
                    logger.warning(f"Timeout on attempt {attempt}, retrying: {method} {url}")
                    time.sleep(1)  # Simple backoff
            
            except requests.exceptions.ConnectionError as e:
                last_exception = APIError(f"Connection error: {e}")
                if attempt == self.retries:
                    logger.error(f"Final connection error on attempt {attempt}: {e}")
                    raise last_exception
                else:
                    logger.warning(f"Connection error on attempt {attempt}, retrying: {e}")
                    time.sleep(2)  # Longer wait for connection issues
            
            except requests.exceptions.RequestException as e:
                # Don't retry other request exceptions
                logger.error(f"Request failed: {e}")
                raise APIError(f"Request failed: {e}")
        
        # Should not reach here, but just in case
        raise last_exception or APIError("Request failed after all retries")
    
    def _handle_response(
        self, 
        response: requests.Response, 
        method: str, 
        url: str
    ) -> Dict[str, Any]:
        """
        Handle HTTP response and check for errors.
        
        Args:
            response: requests Response object
            method: HTTP method used
            url: Request URL
            
        Returns:
            Parsed JSON response data
            
        Raises:
            AuthenticationError: For 401 responses
            APIError: For other HTTP errors
        """
        logger.debug(f"{method} {url} -> {response.status_code}")
        
        # Check for authentication errors
        if response.status_code == 401:
            logger.warning("Authentication failed - invalid or expired token")
            raise AuthenticationError("Invalid or expired access token")
        
        # Check for rate limiting
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After', '60')
            logger.warning(f"Rate limited - should wait {retry_after}s")
            raise APIError(f"Rate limited - retry after {retry_after}s")
        
        # Check for other HTTP errors
        if not response.ok:
            error_message = f"HTTP {response.status_code}: {response.reason}"
            
            # Try to get error details from response
            try:
                error_data = response.json()
                if isinstance(error_data, dict) and 'message' in error_data:
                    error_message = error_data['message']
            except (json.JSONDecodeError, ValueError):
                # If we can't parse JSON, try to get text
                if response.text:
                    error_message += f" - {response.text[:200]}"
            
            logger.error(f"API error: {error_message}")
            raise APIError(error_message, status_code=response.status_code)
        
        # Handle successful responses
        if not response.content:
            return {}
        
        try:
            return response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            raise APIError(f"Invalid JSON response from server")
    
    def get(self, url: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Make GET request."""
        return self.request("GET", url, params=params, **kwargs)
    
    def post(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Make POST request."""
        return self.request("POST", url, data=data, **kwargs)
    
    def put(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Make PUT request."""
        return self.request("PUT", url, data=data, **kwargs)
    
    def delete(self, url: str, **kwargs) -> Dict[str, Any]:
        """Make DELETE request."""
        return self.request("DELETE", url, **kwargs)
    
    def patch(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Make PATCH request."""
        return self.request("PATCH", url, data=data, **kwargs)
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get simple request statistics."""
        runtime = time.time() - self.start_time
        return {
            'requests_made': self.request_count,
            'runtime_seconds': runtime,
            'avg_requests_per_minute': (self.request_count / runtime * 60) if runtime > 0 else 0
        }
    
    def close(self) -> None:
        """Close the HTTP session."""
        stats = self.stats
        logger.info(f"Simple HTTP client closing: {stats['requests_made']} requests in {stats['runtime_seconds']:.1f}s")
        self.session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class RequestsResponseLogger:
    """
    Helper class to log requests and responses in detail.
    Useful for debugging API interactions.
    """
    
    def __init__(self, client: SimpleHTTPClient, log_bodies: bool = True):
        """
        Initialize response logger.
        
        Args:
            client: HTTP client to wrap
            log_bodies: Whether to log request/response bodies
        """
        self.client = client
        self.log_bodies = log_bodies
        self.original_request = client.request
        
        # Wrap the request method
        client.request = self._logged_request
    
    def _logged_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Logged version of HTTP request."""
        # Log request
        logger.info(f"→ {method} {url}")
        
        if self.log_bodies:
            if 'data' in kwargs and kwargs['data']:
                logger.debug(f"Request body: {json.dumps(kwargs['data'], indent=2)}")
            if 'params' in kwargs and kwargs['params']:
                logger.debug(f"Request params: {kwargs['params']}")
        
        start_time = time.time()
        
        try:
            response = self.original_request(method, url, **kwargs)
            duration = time.time() - start_time
            
            # Log successful response
            logger.info(f"← {method} {url} -> SUCCESS ({duration:.3f}s)")
            
            if self.log_bodies and response:
                logger.debug(f"Response body: {json.dumps(response, indent=2)}")
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"← {method} {url} -> ERROR ({duration:.3f}s): {e}")
            raise


# Convenience functions for quick usage
def simple_get(url: str, auth_token: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Simple GET request function.
    
    Args:
        url: Request URL
        auth_token: Optional authorization token
        **kwargs: Additional arguments for request
        
    Returns:
        Parsed JSON response
    """
    with SimpleHTTPClient() as client:
        if auth_token:
            client.set_auth_token(auth_token)
        return client.get(url, **kwargs)


def simple_post(url: str, data: Optional[Dict[str, Any]] = None, auth_token: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Simple POST request function.
    
    Args:
        url: Request URL
        data: JSON data for request body
        auth_token: Optional authorization token
        **kwargs: Additional arguments for request
        
    Returns:
        Parsed JSON response
    """
    with SimpleHTTPClient() as client:
        if auth_token:
            client.set_auth_token(auth_token)
        return client.post(url, data=data, **kwargs)


# Example usage
if __name__ == "__main__":
    # Basic usage
    client = SimpleHTTPClient(timeout=30, retries=3)
    
    # Set authentication
    client.set_auth_token("your_api_token_here")
    
    try:
        # Make requests
        response = client.get("https://api.tractive.com/3/user")
        print(f"User data: {response}")
        
        # Check stats
        print(f"Request stats: {client.stats}")
        
    finally:
        client.close()
    
    # With logging
    logging.basicConfig(level=logging.DEBUG)
    with SimpleHTTPClient() as logged_client:
        logger_wrapper = RequestsResponseLogger(logged_client, log_bodies=True)
        logged_client.set_auth_token("your_token")
        
        response = logged_client.get("https://api.tractive.com/3/user")
