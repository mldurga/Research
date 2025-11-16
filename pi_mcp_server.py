#!/usr/bin/env python3
"""
AVEVA PI System MCP Server (Improved Version)

This MCP server provides integration with AVEVA PI System through PI WebAPI,
exposing resources, tools, and prompts for interacting with PI data and AF objects.

Key Improvements:
- Non-blocking initialization to prevent MCP timeouts
- Better error handling and retry mechanisms
- Optimized session management
- Background indexing with proper async handling
- Progress reporting and health monitoring
"""

import asyncio
import json
import logging
import os
import base64
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote, urljoin
import ssl
from config import config

import threading
import weakref
import pandas as pd
import numpy as np
from prophet import Prophet
import warnings

import aiohttp
from fastmcp import FastMCP
from mcp.types import Resource, Tool, TextResourceContents
from vector_db import vector_db

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, use environment variables directly
    pass

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Enable aiohttp debug logging only for DEBUG level
if log_level == "DEBUG":
    aiohttp_logger = logging.getLogger('aiohttp')
    aiohttp_logger.setLevel(logging.DEBUG)

# Initialize MCP server
mcp = FastMCP("AVEVA PI System")

# Global server state for health monitoring
server_state = {
    "initialization_complete": False,
    "indexing_in_progress": False,
    "last_error": None,
    "startup_time": datetime.now(),
    "indexed_elements_count": 0,
    "last_health_check": None
}

class PIWebAPIClient:
    """Client for AVEVA PI WebAPI interactions with improved error handling and session management"""
    
    def __init__(self, base_url: str, username: str = None, password: str = None, 
                 verify_ssl: bool = True, auth_method: str = "negotiate"):
        """
        Initialize PI WebAPI client
        
        Args:
            base_url: Base URL for PI WebAPI (e.g., https://server/piwebapi)
            username: Username for authentication (optional for Windows auth)
            password: Password for authentication (optional for Windows auth)
            verify_ssl: Whether to verify SSL certificates
            auth_method: Authentication method ('negotiate', 'basic', 'bearer')
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.auth_method = auth_method.lower()
        self._session = None
        self._session_loop = None
        self._lock = None
        self._connection_tested = False  # Track if connection has been tested
        
    async def _get_lock(self):
        """Get or create async lock for current event loop"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock
        
    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure we have a valid session for the current event loop"""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            raise Exception("No event loop running")
        
        # Check if we need to create/recreate the session
        if (self._session is None or 
            self._session.closed or 
            self._session_loop != current_loop):
            
            # Close old session if it exists and is from a different loop
            if self._session and not self._session.closed:
                try:
                    await self._session.close()
                except Exception as e:
                    logger.debug(f"Error closing old session: {e}")
            
            # Create new session for current loop
            self._session = await self._create_session()
            self._session_loop = current_loop
            
        return self._session
    
    async def _create_session(self) -> aiohttp.ClientSession:
        """Create a new HTTP session with appropriate authentication"""
        # Create SSL context based on verification setting
        if self.verify_ssl:
            ssl_context = ssl.create_default_context()
        else:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
        connector = aiohttp.TCPConnector(
            ssl=ssl_context,
            limit=100,  # Connection pool limit
            limit_per_host=30,  # Per-host limit
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        # Setup authentication
        auth = None
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "AVEVA-PI-MCP-Server/1.0"
        }
        
        if self.auth_method == "basic" and self.username and self.password:
            auth = aiohttp.BasicAuth(self.username, self.password)
        elif self.auth_method == "negotiate":
            # For Kerberos/Negotiate authentication, we rely on the system
            headers["Authorization"] = "Negotiate"
        
        # Add CSRF protection header for write operations
        headers["X-Requested-With"] = "XMLHttpRequest"
        
        session = aiohttp.ClientSession(
            connector=connector,
            auth=auth,
            headers=headers,
            timeout=aiohttp.ClientTimeout(
                total=60,  # Increased from 30
                connect=10,
                sock_read=30
            )
        )
        
        logger.debug(f"Created new aiohttp session for loop {id(asyncio.get_running_loop())}")
        return session
    
    async def test_connection(self) -> bool:
        """Test connection to PI Web API"""
        try:
            logger.info("Testing connection to PI WebAPI...")
            result = await self._make_request("GET", "/system")
            self._connection_tested = True
            logger.info("✅ Successfully connected to PI WebAPI!")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to PI WebAPI: {str(e)}")
            self._connection_tested = False
            return False
    
    async def close(self):
        """Close the HTTP session"""
        if self._session and not self._session.closed:
            try:
                await self._session.close()
                # Wait a bit for the connection to close properly
                await asyncio.sleep(0.1)
                logger.debug("HTTP session closed")
            except Exception as e:
                logger.debug(f"Error closing session: {e}")
            finally:
                self._session = None
                self._session_loop = None
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to PI WebAPI with improved error handling and retries"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        logger.debug(f"Making {method} request to: {url}")
        
        # Retry logic for session recreation and network issues
        max_retries = 3
        base_delay = 1.0  # Base delay for exponential backoff
        
        for attempt in range(max_retries):
            try:
                lock = await self._get_lock()
                async with lock:
                    session = await self._ensure_session()
                
                async with session.request(method, url, **kwargs) as response:
                    logger.debug(f"Response status: {response.status}")
                    
                    # Handle different response status codes
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        if 'application/json' in content_type:
                            result = await response.json()
                            logger.debug(f"JSON response received: {len(str(result))} characters")
                            return result
                        else:
                            text_result = await response.text()
                            logger.debug(f"Text response received: {len(text_result)} characters")
                            return {"content": text_result}
                    
                    elif response.status == 401:
                        error_msg = "Authentication failed - check credentials and authentication method"
                        logger.error(error_msg)
                        raise Exception(error_msg)
                        
                    elif response.status == 403:
                        error_msg = "Access forbidden - check permissions"
                        logger.error(error_msg)
                        raise Exception(error_msg)
                        
                    elif response.status == 404:
                        error_text = await response.text()
                        error_msg = f"Resource not found: {error_text}"
                        logger.warning(error_msg)
                        raise Exception(error_msg)
                        
                    elif response.status >= 500:
                        error_text = await response.text()
                        error_msg = f"Server error {response.status}: {error_text}"
                        logger.error(error_msg)
                        # Server errors are retryable
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)  # Exponential backoff
                            logger.info(f"Server error, retrying in {delay} seconds (attempt {attempt + 1})")
                            await asyncio.sleep(delay)
                            continue
                        raise Exception(error_msg)
                        
                    else:
                        error_text = await response.text()
                        error_msg = f"HTTP {response.status}: {error_text}"
                        logger.error(error_msg)
                        raise Exception(error_msg)
                        
            except asyncio.TimeoutError as e:
                error_msg = f"Request timeout (attempt {attempt + 1}): {str(e)}"
                logger.warning(error_msg)
                
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.info(f"Timeout, retrying in {delay} seconds")
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise Exception(f"Request timed out after {max_retries} attempts")
                    
            except (aiohttp.ClientError, RuntimeError) as e:
                error_msg = str(e).lower()
                
                # Handle event loop issues
                if any(phrase in error_msg for phrase in ["event loop is closed", "session is closed", "connector is closed"]):
                    logger.warning(f"Session/loop issue detected (attempt {attempt + 1}): {e}")
                    
                    if attempt < max_retries - 1:
                        # Force session recreation
                        self._session = None
                        self._session_loop = None
                        delay = base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise Exception(f"Event loop/session error after retries: {str(e)}")
                else:
                    logger.error(f"Network error: {str(e)}")
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                        continue
                    raise Exception(f"Network error: {str(e)}")
                    
            except Exception as e:
                logger.error(f"Unexpected error in _make_request: {str(e)}")
                if attempt < max_retries - 1 and "closed" in str(e).lower():
                    # Try to recover from closed session
                    self._session = None
                    self._session_loop = None
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                raise
        
        # If we get here, all retries failed
        raise Exception("Failed to make request after all retries")
    
    async def get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make GET request"""
        return await self._make_request("GET", endpoint, params=params)
    
    async def post(self, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make POST request"""
        return await self._make_request("POST", endpoint, json=data)
    
    async def put(self, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make PUT request"""
        return await self._make_request("PUT", endpoint, json=data)
    
    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make DELETE request"""
        return await self._make_request("DELETE", endpoint)

# Improved global PI WebAPI client instance management
_pi_clients: Dict[int, PIWebAPIClient] = {}
_client_lock = threading.Lock()

def get_pi_client() -> PIWebAPIClient:
    """Get or initialize PI WebAPI client for current thread/loop"""
    try:
        thread_id = threading.get_ident()
        
        with _client_lock:
            if thread_id not in _pi_clients:
                base_url = os.getenv("PI_WEBAPI_URL", "https://localhost/piwebapi")
                username = os.getenv("PI_USERNAME")
                password = os.getenv("PI_PASSWORD")
                auth_method = os.getenv("PI_AUTH_METHOD", "negotiate")
                verify_ssl = os.getenv("PI_VERIFY_SSL", "true").lower() == "true"
                
                _pi_clients[thread_id] = PIWebAPIClient(
                    base_url=base_url,
                    username=username,
                    password=password,
                    verify_ssl=verify_ssl,
                    auth_method=auth_method
                )
                logger.debug(f"Created new PI client for thread {thread_id}")
        
        return _pi_clients[thread_id]
        
    except Exception as e:
        logger.error(f"Error getting PI client: {e}")
        # Fallback to creating a new client
        base_url = os.getenv("PI_WEBAPI_URL", "https://localhost/piwebapi")
        username = os.getenv("PI_USERNAME")
        password = os.getenv("PI_PASSWORD")
        auth_method = os.getenv("PI_AUTH_METHOD", "negotiate")
        verify_ssl = os.getenv("PI_VERIFY_SSL", "true").lower() == "true"
        
        return PIWebAPIClient(
            base_url=base_url,
            username=username,
            password=password,
            verify_ssl=verify_ssl,
            auth_method=auth_method
        )

async def cleanup_clients():
    """Cleanup all PI WebAPI clients"""
    global _pi_clients
    
    with _client_lock:
        cleanup_tasks = []
        for thread_id, client in _pi_clients.items():
            cleanup_tasks.append(client.close())
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        _pi_clients.clear()
    
    logger.info("All PI clients cleaned up")

async def get_all_af_elements_from_api() -> List[Dict[str, Any]]:
    """Get all AF elements from PI Web API for indexing with progress reporting"""
    try:
        client = get_pi_client()
        
        # Test connection first
        if not client._connection_tested:
            if not await client.test_connection():
                return []
        
        logger.info("Getting AF servers...")
        af_servers = await client.get("/assetservers")
        target_server = None
        
        for server in af_servers.get("Items", []):
            if server.get("Name", "").lower() == config.pi_system.af_server_name.lower():
                target_server = server
                break
        
        if not target_server:
            logger.error(f"AF Server '{config.pi_system.af_server_name}' not found")
            return []
        
        logger.info(f"Found AF server: {target_server.get('Name')}")
        
        # Get AF databases
        logger.info("Getting AF databases...")
        databases = await client.get(f"/assetservers/{target_server.get('WebId')}/assetdatabases")
        target_database = None
        
        for db in databases.get("Items", []):
            if db.get("Name", "").lower() == config.pi_system.af_database_name.lower():
                target_database = db
                break
        
        if not target_database:
            logger.error(f"AF Database '{config.pi_system.af_database_name}' not found")
            return []
        
        logger.info(f"Found AF database: {target_database.get('Name')}")
        
        # Get all elements from the database with full hierarchy search
        logger.info("Retrieving AF elements...")
        params = {
            "searchFullHierarchy": "true",
            "selectedFields": "Items.WebId;Items.Id;Items.Name;Items.Description;Items.Path;Items.TemplateName;Items.HasChildren",
            "maxCount": 10000  # Limit to prevent memory issues
        }
        
        elements = await client.get(f"/assetdatabases/{target_database.get('WebId')}/elements", params=params)
        element_items = elements.get("Items", [])
        
        logger.info(f"Retrieved {len(element_items)} AF elements from API (full hierarchy)")
        return element_items
        
    except Exception as e:
        logger.error(f"Failed to get AF elements from API: {str(e)}")
        server_state["last_error"] = str(e)
        return []

async def perform_af_indexing() -> Dict[str, Any]:
    """Perform AF elements indexing with improved error handling and progress tracking"""
    try:
        logger.info("Starting AF elements indexing...")
        server_state["indexing_in_progress"] = True
        server_state["last_error"] = None
        
        # Get all AF elements from PI Web API
        af_elements = await get_all_af_elements_from_api()
        
        if not af_elements:
            logger.warning("No AF elements found to index")
            return {"success": False, "error": "No elements found", "indexed_count": 0}
        
        # Index elements in vector database with progress reporting
        logger.info(f"Indexing {len(af_elements)} elements in vector database...")
        result = await vector_db.index_af_elements(af_elements)
        
        if result["success"]:
            logger.info(f"Successfully indexed {result['indexed_count']} AF elements")
            server_state["indexed_elements_count"] = result['indexed_count']
        else:
            logger.error(f"Failed to index AF elements: {result.get('error')}")
            server_state["last_error"] = result.get('error')
        
        return result
        
    except Exception as e:
        error_msg = f"Error during AF indexing: {str(e)}"
        logger.error(error_msg)
        server_state["last_error"] = error_msg
        return {"success": False, "error": str(e), "indexed_count": 0}
    finally:
        server_state["indexing_in_progress"] = False

async def background_indexing():
    """Background task for automatic AF elements indexing with better error handling"""
    logger.info("Starting background indexing task")
    
    while True:
        try:
            # Check if indexing should be refreshed
            if vector_db.should_refresh_index():
                logger.info("Time to refresh AF elements index")
                await perform_af_indexing()
            else:
                logger.debug("AF index is up to date")
            
            # Sleep for refresh interval
            sleep_hours = config.indexing.refresh_interval_hours
            logger.debug(f"Sleeping for {sleep_hours} hours until next index check")
            await asyncio.sleep(sleep_hours * 3600)
            
        except asyncio.CancelledError:
            logger.info("Background indexing task was cancelled")
            break
        except Exception as e:
            logger.error(f"Error in background indexing: {str(e)}")
            server_state["last_error"] = str(e)
            # Wait shorter time on error, but not too short to avoid spam
            await asyncio.sleep(1800)  # Wait 30 minutes on error

async def initialize_server():
    """Initialize the server with non-blocking startup"""
    logger.info("Initializing PI MCP server with vector database")
    
    try:
        # Test basic connectivity quickly
        client = get_pi_client()
        if await client.test_connection():
            logger.info("✅ Initial connection test successful")
        else:
            logger.warning("⚠️  Initial connection test failed - will retry in background")
        
        # Check if indexing is enabled
        if not config.indexing.enabled:
            logger.info("Vector database indexing is disabled")
            server_state["initialization_complete"] = True
            return
        
        # Start background indexing task (non-blocking)
        background_task = asyncio.create_task(background_indexing())
        background_task.add_done_callback(lambda t: logger.info("Background indexing task completed"))
        
        # Perform initial indexing in background if needed
        if vector_db.should_refresh_index():
            logger.info("Starting initial AF elements indexing in background...")
            # Don't await this - let it run in background
            asyncio.create_task(perform_af_indexing())
        else:
            logger.info("AF elements index is current, skipping initial indexing")
            
        server_state["initialization_complete"] = True
        logger.info("✅ Server initialization completed successfully")
        
    except Exception as e:
        error_msg = f"Server initialization error: {str(e)}"
        logger.error(error_msg)
        server_state["last_error"] = error_msg
        server_state["initialization_complete"] = True  # Mark as complete even with errors

# Server health monitoring
async def update_health_status():
    """Update server health status"""
    try:
        client = get_pi_client()
        
        # Quick system ping
        start_time = asyncio.get_event_loop().time()
        await client.get("/system")
        response_time = (asyncio.get_event_loop().time() - start_time) * 1000
        
        server_state["last_health_check"] = {
            "timestamp": datetime.now().isoformat(),
            "api_response_time_ms": round(response_time, 2),
            "status": "healthy" if response_time < 5000 else "slow"
        }
        
    except Exception as e:
        server_state["last_health_check"] = {
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e)
        }

# Resources
@mcp.resource("pi://system/info")
async def get_system_info() -> str:
    """Get PI System information and status"""
    try:
        client = get_pi_client()
        
        # Get system information
        system_info = await client.get("/system")
        
        # Get user information
        user_info = await client.get("/system/userinfo")
        
        # Get data servers
        data_servers = await client.get("/dataservers")
        
        # Get asset servers
        asset_servers = await client.get("/assetservers")
        
        result = {
            "system": system_info,
            "user": user_info,
            "dataServers": data_servers.get("Items", []),
            "assetServers": asset_servers.get("Items", [])
        }
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return f"Error retrieving system info: {str(e)}"

@mcp.resource("pi://system/health")
async def get_server_health() -> str:
    """Get MCP server health and status"""
    await update_health_status()
    
    health_info = {
        "server_state": server_state,
        "uptime_seconds": (datetime.now() - server_state["startup_time"]).total_seconds(),
        "vector_db_stats": await vector_db.get_collection_stats()
    }
    
    return json.dumps(health_info, indent=2)

@mcp.resource("pi://dataservers/{server_name}/points")
async def get_dataserver_points(server_name: str) -> str:
    """Get PI Points from a specific data server"""
    try:
        client = get_pi_client()
        
        # First get the data server by name/path
        data_servers = await client.get("/dataservers")
        target_server = None
        
        for server in data_servers.get("Items", []):
            if server.get("Name", "").lower() == server_name.lower():
                target_server = server
                break
        
        if not target_server:
            return f"Data server '{server_name}' not found"
        
        # Get points for this server with pagination
        web_id = target_server.get("WebId")
        params = {
            "maxCount": 1000,  # Limit for performance
            "selectedFields": "Items.Name;Items.WebId;Items.Descriptor;Items.PointClass;Items.PointType"
        }
        points = await client.get(f"/dataservers/{web_id}/points", params=params)
        
        return json.dumps({
            "server": target_server.get("Name"),
            "pointCount": len(points.get("Items", [])),
            "totalPoints": points.get("TotalHits", len(points.get("Items", []))),
            "points": points.get("Items", [])
        }, indent=2)
        
    except Exception as e:
        return f"Error retrieving points: {str(e)}"

@mcp.resource("pi://streams/{web_id}/current")
async def get_stream_current_value(web_id: str) -> str:
    """Get current value of a PI stream (Point or AF Attribute)"""
    try:
        client = get_pi_client()
        
        # Get current value
        value_data = await client.get(f"/streams/{web_id}/value", 
                                     params={"selectedFields": "Timestamp;Value;UnitsAbbreviation;Good;Questionable;Substituted"})
        
        return json.dumps(value_data, indent=2)
        
    except Exception as e:
        return f"Error retrieving current value: {str(e)}"

@mcp.resource("pi://elements/{element_path}")
async def get_af_element(element_path: str) -> str:
    """Get AF Element information by path"""
    try:
        client = get_pi_client()
        
        # Get element by path
        element = await client.get("/elements", params={"path": element_path})
        
        # Get element's attributes
        web_id = element.get("WebId")
        if web_id:
            params = {
                "maxCount": 100,  # Limit attributes for performance
                "selectedFields": "Items.Name;Items.WebId;Items.Description;Items.Type;Items.DefaultUnitsName"
            }
            attributes = await client.get(f"/elements/{web_id}/attributes", params=params)
            element["Attributes"] = attributes.get("Items", [])
        
        return json.dumps(element, indent=2)
        
    except Exception as e:
        return f"Error retrieving element: {str(e)}"

# Tools (keeping the same interface but with improved error handling)

@mcp.tool()
async def batch_get_element_attributes(
    element_web_ids: List[str],
    name_filter: str = "*",
    max_attributes_per_element: int = 20
) -> Dict[str, Any]:
    """
    Get AF Element attributes with WebIds and metadata - efficient way to get attribute WebIds for data retrieval
    
    This is the PRIMARY tool to use instead of search_pi_points for getting attribute WebIds.
    Use this when user asks for data from specific equipment
    Get attributes for multiple elements in batch for efficiency
    
    Args:
        element_web_ids: List of element WebIds
        name_filter: Filter attributes by name pattern
        max_attributes_per_element: Max attributes per element
    """
    try:
        client = get_pi_client()
        
        results = {}
        errors = []
        
        # Process elements in batches to avoid overwhelming the API
        batch_size = 10
        for i in range(0, len(element_web_ids), batch_size):
            batch = element_web_ids[i:i + batch_size]
            
            # Create concurrent requests for this batch
            batch_tasks = []
            for web_id in batch:
                params = {
                    "maxCount": max_attributes_per_element,
                    "selectedFields": "Items.WebId;Items.Name;Items.Type;Items.DefaultUnitsNameAbbreviation;Items.DataReferencePlugIn"
                }
                if name_filter != "*":
                    params["nameFilter"] = name_filter
                
                task = client.get(f"/elements/{web_id}/attributes", params=params)
                batch_tasks.append((web_id, task))
            
            # Execute batch requests
            for web_id, task in batch_tasks:
                try:
                    attributes = await task
                    results[web_id] = {
                        "count": len(attributes.get("Items", [])),
                        "attributes": attributes.get("Items", [])
                    }
                except Exception as e:
                    errors.append({"element_web_id": web_id, "error": str(e)})
        
        return {
            "requested_elements": len(element_web_ids),
            "successful_elements": len(results),
            "failed_elements": len(errors),
            "name_filter": name_filter,
            "results": results,
            "errors": errors
        }
        
    except Exception as e:
        logger.error(f"Batch get element attributes error: {str(e)}")
        return {"error": f"Failed to batch get element attributes: {str(e)}"}
    
@mcp.tool()
async def search_pi_points(
    name_filter: str = "*",
    max_count: int = 100,
    point_source: str = None
) -> Dict[str, Any]:
    """
    Dont use this until specifically asked to find pi points. Search for PI Points on the configured data server
    
    Args:
        name_filter: Point name filter (supports wildcards)
        max_count: Maximum number of results to return
        point_source: Filter by point source (optional)
    """
    try:
        client = get_pi_client()
        
        # Get data server from config
        data_servers = await client.get("/dataservers")
        target_server = None
        
        for server in data_servers.get("Items", []):
            if server.get("Name", "").lower() == config.pi_system.data_server_name.lower():
                target_server = server
                break
        
        if not target_server:
            return {"error": f"Data server '{config.pi_system.data_server_name}' not found"}
        
        # Build search query
        query_parts = [f"Tag:={name_filter}"]
        if point_source:
            query_parts.append(f"PointSource:={point_source}")
        
        query = " ".join(query_parts)
        
        # Search points with reasonable limits
        params = {
            "dataServerWebId": target_server.get("WebId"),
            "query": query,
            "maxCount": min(max_count, 500),  # Cap at 500 for performance
            "selectedFields": "Items.Name;Items.WebId;Items.Descriptor;Items.PointClass;Items.PointType"
        }
        
        results = await client.get("/points/search", params=params)
        
        return {
            "server": config.pi_system.data_server_name,
            "query": query,
            "count": len(results.get("Items", [])),
            "totalHits": results.get("TotalHits", len(results.get("Items", []))),
            "points": results.get("Items", [])
        }
        
    except Exception as e:
        logger.error(f"PI points search error: {str(e)}")
        return {"error": f"Search failed: {str(e)}"}

@mcp.tool()
async def get_recorded_values(
    stream_web_id: str,
    start_time: str = "*-1d",
    end_time: str = "*",
    max_count: int = 1000,
    filter_expression: str = None
) -> Dict[str, Any]:
    """
    Get recorded (historical) values for a PI stream
    
    Args:
        stream_web_id: WebId of the stream (PI Point or AF Attribute)
        start_time: Start time (PI time format, e.g., '*-1d', '2024-01-01T00:00:00Z')
        end_time: End time (PI time format)
        max_count: Maximum number of values to return
        filter_expression: Optional filter expression (e.g., "'.''>75")
    """
    try:
        client = get_pi_client()
        
        params = {
            "startTime": start_time,
            "endTime": end_time,
            "maxCount": min(max_count, 10000),  # Cap at 10k for performance
            "selectedFields": "Items.Timestamp;Items.Value;Items.UnitsAbbreviation;Items.Good"
        }
        
        if filter_expression:
            params["filterExpression"] = filter_expression
        
        values = await client.get(f"/streams/{stream_web_id}/recorded", params=params)
        
        return {
            "webId": stream_web_id,
            "startTime": start_time,
            "endTime": end_time,
            "count": len(values.get("Items", [])),
            "values": values.get("Items", [])
        }
        
    except Exception as e:
        logger.error(f"Get recorded values error: {str(e)}")
        return {"error": f"Failed to get recorded values: {str(e)}"}

@mcp.tool()
async def get_interpolated_values(
    stream_web_id: str,
    start_time: str = "*-1d",
    end_time: str = "*",
    interval: str = "1h"
) -> Dict[str, Any]:
    """
    Get interpolated values for a PI stream at regular intervals
    
    Args:
        stream_web_id: WebId of the stream
        start_time: Start time (PI time format)
        end_time: End time (PI time format)
        interval: Interpolation interval (e.g., '1h', '30m', '15s')
    """
    try:
        client = get_pi_client()
        
        params = {
            "startTime": start_time,
            "endTime": end_time,
            "interval": interval,
            "selectedFields": "Items.Timestamp;Items.Value;Items.UnitsAbbreviation"
        }
        
        values = await client.get(f"/streams/{stream_web_id}/interpolated", params=params)
        
        return {
            "webId": stream_web_id,
            "startTime": start_time,
            "endTime": end_time,
            "interval": interval,
            "count": len(values.get("Items", [])),
            "values": values.get("Items", [])
        }
        
    except Exception as e:
        logger.error(f"Get interpolated values error: {str(e)}")
        return {"error": f"Failed to get interpolated values: {str(e)}"}

# @mcp.tool()
# async def write_stream_value(
#     stream_web_id: str,
#     value: Union[float, str, int],
#     timestamp: str = None,
#     units_abbreviation: str = None
# ) -> Dict[str, Any]:
#     """
#     Write a value to a PI stream
    
#     Args:
#         stream_web_id: WebId of the stream
#         value: Value to write
#         timestamp: Timestamp for the value (optional, defaults to current time)
#         units_abbreviation: Units for the value (optional)
#     """
#     try:
#         client = get_pi_client()
        
#         # Prepare the value data
#         value_data = {"Value": value}
        
#         if timestamp:
#             value_data["Timestamp"] = timestamp
#         else:
#             value_data["Timestamp"] = datetime.utcnow().isoformat() + "Z"
            
#         if units_abbreviation:
#             value_data["UnitsAbbreviation"] = units_abbreviation
        
#         # Write the value
#         result = await client.post(f"/streams/{stream_web_id}/value", data=value_data)
        
#         return {
#             "webId": stream_web_id,
#             "writtenValue": value_data,
#             "result": result
#         }
        
#     except Exception as e:
#         logger.error(f"Write stream value error: {str(e)}")
#         return {"error": f"Failed to write value: {str(e)}"}

@mcp.tool()
async def search_af_elements(
    search_query: str,
    max_count: int = 100
) -> Dict[str, Any]:
    """
    Search for AF Elements in the configured database
    
    Args:
        search_query: Search query (e.g., 'Name:Tank*', 'Template:BoilerTemplate')
        max_count: Maximum number of results
    """
    try:
        client = get_pi_client()
        
        # Get the default database WebId from config
        af_servers = await client.get("/assetservers")
        target_server = None
        
        for server in af_servers.get("Items", []):
            if server.get("Name", "").lower() == config.pi_system.af_server_name.lower():
                target_server = server
                break
        
        if not target_server:
            return {"error": f"AF Server '{config.pi_system.af_server_name}' not found"}
        
        # Get databases
        databases = await client.get(f"/assetservers/{target_server.get('WebId')}/assetdatabases")
        target_database = None
        
        for db in databases.get("Items", []):
            if db.get("Name", "").lower() == config.pi_system.af_database_name.lower():
                target_database = db
                break
        
        if not target_database:
            return {"error": f"AF Database '{config.pi_system.af_database_name}' not found"}
        
        params = {
            "databaseWebId": target_database.get("WebId"),
            "query": search_query,
            "maxCount": min(max_count, 500),  # Cap at 500 for performance
            "selectedFields": "Items.Name;Items.WebId;Items.Path;Items.TemplateName;Items.HasChildren"
        }
        
        results = await client.get("/elements/search", params=params)
        
        return {
            "database": config.pi_system.af_database_name,
            "query": search_query,
            "count": len(results.get("Items", [])),
            "totalHits": results.get("TotalHits", len(results.get("Items", []))),
            "elements": results.get("Items", [])
        }
        
    except Exception as e:
        logger.error(f"AF elements search error: {str(e)}")
        return {"error": f"Search failed: {str(e)}"}

@mcp.tool()
async def get_streamset_values(
    element_web_id: str,
    name_filter: str = "*",
    start_time: str = "*",
    end_time: str = "*"
) -> Dict[str, Any]:
    """
    Get current values for all attributes of an AF Element (StreamSet operation)
    
    Args:
        element_web_id: WebId of the AF Element
        name_filter: Filter attributes by name pattern
        start_time: Start time for values (for recorded data)
        end_time: End time for values (for recorded data)
    """
    try:
        client = get_pi_client()
        
        params = {
            "selectedFields": "Items.Name;Items.Value;Items.Timestamp;Items.UnitsAbbreviation",
            "maxCount": 200  # Limit attributes for performance
        }
        
        if name_filter != "*":
            params["nameFilter"] = name_filter
            
        # Get current values for all attributes of the element
        values = await client.get(f"/streamsets/{element_web_id}/value", params=params)
        
        return {
            "elementWebId": element_web_id,
            "nameFilter": name_filter,
            "count": len(values.get("Items", [])),
            "values": values.get("Items", [])
        }
        
    except Exception as e:
        logger.error(f"Get streamset values error: {str(e)}")
        return {"error": f"Failed to get streamset values: {str(e)}"}

@mcp.tool()
async def search_af_elements_semantic(
    query: str,
    max_results: int = 10,
    template_filter: str = None,
    path_filter: str = None
) -> Dict[str, Any]:
    """
    Search AF elements using semantic/natural language search via vector database
    
    Args:
        query: Natural language search query (e.g., "temperature sensors", "pumps in unit 100")
        max_results: Maximum number of results to return
        template_filter: Optional template name filter
        path_filter: Optional path pattern filter
    """
    try:
        # Build filters
        filters = {}
        if template_filter:
            filters["template_name"] = template_filter
        if path_filter:
            # This would need custom logic for path filtering in ChromaDB
            pass
        
        # Search using vector database
        results = await vector_db.search_af_elements(query, min(max_results, 50), filters)
        
        return {
            "query": query,
            "search_type": "semantic_vector",
            "count": len(results),
            "results": results,
            "filters_applied": filters
        }
        
    except Exception as e:
        logger.error(f"Semantic search error: {str(e)}")
        return {"error": f"Semantic search failed: {str(e)}"}
    
@mcp.tool()
async def search_elements_by_template(
    template_name: str,
    max_results: int = 50
) -> Dict[str, Any]:
    """
    Search AF elements by template name using vector database
    
    Args:
        template_name: Name of the AF template
        max_results: Maximum number of results
    """
    try:
        results = await vector_db.get_elements_by_template(template_name, min(max_results, 100))
        
        return {
            "template_name": template_name,
            "search_type": "template_vector",
            "count": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Template search error: {str(e)}")
        return {"error": f"Template search failed: {str(e)}"}

@mcp.tool()
async def trigger_af_reindex() -> Dict[str, Any]:
    """
    Manually trigger AF elements re-indexing
    
    Returns:
        Result of the indexing operation
    """
    try:
        if server_state["indexing_in_progress"]:
            return {
                "error": "Indexing already in progress",
                "status": "skipped"
            }
        
        logger.info("Manual AF re-indexing triggered")
        result = await perform_af_indexing()
        
        return {
            "status": "completed",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Manual reindex error: {str(e)}")
        return {"error": f"Manual reindex failed: {str(e)}"}

@mcp.tool()
async def forecast_pi_attribute(
    stream_web_id: str,
    historical_days: int = 30,
    forecast_days: int = 7,
    seasonality_mode: str = "auto",
    growth: str = "linear",
    include_holidays: bool = False,
    interval_width: float = 0.8
) -> Dict[str, Any]:
    """
    Generate time series forecast for a single PI attribute using Facebook Prophet
    
    Args:
        stream_web_id: WebId of the PI stream (Point or AF Attribute)
        historical_days: Number of days of historical data to use for training
        forecast_days: Number of days to forecast into the future
        seasonality_mode: Seasonality mode ('additive', 'multiplicative', 'auto')
        growth: Growth model ('linear', 'logistic')
        include_holidays: Whether to include holiday effects (US holidays)
        interval_width: Width of the uncertainty intervals (0-1)
    
    Returns:
        Forecast results with historical data, predictions, and model performance metrics
    """
    try:
        # Suppress Prophet warnings for cleaner output
        warnings.filterwarnings('ignore', category=UserWarning, module='prophet')
        
        logger.info(f"Starting forecast for stream {stream_web_id}")
        client = get_pi_client()
        
        # Calculate time range for historical data
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=historical_days)
        
        # Get historical data
        params = {
            "startTime": start_time.isoformat() + "Z",
            "endTime": end_time.isoformat() + "Z",
            "maxCount": min(historical_days * 24 * 60, 50000),  # Reasonable limit
            "selectedFields": "Items.Timestamp;Items.Value;Items.Good"
        }
        
        logger.info(f"Retrieving historical data from {start_time} to {end_time}")
        values_response = await client.get(f"/streams/{stream_web_id}/recorded", params=params)
        values = values_response.get("Items", [])
        
        if len(values) < 10:
            return {
                "error": "Insufficient historical data for forecasting (minimum 10 data points required)",
                "data_points_found": len(values)
            }
        
        # Convert to DataFrame for Prophet
        df_data = []
        for item in values:
            # Only use good quality data
            if item.get("Good", False):
                try:
                    timestamp = pd.to_datetime(item["Timestamp"])
                    value = float(item["Value"])
                    df_data.append({"ds": timestamp, "y": value})
                except (ValueError, TypeError, KeyError):
                    continue
        
        if len(df_data) < 10:
            return {
                "error": "Insufficient good quality data for forecasting",
                "total_points": len(values),
                "good_quality_points": len(df_data)
            }
        
        df = pd.DataFrame(df_data)
        logger.info(f"Prepared {len(df)} data points for forecasting")
        
        # Remove duplicates and sort by timestamp
        df = df.drop_duplicates(subset=['ds']).sort_values('ds').reset_index(drop=True)
        
        # Basic data validation and cleaning
        # Remove obvious outliers (beyond 3 standard deviations)
        mean_val = df['y'].mean()
        std_val = df['y'].std()
        
        if std_val > 0:
            outlier_threshold = 3 * std_val
            df = df[abs(df['y'] - mean_val) <= outlier_threshold]
        
        if len(df) < 10:
            return {
                "error": "Insufficient data after cleaning (outlier removal)",
                "remaining_points": len(df)
            }
        
        # Initialize Prophet model with parameters
        model_params = {
            "growth": growth,
            "seasonality_mode": seasonality_mode,
            "interval_width": interval_width,
            "daily_seasonality": True,
            "weekly_seasonality": True,
            "yearly_seasonality": True if historical_days > 365 else False
        }
        
        # Add US holidays if requested
        if include_holidays:
            try:
                model_params["holidays"] = Prophet().make_holidays_df(
                    year_list=list(range(start_time.year, end_time.year + 2))
                )
            except Exception as e:
                logger.warning(f"Could not add holidays: {e}")
        
        # Create and fit the model
        logger.info("Training Prophet model...")
        model = Prophet(**model_params)
        
        # Fit the model
        model.fit(df)
        
        # Create future dataframe for predictions
        future_periods = forecast_days * 24  # Hourly predictions
        future = model.make_future_dataframe(periods=future_periods, freq='H')
        
        # Generate forecast
        logger.info(f"Generating {forecast_days}-day forecast...")
        forecast = model.predict(future)
        
        # Split historical and future predictions
        historical_count = len(df)
        historical_forecast = forecast.iloc[:historical_count]
        future_forecast = forecast.iloc[historical_count:]
        
        # Calculate model performance metrics on historical data
        actual_values = df['y'].values
        predicted_values = historical_forecast['yhat'].values
        
        # Align arrays (in case of different lengths)
        min_len = min(len(actual_values), len(predicted_values))
        actual_values = actual_values[:min_len]
        predicted_values = predicted_values[:min_len]
        
        # Calculate metrics
        mae = np.mean(np.abs(actual_values - predicted_values))
        mse = np.mean((actual_values - predicted_values) ** 2)
        rmse = np.sqrt(mse)
        
        # Calculate MAPE (avoiding division by zero)
        mape = np.mean(np.abs((actual_values - predicted_values) / np.where(actual_values != 0, actual_values, 1))) * 100
        
        # R-squared
        ss_res = np.sum((actual_values - predicted_values) ** 2)
        ss_tot = np.sum((actual_values - np.mean(actual_values)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        # Prepare results
        result = {
            "stream_web_id": stream_web_id,
            "model_parameters": model_params,
            "data_summary": {
                "historical_days": historical_days,
                "forecast_days": forecast_days,
                "total_historical_points": len(values),
                "good_quality_points": len(df_data),
                "points_used_for_training": len(df),
                "training_period_start": df['ds'].min().isoformat(),
                "training_period_end": df['ds'].max().isoformat()
            },
            "model_performance": {
                "mae": round(mae, 4),
                "mse": round(mse, 4),
                "rmse": round(rmse, 4),
                "mape_percent": round(mape, 2),
                "r_squared": round(r_squared, 4)
            },
            "forecast_data": {
                "forecast_start": future_forecast['ds'].min().isoformat() if len(future_forecast) > 0 else None,
                "forecast_end": future_forecast['ds'].max().isoformat() if len(future_forecast) > 0 else None,
                "forecast_points": len(future_forecast),
                "predictions": []
            },
            "historical_fit": {
                "points": len(historical_forecast),
                "data": []
            }
        }
        
        # Add forecast predictions (limit to reasonable number for response size)
        max_forecast_points = min(len(future_forecast), 168)  # Max 1 week hourly
        for i in range(max_forecast_points):
            row = future_forecast.iloc[i]
            result["forecast_data"]["predictions"].append({
                "timestamp": row['ds'].isoformat(),
                "predicted_value": round(row['yhat'], 4),
                "lower_bound": round(row['yhat_lower'], 4),
                "upper_bound": round(row['yhat_upper'], 4),
                "trend": round(row['trend'], 4) if 'trend' in row else None
            })
        
        # Add historical fit data (sample for response size)
        sample_size = min(len(historical_forecast), 100)
        step = max(1, len(historical_forecast) // sample_size)
        
        for i in range(0, len(historical_forecast), step):
            hist_row = historical_forecast.iloc[i]
            actual_row = df.iloc[i] if i < len(df) else None
            
            fit_point = {
                "timestamp": hist_row['ds'].isoformat(),
                "predicted_value": round(hist_row['yhat'], 4),
                "actual_value": round(actual_row['y'], 4) if actual_row is not None else None,
                "residual": round(actual_row['y'] - hist_row['yhat'], 4) if actual_row is not None else None
            }
            result["historical_fit"]["data"].append(fit_point)
        
        # Add forecast summary statistics
        if len(future_forecast) > 0:
            result["forecast_summary"] = {
                "mean_predicted_value": round(future_forecast['yhat'].mean(), 4),
                "min_predicted_value": round(future_forecast['yhat'].min(), 4),
                "max_predicted_value": round(future_forecast['yhat'].max(), 4),
                "predicted_trend": "increasing" if future_forecast['yhat'].iloc[-1] > future_forecast['yhat'].iloc[0] else "decreasing",
                "average_uncertainty_range": round((future_forecast['yhat_upper'] - future_forecast['yhat_lower']).mean(), 4)
            }
        
        logger.info(f"Forecast completed successfully. RMSE: {rmse:.4f}, MAPE: {mape:.2f}%")
        
        return result
        
    except ImportError as e:
        logger.error(f"Prophet library not available: {str(e)}")
        return {
            "error": "Prophet library not installed. Please install with: pip install prophet",
            "details": str(e)
        }
    except Exception as e:
        logger.error(f"Forecast error: {str(e)}")
        return {
            "error": f"Failed to generate forecast: {str(e)}",
            "stream_web_id": stream_web_id,
            "parameters": {
                "historical_days": historical_days,
                "forecast_days": forecast_days
            }
        }
      
@mcp.tool()
async def get_pi_system_health() -> Dict[str, Any]:
    """
    Get comprehensive PI System health information
    
    Returns comprehensive system health data including:
    - System status and uptime
    - Data server information
    - Asset server status
    - User authentication info
    - Recent system performance
    - MCP server health
    """
    try:
        client = get_pi_client()
        health_data = {}
        
        # 1. Get system status and uptime
        system_info = await client.get("/system")
        health_data["system_status"] = {
            "version": system_info.get("Version"),
            "uptime_minutes": system_info.get("UpTimeMinutes"),
            "state": system_info.get("State"),
            "cache_instances": system_info.get("CacheInstances"),
            "server_time": system_info.get("ServerTime")
        }
        
        # 2. Get user authentication info
        user_info = await client.get("/system/userinfo")
        health_data["authentication"] = {
            "current_user": user_info.get("Name"),
            "identity_type": user_info.get("IdentityType"),
            "is_authenticated": user_info.get("IsAuthenticated"),
            "impersonation_level": user_info.get("ImpersonationLevel")
        }
        
        # 3. Get data servers status (limit to avoid timeout)
        data_servers = await client.get("/dataservers")
        health_data["data_servers"] = []
        
        # Limit to first 3 servers to avoid timeout
        for server in data_servers.get("Items", [])[:3]:
            try:
                server_detail = await client.get(f"/dataservers/{server.get('WebId')}")
                
                # Get server points count with timeout protection
                try:
                    points = await asyncio.wait_for(
                        client.get(f"/dataservers/{server.get('WebId')}/points", 
                                  params={"maxCount": 1}),
                        timeout=5.0
                    )
                    total_points = points.get("TotalHits", 0)
                except asyncio.TimeoutError:
                    total_points = "Timeout"
                except Exception:
                    total_points = "Unknown"
                
                health_data["data_servers"].append({
                    "name": server.get("Name"),
                    "server_version": server_detail.get("ServerVersion"),
                    "is_connected": server_detail.get("IsConnected"),
                    "server_time": server_detail.get("ServerTime"),
                    "total_points": total_points
                })
            except Exception as e:
                logger.warning(f"Error getting details for data server {server.get('Name')}: {e}")
                health_data["data_servers"].append({
                    "name": server.get("Name"),
                    "error": str(e)
                })
        
        # 4. Get asset servers status (limit to avoid timeout)
        asset_servers = await client.get("/assetservers")
        health_data["asset_servers"] = []
        
        # Limit to first 3 servers
        for server in asset_servers.get("Items", [])[:3]:
            try:
                server_detail = await asyncio.wait_for(
                    client.get(f"/assetservers/{server.get('WebId')}"),
                    timeout=5.0
                )
                
                # Get databases count with timeout protection
                try:
                    databases = await asyncio.wait_for(
                        client.get(f"/assetservers/{server.get('WebId')}/assetdatabases"),
                        timeout=5.0
                    )
                    db_count = len(databases.get("Items", []))
                except asyncio.TimeoutError:
                    db_count = "Timeout"
                except Exception:
                    db_count = "Unknown"
                    
                health_data["asset_servers"].append({
                    "name": server.get("Name"),
                    "server_version": server_detail.get("ServerVersion"),
                    "is_connected": server_detail.get("IsConnected"),
                    "server_time": server_detail.get("ServerTime"),
                    "database_count": db_count
                })
            except Exception as e:
                logger.warning(f"Error getting details for asset server {server.get('Name')}: {e}")
                health_data["asset_servers"].append({
                    "name": server.get("Name"),
                    "error": str(e)
                })
        
        # 5. Test API responsiveness
        import time
        start_time = time.time()
        try:
            await asyncio.wait_for(client.get("/system"), timeout=10.0)
            response_time = (time.time() - start_time) * 1000  # ms
            health_data["performance"] = {
                "api_response_time_ms": round(response_time, 2),
                "status": "responsive" if response_time < 1000 else "slow"
            }
        except asyncio.TimeoutError:
            health_data["performance"] = {
                "api_response_time_ms": None,
                "status": "timeout",
                "error": "API response timeout"
            }
        except Exception as e:
            health_data["performance"] = {
                "api_response_time_ms": None,
                "status": "error",
                "error": str(e)
            }
        
        # 6. Add MCP server health
        health_data["mcp_server"] = {
            "initialization_complete": server_state["initialization_complete"],
            "indexing_in_progress": server_state["indexing_in_progress"],
            "indexed_elements_count": server_state["indexed_elements_count"],
            "last_error": server_state["last_error"],
            "uptime_seconds": (datetime.now() - server_state["startup_time"]).total_seconds()
        }
        
        # 7. Add vector database stats
        try:
            vector_stats = await asyncio.wait_for(vector_db.get_collection_stats(), timeout=5.0)
            health_data["vector_database"] = vector_stats
        except Exception as e:
            health_data["vector_database"] = {"error": str(e)}
        
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "overall_status": "healthy" if all([
                health_data["system_status"].get("state") == "Running",
                health_data["authentication"].get("is_authenticated"),
                len(health_data["data_servers"]) > 0,
                server_state["initialization_complete"]
            ]) else "issues_detected",
            "health_data": health_data
        }
        
    except Exception as e:
        logger.error(f"System health check error: {str(e)}")
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "overall_status": "error",
            "error": f"Failed to get system health: {str(e)}",
            "mcp_server_state": server_state
        }

# Prompt templates (keeping the same interface)
@mcp.prompt()
async def pi_data_analysis(
    tag_names: List[str],
    time_period: str = "24h",
    analysis_type: str = "trend"
) -> str:
    """
    Generate a prompt for analyzing PI data trends and patterns
    
    Args:
        tag_names: List of PI Point or AF Attribute names to analyze
        time_period: Time period for analysis (e.g., '24h', '7d', '1w')
        analysis_type: Type of analysis ('trend', 'correlation', 'anomaly', 'summary')
    """
    
    tag_list = ", ".join(tag_names)
    
    if analysis_type == "trend":
        return f"""
Analyze the trending behavior of the following PI data points over the last {time_period}:
{tag_list}

Please examine:
1. Overall trends (increasing, decreasing, stable)
2. Significant changes or inflection points
3. Cyclical patterns or seasonality
4. Data quality issues (gaps, outliers)
5. Range and variability of values

Provide insights on:
- Process stability and control
- Potential operational issues
- Recommendations for further investigation
- Data quality assessment
"""
    
    elif analysis_type == "correlation":
        return f"""
Perform correlation analysis between these PI data points over the last {time_period}:
{tag_list}

Analyze:
1. Correlation coefficients between variables
2. Lead-lag relationships
3. Cause-and-effect patterns
4. Process interdependencies

Provide insights on:
- Which variables move together
- Process control loops and relationships
- Potential cascade effects
- Optimization opportunities
"""
    
    elif analysis_type == "anomaly":
        return f"""
Identify anomalies and outliers in the following PI data over the last {time_period}:
{tag_list}

Look for:
1. Statistical outliers (values beyond normal ranges)
2. Sudden spikes or drops
3. Extended periods of abnormal behavior
4. Missing or bad quality data
5. Process upsets or disturbances

Provide:
- Root cause analysis suggestions
- Impact assessment
- Preventive measures
- Data validation recommendations
"""
    
    else:  # summary
        return f"""
Provide a comprehensive summary of the following PI data points over the last {time_period}:
{tag_list}

Include:
1. Statistical summary (min, max, average, standard deviation)
2. Data completeness and quality metrics
3. Key operational events or changes
4. Performance indicators and KPIs
5. Comparison to typical operating ranges

Summarize:
- Overall process performance
- Data reliability
- Operational highlights
- Areas for improvement
"""

@mcp.prompt()
async def pi_system_health() -> str:
    """Generate a prompt for assessing PI System health and performance"""
    return """
Assess the overall health and performance of the PI System based on available system information.

Please analyze:

1. **System Status**
   - PI Data Archive status and performance
   - PI Asset Framework (AF) server health
   - PI Web API service status
   - Network connectivity and authentication

2. **Data Quality**
   - Missing or bad data points
   - Archive efficiency and compression
   - Point count and data rates
   - Buffer subsystem status

3. **Performance Metrics**
   - Query response times
   - Data throughput rates
   - System resource utilization
   - User activity and load

4. **Security and Access**
   - Authentication methods in use
   - User permissions and mappings
   - SSL/TLS configuration
   - Recent security events

5. **Maintenance Indicators**
   - System uptime and stability
   - Recent configuration changes
   - Backup and recovery status
   - Version information and updates

6. **MCP Server Health**
   - Server initialization status
   - Vector database indexing status
   - Background task health
   - Error conditions and recovery

Provide recommendations for:
- Performance optimization
- Data quality improvements
- Security enhancements
- Preventive maintenance actions
"""

@mcp.prompt()
async def pi_forecasting_analysis(
    attribute_name: str,
    forecast_period: str = "7 days",
    historical_period: str = "30 days"
) -> str:
    """
    Generate a prompt for analyzing PI forecasting results and trends
    
    Args:
        attribute_name: Name of the PI attribute being forecasted
        forecast_period: Period for which forecast was generated
        historical_period: Historical period used for training
    """
    return f"""
Analyze the forecasting results for the PI attribute '{attribute_name}' based on {historical_period} of historical data to predict the next {forecast_period}.

Please examine the following aspects:

1. **Model Performance**
   - Evaluate the accuracy metrics (RMSE, MAE, MAPE, R-squared)
   - Assess the quality of the historical fit
   - Identify any systematic biases or patterns in residuals
   - Comment on model reliability and confidence intervals

2. **Forecast Analysis**
   - Describe the predicted trend (increasing, decreasing, stable)
   - Identify any seasonal patterns or cyclical behavior
   - Highlight significant changes or anomalies in the forecast
   - Assess the uncertainty ranges and their implications

3. **Historical Data Quality**
   - Review data completeness and quality metrics
   - Identify any data gaps or outliers that were removed
   - Comment on the representativeness of the training period
   - Suggest improvements for data collection or preprocessing

4. **Business Insights**
   - Translate technical forecast into operational insights
   - Identify potential operational issues or opportunities
   - Suggest proactive maintenance or operational adjustments
   - Recommend monitoring thresholds or alert conditions

5. **Model Limitations & Recommendations**
   - Discuss the assumptions and limitations of the forecast
   - Suggest when the model should be retrained
   - Recommend additional data sources or features that could improve accuracy
   - Propose validation strategies for ongoing model performance

6. **Actionable Recommendations**
   - Provide specific actions based on the forecast
   - Suggest optimal timing for maintenance or operational changes
   - Recommend risk mitigation strategies for adverse predictions
   - Propose continuous improvement opportunities

Focus on practical, actionable insights that can help optimize plant operations and maintenance schedules.
"""

# Cleanup function
async def cleanup():
    """Cleanup function to close PI WebAPI clients and background tasks"""
    logger.info("Starting cleanup...")
    
    # Cancel any running background tasks
    current_task = asyncio.current_task()
    all_tasks = asyncio.all_tasks()
    
    background_tasks = [
        task for task in all_tasks 
        if task != current_task and not task.done()
    ]
    
    if background_tasks:
        logger.info(f"Cancelling {len(background_tasks)} background tasks")
        for task in background_tasks:
            task.cancel()
        
        # Wait for tasks to cancel
        await asyncio.gather(*background_tasks, return_exceptions=True)
    
    # Cleanup clients
    await cleanup_clients()
    
    logger.info("Cleanup completed")

if __name__ == "__main__":
    # Configuration validation
    required_env_vars = ["PI_WEBAPI_URL"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.info("Please set the following environment variables:")
        logger.info("- PI_WEBAPI_URL: Base URL for PI Web API (e.g., https://server/piwebapi)")
        logger.info("- PI_USERNAME: Username for authentication (optional for Windows auth)")
        logger.info("- PI_PASSWORD: Password for authentication (optional for Windows auth)")
        logger.info("- PI_AUTH_METHOD: Authentication method (negotiate, basic, bearer)")
        logger.info("- PI_VERIFY_SSL: Whether to verify SSL certificates (true/false)")
        exit(1)
    
    logger.info("Starting AVEVA PI System MCP Server...")
    logger.info(f"PI Web API URL: {os.getenv('PI_WEBAPI_URL')}")
    logger.info(f"Authentication Method: {os.getenv('PI_AUTH_METHOD', 'negotiate')}")
    logger.info(f"SSL Verification: {os.getenv('PI_VERIFY_SSL', 'true')}")
    
    # Set up initialization flag
    _initialization_started = False
    
    # Original resource that will trigger initialization on first access
    original_get_system_info = get_system_info
    
    @mcp.resource("pi://system/info")
    async def get_system_info_with_init() -> str:
        """Get PI System information and trigger initialization if needed"""
        global _initialization_started
        
        # Start initialization on first resource access
        if not _initialization_started:
            _initialization_started = True
            logger.info("🔄 First resource access detected, starting background initialization...")
            asyncio.create_task(initialize_server())
        
        return await original_get_system_info()
    
    try:
        # Get port and host from environment variables or use defaults
        port = int(os.environ.get("PORT", 8001))
        host = os.environ.get("HOST", "0.0.0.0")

        logger.info(f"🚀 Starting MCP server on {host}:{port}...")

        # Run the server ONCE with the correct transport and configuration
        # Note: The transport name is 'http', not 'streamable-http' in newer versions.
        mcp.run(transport="http", host=host, port=port)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        # Run cleanup in a new event loop since the main one is shutting down
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(cleanup())
            loop.close()
        except Exception as cleanup_error:
            logger.error(f"Cleanup error: {cleanup_error}")
    except Exception as e:
        logger.error(f"Server error: {e}")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(cleanup())
            loop.close()
        except Exception as cleanup_error:
            logger.error(f"Cleanup error: {cleanup_error}")
        exit(1)
