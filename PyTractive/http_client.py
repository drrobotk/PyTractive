"""
Enhanced HTTP client utilities for Tractive API communication with async support.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, Union, Callable
import requests
import aiohttp
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json

from .exceptions import APIError, AuthenticationError, ConfigurationError
from .config import TractiveConfig
from .utils import RateLimiter


logger = logging.getLogger(__name__)


class HTTPClient:
    """
    Enhanced synchronous HTTP client for Tractive API communication.
    
    Features:
    - Automatic retries with exponential backoff
    - Rate limiting
    - Request/response logging
    - Comprehensive error handling
    - Session persistence
    """
    
    def __init__(self, config: TractiveConfig):
        self.config = config
        self.session = self._create_session()
        self.rate_limiter = RateLimiter(calls_per_minute=config.api_rate_limit)
        self._request_count = 0
        self._start_time = time.time()
    
    def _create_session(self) -> requests.Session:
        """Create configured requests session with retries and adapters."""
        session = requests.Session()
        
        # Set headers
        session.headers.update({
            'User-Agent': self.config.user_agent,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Tractive-Client': self.config.client_id,
            'X-Tractive-Version': '2.0.0'
        })
        
        # Configure retries with exponential backoff
        retry_strategy = Retry(
            total=self.config.retry_attempts,
            backoff_factor=self.config.retry_backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"],
            raise_on_redirect=False,
            raise_on_status=False  # We'll handle status codes manually
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=self.config.connection_pool_size,
            pool_maxsize=self.config.connection_pool_maxsize
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def set_auth_token(self, token: str) -> None:
        """Set authorization token for requests."""
        if not token or not token.strip():
            raise ValueError("Invalid token provided")
        self.session.headers['Authorization'] = f'Bearer {token.strip()}'
        logger.debug("Authorization token set")
    
    def clear_auth_token(self) -> None:
        """Clear authorization token."""
        self.session.headers.pop('Authorization', None)
        logger.debug("Authorization token cleared")
    
    def request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make HTTP request with comprehensive error handling and rate limiting.
        
        Args:
            method: HTTP method
            url: Request URL
            data: JSON data for request body
            params: URL parameters
            headers: Additional headers
            timeout: Request timeout (overrides config)
            **kwargs: Additional arguments for requests
            
        Returns:
            Parsed JSON response data
            
        Raises:
            APIError: For API-related errors
            AuthenticationError: For authentication failures
            ConfigurationError: For configuration issues
        """
        # Apply rate limiting
        self.rate_limiter.wait_if_needed()
        
        # Prepare request
        request_timeout = timeout or self.config.request_timeout
        request_headers = self.session.headers.copy()
        if headers:
            request_headers.update(headers)
        
        # Track request metrics
        self._request_count += 1
        start_time = time.time()
        
        try:
            logger.debug(f"Making {method} request to {url}")
            
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=request_headers,
                timeout=request_timeout,
                **kwargs
            )
            
            request_duration = time.time() - start_time
            logger.debug(f"{method} {url} -> {response.status_code} ({request_duration:.3f}s)")
            
            # Handle response
            return self._handle_response(response, method, url)
            
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout after {request_timeout}s: {method} {url}")
            raise APIError(f"Request timeout after {request_timeout}s")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise APIError(f"Connection error: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise APIError(f"Request failed: {e}")
    
    def _handle_response(
        self, 
        response: requests.Response, 
        method: str, 
        url: str
    ) -> Dict[str, Any]:
        """Handle HTTP response with detailed error processing."""
        
        # Handle authentication errors
        if response.status_code == 401:
            logger.warning("Authentication failed - token may be expired")
            raise AuthenticationError("Invalid or expired access token")
        
        # Handle rate limiting
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After', '60')
            try:
                wait_time = int(retry_after)
            except ValueError:
                wait_time = 60
            
            logger.warning(f"Rate limited - waiting {wait_time}s")
            raise APIError(f"Rate limited - retry after {wait_time}s", status_code=429)
        
        # Handle other client/server errors
        if not response.ok:
            error_msg = f"HTTP {response.status_code}: {response.reason}"
            error_details = None
            
            try:
                error_data = response.json()
                if isinstance(error_data, dict):
                    error_msg = error_data.get('message', error_msg)
                    error_details = error_data.get('details')
            except (json.JSONDecodeError, ValueError):
                # Try to get text content for error details
                if response.text:
                    error_details = response.text[:500]  # Limit error text
            
            logger.error(f"API error: {error_msg} (URL: {url})")
            raise APIError(
                message=error_msg,
                status_code=response.status_code,
                response_data=error_details
            )
        
        # Handle successful responses
        if not response.content:
            return {}
        
        try:
            return response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            raise APIError(f"Invalid JSON response: {e}")
    
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
    def request_stats(self) -> Dict[str, Any]:
        """Get request statistics."""
        runtime = time.time() - self._start_time
        return {
            'total_requests': self._request_count,
            'runtime_seconds': runtime,
            'requests_per_minute': (self._request_count / runtime) * 60 if runtime > 0 else 0
        }
    
    def close(self) -> None:
        """Close the session and log statistics."""
        stats = self.request_stats
        logger.info(f"HTTP client closing: {stats['total_requests']} requests in {stats['runtime_seconds']:.1f}s")
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class AsyncHTTPClient:
    """
    Asynchronous HTTP client for Tractive API communication.
    
    Features:
    - High-performance async/await support
    - Connection pooling and session management
    - Automatic retries and error handling
    - Rate limiting
    """
    
    def __init__(self, config: TractiveConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limiter = RateLimiter(calls_per_minute=config.api_rate_limit)
        self._request_count = 0
        self._start_time = time.time()
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.request_timeout)
            connector = aiohttp.TCPConnector(
                limit=self.config.connection_pool_size,
                limit_per_host=self.config.connection_pool_maxsize
            )
            
            headers = {
                'User-Agent': self.config.user_agent,
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Tractive-Client': self.config.client_id,
                'X-Tractive-Version': '2.0.0'
            }
            
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers=headers
            )
        
        return self.session
    
    def set_auth_token(self, token: str) -> None:
        """Set authorization token for requests."""
        if not token or not token.strip():
            raise ValueError("Invalid token provided")
        
        # Store token for when session is created/recreated
        self._auth_token = f'Bearer {token.strip()}'
        
        # Update existing session if available
        if self.session and not self.session.closed:
            self.session.headers['Authorization'] = self._auth_token
    
    async def request(
        self,
        method: str,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make async HTTP request with error handling.
        
        Args:
            method: HTTP method
            url: Request URL  
            data: JSON data for request body
            params: URL parameters
            headers: Additional headers
            **kwargs: Additional arguments for aiohttp
            
        Returns:
            Parsed JSON response data
        """
        # Apply rate limiting
        self.rate_limiter.wait_if_needed()
        
        session = await self._get_session()
        
        # Add auth token if available
        request_headers = {}
        if hasattr(self, '_auth_token'):
            request_headers['Authorization'] = self._auth_token
        
        if headers:
            request_headers.update(headers)
        
        self._request_count += 1
        start_time = time.time()
        
        try:
            logger.debug(f"Making async {method} request to {url}")
            
            async with session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=request_headers,
                **kwargs
            ) as response:
                
                request_duration = time.time() - start_time
                logger.debug(f"Async {method} {url} -> {response.status} ({request_duration:.3f}s)")
                
                return await self._handle_response(response, method, url)
                
        except asyncio.TimeoutError:
            logger.error(f"Async request timeout: {method} {url}")
            raise APIError("Request timeout")
        except aiohttp.ClientError as e:
            logger.error(f"Async request failed: {e}")
            raise APIError(f"Request failed: {e}")
    
    async def _handle_response(
        self, 
        response: aiohttp.ClientResponse, 
        method: str, 
        url: str
    ) -> Dict[str, Any]:
        """Handle async HTTP response."""
        
        if response.status == 401:
            logger.warning("Async authentication failed")
            raise AuthenticationError("Invalid or expired access token")
        
        if response.status == 429:
            retry_after = response.headers.get('Retry-After', '60')
            logger.warning(f"Async rate limited - retry after {retry_after}s")
            raise APIError(f"Rate limited - retry after {retry_after}s", status_code=429)
        
        if not (200 <= response.status < 300):
            error_msg = f"HTTP {response.status}: {response.reason}"
            try:
                error_data = await response.json()
                if isinstance(error_data, dict):
                    error_msg = error_data.get('message', error_msg)
            except (aiohttp.ContentTypeError, json.JSONDecodeError):
                pass
            
            logger.error(f"Async API error: {error_msg}")
            raise APIError(
                message=error_msg,
                status_code=response.status,
                response_data=await response.text()
            )
        
        if response.content_length == 0:
            return {}
        
        try:
            return await response.json()
        except (aiohttp.ContentTypeError, json.JSONDecodeError) as e:
            logger.error(f"Invalid async JSON response: {e}")
            raise APIError(f"Invalid JSON response: {e}")
    
    async def get(self, url: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Make async GET request."""
        return await self.request("GET", url, params=params, **kwargs)
    
    async def post(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Make async POST request."""
        return await self.request("POST", url, data=data, **kwargs)
    
    async def put(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Make async PUT request."""
        return await self.request("PUT", url, data=data, **kwargs)
    
    async def delete(self, url: str, **kwargs) -> Dict[str, Any]:
        """Make async DELETE request."""
        return await self.request("DELETE", url, **kwargs)
    
    @property
    def request_stats(self) -> Dict[str, Any]:
        """Get request statistics."""
        runtime = time.time() - self._start_time
        return {
            'total_requests': self._request_count,
            'runtime_seconds': runtime,
            'requests_per_minute': (self._request_count / runtime) * 60 if runtime > 0 else 0
        }
    
    async def close(self) -> None:
        """Close the async session."""
        if self.session and not self.session.closed:
            stats = self.request_stats
            logger.info(f"Async HTTP client closing: {stats['total_requests']} requests in {stats['runtime_seconds']:.1f}s")
            await self.session.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
