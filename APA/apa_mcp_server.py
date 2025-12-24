#!/usr/bin/env python3
"""
AVEVA Predictive Analytics MCP Server

This MCP server provides integration with AVEVA Predictive Analytics Web API,
exposing resources, tools, and prompts for interacting with PA projects,
assets, alerts, fault diagnostics, forecasts, and historical data.

Features:
- Token-based authentication with automatic refresh
- Complete API coverage for PA Web API
- Alert management and state transitions
- Historical data retrieval
- Fault diagnostics analysis
- Forecast model management
- Sensor monitoring

Author: AVEVA PI System Integration Team
Version: 1.0.0
"""

import asyncio
import json
import logging
import os
import base64
import ssl
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin
import threading

import aiohttp
from fastmcp import FastMCP
from mcp.types import Resource, Tool, TextResourceContents

from config import config, ALERT_STATE_ICONS, POINT_TYPES, ALERT_THRESHOLD_TYPES

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("AVEVA Predictive Analytics")

# Global server state
server_state = {
    "initialization_complete": False,
    "last_error": None,
    "startup_time": datetime.now(),
    "authenticated": False,
    "last_health_check": None
}


class APAWebAPIClient:
    """
    Client for AVEVA Predictive Analytics Web API interactions.
    
    Implements token-based authentication with automatic refresh,
    as per the API documentation.
    """

    def __init__(self, base_url: str, username: str = None, password: str = None,
                 domain: str = None, verify_ssl: bool = True, timeout: int = 60):
        """
        Initialize APA Web API client.
        
        Args:
            base_url: Base URL for PA Web (e.g., https://server/avevapredictiveanalytics)
            username: Domain username (format: DOMAIN\\USER)
            password: User password
            domain: Active Directory domain
            verify_ssl: Whether to verify SSL certificates
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.domain = domain
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        
        self._session = None
        self._session_loop = None
        self._lock = None
        
        # Token management
        self._access_token = None
        self._refresh_token = None
        self._token_expires_at = None
        self._user_guid = None

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

        if (self._session is None or
                self._session.closed or
                self._session_loop != current_loop):

            if self._session and not self._session.closed:
                try:
                    await self._session.close()
                except Exception as e:
                    logger.debug(f"Error closing old session: {e}")

            self._session = await self._create_session()
            self._session_loop = current_loop

        return self._session

    async def _create_session(self) -> aiohttp.ClientSession:
        """Create a new HTTP session"""
        if self.verify_ssl:
            ssl_context = ssl.create_default_context()
        else:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(
            ssl=ssl_context,
            limit=100,
            limit_per_host=30,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )

        session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(
                total=self.timeout,
                connect=10,
                sock_read=30
            )
        )

        logger.debug(f"Created new aiohttp session")
        return session

    async def authenticate(self) -> bool:
        """
        Authenticate with the PA Web API using Identity and Token endpoints.
        
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            logger.info("Authenticating with AVEVA Predictive Analytics API...")
            
            # Step 1: Call Identity endpoint to get user GUID
            identity_url = f"{self.base_url}/api/identity"
            
            # Prepare credentials (base64 encoded for SSL)
            credentials = f"{self.domain}\\{self.username}" if self.domain else self.username
            auth_header = base64.b64encode(
                f"{credentials}:{self.password}".encode()
            ).decode()

            session = await self._ensure_session()
            
            headers = {
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/json"
            }

            async with session.post(identity_url, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    self._user_guid = result if isinstance(result, str) else result.get("guid", result.get("Id"))
                    logger.info("✅ Identity authentication successful")
                elif response.status == 401:
                    logger.error("❌ Authentication failed - invalid credentials")
                    return False
                elif response.status == 403:
                    logger.error("❌ Access forbidden - user does not have PA Web privileges")
                    return False
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Identity authentication failed: {response.status} - {error_text}")
                    return False

            # Step 2: Get tokens from Token endpoint
            token_url = f"{self.base_url}/token"
            
            token_data = {
                "grant_type": "password",
                "username": self._user_guid,
                "client_id": "prism-api",
                "client_secret": "prism-api"
            }

            headers = {"Content-Type": "application/x-www-form-urlencoded"}

            async with session.post(token_url, data=token_data, headers=headers) as response:
                if response.status == 200:
                    token_result = await response.json()
                    self._access_token = token_result.get("access_token")
                    self._refresh_token = token_result.get("refresh_token")
                    expires_in = token_result.get("expires_in", 35999)
                    self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                    
                    server_state["authenticated"] = True
                    logger.info(f"✅ Token acquired, expires in {expires_in} seconds")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Token acquisition failed: {response.status} - {error_text}")
                    return False

        except Exception as e:
            logger.error(f"❌ Authentication error: {str(e)}")
            return False

    async def _ensure_authenticated(self):
        """Ensure we have a valid access token, refreshing if necessary"""
        if not self._access_token:
            if not await self.authenticate():
                raise Exception("Authentication failed")
        
        # Check if token is about to expire (with 5 minute buffer)
        if self._token_expires_at and datetime.now() >= (
            self._token_expires_at - timedelta(seconds=config.token_refresh_buffer_seconds)
        ):
            logger.info("Access token expiring soon, re-authenticating...")
            if not await self.authenticate():
                raise Exception("Token refresh failed")

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated HTTP request to PA Web API"""
        await self._ensure_authenticated()
        
        url = f"{self.base_url}/api/v1/{endpoint.lstrip('/')}"
        
        logger.debug(f"Making {method} request to: {url}")

        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                session = await self._ensure_session()
                
                headers = kwargs.pop("headers", {})
                headers["Authorization"] = f"Bearer {self._access_token}"
                headers["Content-Type"] = "application/json"

                async with session.request(method, url, headers=headers, **kwargs) as response:
                    logger.debug(f"Response status: {response.status}")

                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        if 'application/json' in content_type:
                            return await response.json()
                        else:
                            return {"content": await response.text()}

                    elif response.status == 206:
                        # Partial content - large dataset
                        return await response.json()

                    elif response.status == 401:
                        logger.warning("Token invalid, re-authenticating...")
                        self._access_token = None
                        await self._ensure_authenticated()
                        continue

                    elif response.status == 403:
                        error_text = await response.text()
                        raise Exception(f"Access forbidden: {error_text}")

                    elif response.status == 406:
                        # Token expired
                        logger.warning("Token expired, re-authenticating...")
                        self._access_token = None
                        await self._ensure_authenticated()
                        continue

                    elif response.status == 423:
                        raise Exception("Resource is locked")

                    elif response.status >= 400:
                        error_text = await response.text()
                        raise Exception(f"HTTP {response.status}: {error_text}")

            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (2 ** attempt))
                    continue
                raise Exception("Request timed out")

            except aiohttp.ClientError as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (2 ** attempt))
                    continue
                raise Exception(f"Network error: {str(e)}")

        raise Exception("Request failed after all retries")

    async def get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make GET request"""
        return await self._make_request("GET", endpoint, params=params)

    async def post(self, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make POST request"""
        return await self._make_request("POST", endpoint, json=data)

    async def put(self, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make PUT request"""
        return await self._make_request("PUT", endpoint, json=data)

    async def delete(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make DELETE request"""
        return await self._make_request("DELETE", endpoint, params=params)

    async def close(self):
        """Close the HTTP session"""
        if self._session and not self._session.closed:
            try:
                await self._session.close()
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.debug(f"Error closing session: {e}")
            finally:
                self._session = None
                self._session_loop = None


# Global client management
_apa_clients: Dict[int, APAWebAPIClient] = {}
_client_lock = threading.Lock()


def get_apa_client() -> APAWebAPIClient:
    """Get or initialize APA Web API client for current thread"""
    thread_id = threading.get_ident()

    with _client_lock:
        if thread_id not in _apa_clients:
            _apa_clients[thread_id] = APAWebAPIClient(
                base_url=config.apa.base_url,
                username=config.apa.username,
                password=config.apa.password,
                domain=config.apa.domain,
                verify_ssl=config.apa.verify_ssl,
                timeout=config.apa.timeout
            )
            logger.debug(f"Created new APA client for thread {thread_id}")

    return _apa_clients[thread_id]


async def cleanup_clients():
    """Cleanup all APA Web API clients"""
    global _apa_clients

    with _client_lock:
        cleanup_tasks = []
        for thread_id, client in _apa_clients.items():
            cleanup_tasks.append(client.close())

        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)

        _apa_clients.clear()

    logger.info("All APA clients cleaned up")


# ============================================================================
# MCP RESOURCES
# ============================================================================

@mcp.resource("apa://system/health")
async def get_system_health() -> str:
    """Get MCP server health and authentication status"""
    health_info = {
        "server_state": server_state,
        "uptime_seconds": (datetime.now() - server_state["startup_time"]).total_seconds(),
        "authenticated": server_state["authenticated"],
        "config": {
            "base_url": config.apa.base_url,
            "api_version": config.apa.api_version
        }
    }
    return json.dumps(health_info, indent=2, default=str)


@mcp.resource("apa://alerts/states")
async def get_alert_states_resource() -> str:
    """Get available alert workflow states"""
    try:
        client = get_apa_client()
        states = await client.get("/AlarmWorkFlowStates")
        return json.dumps(states, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.resource("apa://alerts/clear-parameters")
async def get_clear_parameters_resource() -> str:
    """Get allowed clear parameters for alert management"""
    try:
        client = get_apa_client()
        params = await client.get("/AlarmWorkFlowStates/ClearParameters")
        return json.dumps(params, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ============================================================================
# MCP TOOLS - AUTHENTICATION
# ============================================================================

@mcp.tool()
async def authenticate_apa() -> Dict[str, Any]:
    """
    Authenticate with AVEVA Predictive Analytics Web API.
    
    This tool initiates the authentication process using configured credentials.
    Must be called before using any other tools if not already authenticated.
    
    Returns:
        Authentication status and token expiration info
    """
    try:
        client = get_apa_client()
        success = await client.authenticate()
        
        if success:
            return {
                "success": True,
                "message": "Successfully authenticated with PA Web API",
                "token_expires_at": client._token_expires_at.isoformat() if client._token_expires_at else None
            }
        else:
            return {
                "success": False,
                "error": "Authentication failed - check credentials and permissions"
            }
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MCP TOOLS - ALERT STATUS
# ============================================================================

@mcp.tool()
async def get_asset_alert_status(
    asset_id: int = None
) -> Dict[str, Any]:
    """
    Get alert status for an asset and its children.
    
    Returns the name and alert state for the requested asset, including all
    child assets and projects assigned to this asset.
    
    Args:
        asset_id: Asset ID (optional, returns root asset if not provided)
    
    Returns:
        Asset alert status including child assets and projects
    """
    try:
        client = get_apa_client()
        
        endpoint = "/assets" if asset_id is None else f"/assets/{asset_id}"
        result = await client.get(endpoint)
        
        return {
            "success": True,
            "asset": result
        }
    except Exception as e:
        logger.error(f"Get asset alert status error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_project_alert_status(
    project_id: int,
    exclude_non_modeled_points: bool = False
) -> Dict[str, Any]:
    """
    Get alert status for a project and its points.
    
    Returns basic alert state information about the project identified by
    the project ID, including all points and their runtime states.
    
    Args:
        project_id: Project ID (required)
        exclude_non_modeled_points: Exclude points not in the model
    
    Returns:
        Project alert status including all points
    """
    try:
        client = get_apa_client()
        
        params = {}
        if exclude_non_modeled_points:
            params["excludeNonModeledPoints"] = "true"
        
        result = await client.get(f"/projects/{project_id}", params=params)
        
        return {
            "success": True,
            "project": result
        }
    except Exception as e:
        logger.error(f"Get project alert status error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_point_alert_configuration(
    point_id: int
) -> Dict[str, Any]:
    """
    Get alert configuration for a specific point.
    
    Returns basic threshold information about the point identified by the PointID,
    including related output points and thresholds (High/Low Alert/Warning).
    
    Args:
        point_id: Point ID (required)
    
    Returns:
        Point configuration including output points and thresholds
    """
    try:
        client = get_apa_client()
        result = await client.get(f"/points/{point_id}")
        
        return {
            "success": True,
            "point": result
        }
    except Exception as e:
        logger.error(f"Get point alert configuration error: {str(e)}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MCP TOOLS - HISTORICAL DATA
# ============================================================================

@mcp.tool()
async def get_historical_data(
    point_ids: List[int],
    start_datetime: str,
    end_datetime: str,
    frequency_seconds: int = 60
) -> Dict[str, Any]:
    """
    Get historical time-series data for specified points.
    
    Retrieves actual values, predicted values, deviations, and OMR data
    from the Archive Database for specified project points and time range.
    
    Args:
        point_ids: List of point IDs to retrieve data for
        start_datetime: Start time in ISO 8601 format (UTC)
        end_datetime: End time in ISO 8601 format (UTC)
        frequency_seconds: Sample interval in seconds (default: 60)
    
    Returns:
        Historical data for each point with timestamps and values
    """
    try:
        client = get_apa_client()
        
        data = {
            "PointIds": point_ids,
            "StartDateTime": start_datetime,
            "EndDateTime": end_datetime,
            "FrequencySeconds": frequency_seconds
        }
        
        result = await client.post("/histdata", data=data)
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.error(f"Get historical data error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_omr_history(
    project_id: int,
    frequency_seconds: int,
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    Get Overall Model Residual (OMR) historical data for a project.
    
    Retrieves OMR time-series data from the Archive Database, which represents
    the aggregate health score of the operational profile.
    
    Args:
        project_id: Project ID
        frequency_seconds: Sample interval in seconds
        start_date: Start time in ISO 8601 format
        end_date: End time in ISO 8601 format
    
    Returns:
        OMR historical data with timestamps and values
    """
    try:
        client = get_apa_client()
        
        params = {
            "startDate": start_date,
            "endDate": end_date
        }
        
        result = await client.get(
            f"/HistoricalArchive/omr/{project_id}/{frequency_seconds}",
            params=params
        )
        
        return {
            "success": True,
            "omr_data": result
        }
    except Exception as e:
        logger.error(f"Get OMR history error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_output_points_history(
    input_point_ids: List[int],
    output_point_types: List[int],
    frequency_seconds: int,
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    Get output points historical data.
    
    Retrieves output point time-series data (predictions, deviations, contributions)
    from the Archive Database.
    
    Args:
        input_point_ids: List of input point IDs
        output_point_types: List of output point type codes (3=Actual, 4=Predicted, 5=Deviation)
        frequency_seconds: Sample interval in seconds
        start_date: Start time in ISO 8601 format
        end_date: End time in ISO 8601 format
    
    Returns:
        Output point historical data
    """
    try:
        client = get_apa_client()
        
        data = {
            "InputPointIDs": input_point_ids,
            "OutputPointTypes": output_point_types,
            "FrequencySeconds": frequency_seconds,
            "StartDate": start_date,
            "EndDate": end_date
        }
        
        result = await client.post("/HistoricalArchive/output-points", data=data)
        
        return {
            "success": True,
            "output_points_data": result
        }
    except Exception as e:
        logger.error(f"Get output points history error: {str(e)}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MCP TOOLS - ALERT MANAGEMENT
# ============================================================================

@mcp.tool()
async def get_alert_workflow_states() -> Dict[str, Any]:
    """
    Get all available alert workflow states.
    
    Returns the list of all alert workflow states defined in the system,
    along with their text descriptions, categories, modes, and importance levels.
    
    Returns:
        List of alert workflow states with their properties
    """
    try:
        client = get_apa_client()
        result = await client.get("/AlarmWorkFlowStates")
        
        return {
            "success": True,
            "states": result
        }
    except Exception as e:
        logger.error(f"Get alert workflow states error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_alert_clear_parameters() -> Dict[str, Any]:
    """
    Get allowed clear parameters for alert management.
    
    Returns lists of ClearTypes, ActionTypes, and ClassificationTypes
    that can be used when clearing alerts.
    
    Returns:
        Clear parameters organized by type
    """
    try:
        client = get_apa_client()
        result = await client.get("/AlarmWorkFlowStates/ClearParameters")
        
        return {
            "success": True,
            "clear_parameters": result
        }
    except Exception as e:
        logger.error(f"Get alert clear parameters error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def set_asset_alert_state(
    asset_id: int,
    state_id: int,
    notes: str = None,
    clear_type_id: int = None,
    action_type_id: int = None,
    classification_type_id: int = None,
    expiration_date_utc: str = None
) -> Dict[str, Any]:
    """
    Set alert workflow state for an asset.
    
    Changes the alert state for the specified asset. Different parameters
    are required based on the state being set:
    - Clear states (StateID=1): Require clear_type_id, action_type_id, classification_type_id
    - Pending/Deferred states: Require expiration_date_utc
    
    Args:
        asset_id: Asset ID
        state_id: Target state ID
        notes: Optional notes for the state change
        clear_type_id: Required for clear states
        action_type_id: Required for clear states
        classification_type_id: Required for clear states
        expiration_date_utc: Required for pending/deferred states
    
    Returns:
        Operation result
    """
    try:
        client = get_apa_client()
        
        data = {"StateID": state_id}
        if notes:
            data["Notes"] = notes
        if clear_type_id:
            data["ClearTypeID"] = clear_type_id
        if action_type_id:
            data["ActionTypeID"] = action_type_id
        if classification_type_id:
            data["ClassificationTypeID"] = classification_type_id
        if expiration_date_utc:
            data["ExpirationDateUtc"] = expiration_date_utc
        
        result = await client.post(f"/assets/{asset_id}/AlarmWorkFlowState", data=data)
        
        return {
            "success": True,
            "message": f"Asset {asset_id} alert state updated to {state_id}"
        }
    except Exception as e:
        logger.error(f"Set asset alert state error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def set_project_alert_state(
    project_id: int,
    state_id: int,
    notes: str = None,
    clear_type_id: int = None,
    action_type_id: int = None,
    classification_type_id: int = None,
    expiration_date_utc: str = None
) -> Dict[str, Any]:
    """
    Set alert workflow state for a project.
    
    Changes the alert state for the specified project.
    
    Args:
        project_id: Project ID
        state_id: Target state ID
        notes: Optional notes
        clear_type_id: Required for clear states
        action_type_id: Required for clear states
        classification_type_id: Required for clear states
        expiration_date_utc: Required for pending/deferred states
    
    Returns:
        Operation result
    """
    try:
        client = get_apa_client()
        
        data = {"StateID": state_id}
        if notes:
            data["Notes"] = notes
        if clear_type_id:
            data["ClearTypeID"] = clear_type_id
        if action_type_id:
            data["ActionTypeID"] = action_type_id
        if classification_type_id:
            data["ClassificationTypeID"] = classification_type_id
        if expiration_date_utc:
            data["ExpirationDateUtc"] = expiration_date_utc
        
        result = await client.post(f"/projects/{project_id}/AlarmWorkFlowState", data=data)
        
        return {
            "success": True,
            "message": f"Project {project_id} alert state updated to {state_id}"
        }
    except Exception as e:
        logger.error(f"Set project alert state error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def set_point_alert_state(
    point_id: int,
    state_id: int,
    notes: str = None,
    clear_type_id: int = None,
    action_type_id: int = None,
    classification_type_id: int = None,
    expiration_date_utc: str = None
) -> Dict[str, Any]:
    """
    Set alert workflow state for a point.
    
    Changes the alert state for the specified point.
    
    Args:
        point_id: Point ID
        state_id: Target state ID
        notes: Optional notes
        clear_type_id: Required for clear states
        action_type_id: Required for clear states
        classification_type_id: Required for clear states
        expiration_date_utc: Required for pending/deferred states
    
    Returns:
        Operation result
    """
    try:
        client = get_apa_client()
        
        data = {"StateID": state_id}
        if notes:
            data["Notes"] = notes
        if clear_type_id:
            data["ClearTypeID"] = clear_type_id
        if action_type_id:
            data["ActionTypeID"] = action_type_id
        if classification_type_id:
            data["ClassificationTypeID"] = classification_type_id
        if expiration_date_utc:
            data["ExpirationDateUtc"] = expiration_date_utc
        
        result = await client.post(f"/points/{point_id}/AlarmWorkFlowState", data=data)
        
        return {
            "success": True,
            "message": f"Point {point_id} alert state updated to {state_id}"
        }
    except Exception as e:
        logger.error(f"Set point alert state error: {str(e)}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MCP TOOLS - ALERT THRESHOLDS
# ============================================================================

@mcp.tool()
async def add_alert_threshold(
    project_point_id: int,
    alert_threshold_type: int,
    threshold_value: float = None,
    persistence_denomination: int = 0,
    minimum_count: int = 1,
    seconds_or_event_count: int = 60,
    note: str = None,
    is_critical: bool = False
) -> Dict[str, Any]:
    """
    Add a new threshold to a project point or OMR.
    
    Creates one or more alert thresholds for monitoring point deviations.
    
    Args:
        project_point_id: Project Point ID
        alert_threshold_type: Type (1=HighAlert, 2=LowAlert, 3=HighWarning, 4=LowWarning)
        threshold_value: Threshold value in engineering units
        persistence_denomination: Persistence type (0=Seconds, 1=Events)
        minimum_count: Minimum count for persistence
        seconds_or_event_count: Time or event count for persistence window
        note: Optional note
        is_critical: Whether this is a critical threshold
    
    Returns:
        Operation result
    """
    try:
        client = get_apa_client()
        
        data = [{
            "ProjectPointId": project_point_id,
            "AlertThresholdType": alert_threshold_type,
            "ThresholdValue": threshold_value,
            "PersistenceDenomination": persistence_denomination,
            "MinimumCount": minimum_count,
            "SecondsOrEventCount": seconds_or_event_count,
            "Note": note,
            "IsCritical": is_critical
        }]
        
        result = await client.put("/AlertThresholds/new-point-thresholds", data=data)
        
        return {
            "success": True,
            "message": "Threshold created successfully"
        }
    except Exception as e:
        logger.error(f"Add alert threshold error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def update_alert_threshold(
    threshold_id: int,
    alert_threshold_type: int,
    threshold_value: float = None,
    persistence_denomination: int = 0,
    minimum_count: int = 1,
    seconds_or_event_count: int = 60,
    note: str = None,
    is_critical: bool = False,
    is_active: bool = True
) -> Dict[str, Any]:
    """
    Update an existing alert threshold.
    
    Modifies threshold parameters for an existing threshold.
    
    Args:
        threshold_id: Threshold ID to update
        alert_threshold_type: Type (1=HighAlert, 2=LowAlert, 3=HighWarning, 4=LowWarning)
        threshold_value: New threshold value
        persistence_denomination: Persistence type
        minimum_count: Minimum count for persistence
        seconds_or_event_count: Time or event count
        note: Optional note
        is_critical: Whether this is critical
        is_active: Whether threshold is active
    
    Returns:
        Operation result
    """
    try:
        client = get_apa_client()
        
        data = [{
            "ThresholdId": threshold_id,
            "AlertThresholdType": alert_threshold_type,
            "ThresholdValue": threshold_value,
            "PersistenceDenomination": persistence_denomination,
            "MinimumCount": minimum_count,
            "SecondsOrEventCount": seconds_or_event_count,
            "Note": note,
            "IsCritical": is_critical,
            "IsActive": is_active
        }]
        
        result = await client.put("/AlertThresholds/thresholds", data=data)
        
        return {
            "success": True,
            "message": f"Threshold {threshold_id} updated successfully"
        }
    except Exception as e:
        logger.error(f"Update alert threshold error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def delete_alert_threshold(
    threshold_ids: List[int]
) -> Dict[str, Any]:
    """
    Delete one or more alert thresholds.
    
    Permanently removes thresholds from points or OMR.
    This action cannot be undone.
    
    Args:
        threshold_ids: List of threshold IDs to delete
    
    Returns:
        Operation result
    """
    try:
        client = get_apa_client()
        
        params = {"thresholdIds": threshold_ids}
        result = await client.delete("/AlertThresholds/thresholds", params=params)
        
        return {
            "success": True,
            "message": f"Deleted {len(threshold_ids)} threshold(s)"
        }
    except Exception as e:
        logger.error(f"Delete alert threshold error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_threshold_by_id(
    threshold_id: int
) -> Dict[str, Any]:
    """
    Get threshold information by threshold ID.
    
    Args:
        threshold_id: Threshold ID
    
    Returns:
        Threshold details
    """
    try:
        client = get_apa_client()
        result = await client.get(f"/AlertThresholds/threshold/{threshold_id}")
        
        return {
            "success": True,
            "threshold": result
        }
    except Exception as e:
        logger.error(f"Get threshold error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_thresholds_by_point(
    point_id: int
) -> Dict[str, Any]:
    """
    Get all thresholds for a specific point.
    
    Args:
        point_id: Point ID
    
    Returns:
        List of thresholds for the point
    """
    try:
        client = get_apa_client()
        result = await client.get(f"/AlertThresholds/point-thresholds/{point_id}")
        
        return {
            "success": True,
            "thresholds": result
        }
    except Exception as e:
        logger.error(f"Get thresholds by point error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def restore_template_thresholds(
    threshold_ids: List[int]
) -> Dict[str, Any]:
    """
    Restore template-based project thresholds to template values.
    
    Resets modified threshold values back to their original template defaults.
    
    Args:
        threshold_ids: List of threshold IDs to restore
    
    Returns:
        Operation result
    """
    try:
        client = get_apa_client()
        
        params = {"thresholdIds": threshold_ids}
        result = await client.post("/AlertThresholds/template-references-reset", data=params)
        
        return {
            "success": True,
            "message": f"Restored {len(threshold_ids)} threshold(s) to template values"
        }
    except Exception as e:
        logger.error(f"Restore template thresholds error: {str(e)}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MCP TOOLS - FAULT DIAGNOSTICS
# ============================================================================

@mcp.tool()
async def get_fault_diagnostic(
    fault_diagnostic_id: int
) -> Dict[str, Any]:
    """
    Get fault diagnostic details by ID.
    
    Retrieves description, next steps, and user-defined properties for a fault.
    
    Args:
        fault_diagnostic_id: Fault diagnostic ID
    
    Returns:
        Fault diagnostic details
    """
    try:
        client = get_apa_client()
        result = await client.get(f"/FaultDiagnostic?faultDiagnosticId={fault_diagnostic_id}")
        
        return {
            "success": True,
            "fault_diagnostic": result
        }
    except Exception as e:
        logger.error(f"Get fault diagnostic error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_fault_diagnostics_for_project(
    project_id: int,
    frequency_seconds: int,
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    Get fault diagnostics for a project with time series data.
    
    Retrieves fault match information based on ID, frequency, and time span.
    
    Args:
        project_id: Project ID
        frequency_seconds: Sample frequency in seconds
        start_date: Start time in ISO 8601 format
        end_date: End time in ISO 8601 format
    
    Returns:
        Fault diagnostics with match percentages
    """
    try:
        client = get_apa_client()
        
        params = {
            "startDate": start_date,
            "endDate": end_date
        }
        
        result = await client.get(
            f"/FaultDiagnostic/project/{project_id}/{frequency_seconds}",
            params=params
        )
        
        return {
            "success": True,
            "fault_diagnostics": result
        }
    except Exception as e:
        logger.error(f"Get fault diagnostics for project error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_fault_diagnostics_with_recent_match(
    project_id: int,
    frequency_seconds: int,
    recent_match_percentage: float,
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    Get fault diagnostics with recent match percentage filter.
    
    Retrieves fault information filtered by recent match percentage.
    
    Args:
        project_id: Project ID
        frequency_seconds: Sample frequency
        recent_match_percentage: Minimum recent match percentage (0-100)
        start_date: Start time
        end_date: End time
    
    Returns:
        Filtered fault diagnostics
    """
    try:
        client = get_apa_client()
        
        params = {
            "startDate": start_date,
            "endDate": end_date
        }
        
        result = await client.get(
            f"/FaultDiagnostic/project/{project_id}/{frequency_seconds}/{recent_match_percentage}",
            params=params
        )
        
        return {
            "success": True,
            "fault_diagnostics": result
        }
    except Exception as e:
        logger.error(f"Get fault diagnostics with recent match error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_fault_details(
    project_ids: List[int],
    frequency_seconds: int,
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    Get detailed fault diagnostics for multiple projects.
    
    Retrieves fault and fault signature information for up to 5 projects.
    
    Args:
        project_ids: List of project IDs (max 5)
        frequency_seconds: Sample frequency
        start_date: Start time
        end_date: End time
    
    Returns:
        Detailed fault information for specified projects
    """
    try:
        if len(project_ids) > 5:
            return {"success": False, "error": "Maximum 5 project IDs allowed"}
        
        client = get_apa_client()
        
        data = {
            "ProjectIds": project_ids,
            "FrequencySeconds": frequency_seconds,
            "StartDate": start_date,
            "EndDate": end_date
        }
        
        result = await client.post("/FaultDiagnostic/fault-details", data=data)
        
        return {
            "success": True,
            "fault_details": result
        }
    except Exception as e:
        logger.error(f"Get fault details error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_fault_summary(
    project_id: int,
    fault_ids: List[int],
    frequency_seconds: int,
    recent_match_percentage: float,
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    Get fault diagnostic summary with fault signatures.
    
    Retrieves comprehensive fault and signature information.
    
    Args:
        project_id: Project ID
        fault_ids: List of fault IDs to include
        frequency_seconds: Sample frequency
        recent_match_percentage: Recent match percentage filter
        start_date: Start time
        end_date: End time
    
    Returns:
        Fault summary with signatures
    """
    try:
        client = get_apa_client()
        
        params = {
            "ProjectId": project_id,
            "FaultIds": fault_ids,
            "FrequencySeconds": frequency_seconds,
            "RecentMatchPercentage": recent_match_percentage,
            "StartDate": start_date,
            "EndDate": end_date
        }
        
        result = await client.get("/FaultDiagnostic/summary", params=params)
        
        return {
            "success": True,
            "fault_summary": result
        }
    except Exception as e:
        logger.error(f"Get fault summary error: {str(e)}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MCP TOOLS - FORECAST
# ============================================================================

@mcp.tool()
async def get_forecast(
    project_point_id: int,
    fitted_values_start: str = None,
    fitted_values_end: str = None,
    forecast_values_start: str = None,
    forecast_values_end: str = None,
    record_count: int = 100
) -> Dict[str, Any]:
    """
    Get forecast predictions for a project point.
    
    Retrieves future value predictions based on past behavior and current conditions.
    
    Args:
        project_point_id: Project point ID
        fitted_values_start: Start time for fitted values
        fitted_values_end: End time for fitted values
        forecast_values_start: Start time for forecast
        forecast_values_end: End time for forecast
        record_count: Number of records to return
    
    Returns:
        Forecast data including predictions, upper/lower limits
    """
    try:
        client = get_apa_client()
        
        data = {
            "ProjectPointId": project_point_id,
            "FittedValues": {
                "Predictions": {
                    "Start": fitted_values_start,
                    "End": fitted_values_end,
                    "RecordCount": record_count
                },
                "UpperLimit": {
                    "Start": fitted_values_start,
                    "End": fitted_values_end,
                    "RecordCount": record_count
                },
                "LowerLimit": {
                    "Start": fitted_values_start,
                    "End": fitted_values_end,
                    "RecordCount": record_count
                }
            },
            "ForecastValues": {
                "Predictions": {
                    "Start": forecast_values_start,
                    "End": forecast_values_end,
                    "RecordCount": record_count
                },
                "UpperLimit": {
                    "Start": forecast_values_start,
                    "End": forecast_values_end,
                    "RecordCount": record_count
                },
                "LowerLimit": {
                    "Start": forecast_values_start,
                    "End": forecast_values_end,
                    "RecordCount": record_count
                }
            }
        }
        
        result = await client.post("/Forecast", data=data)
        
        return {
            "success": True,
            "forecast": result
        }
    except Exception as e:
        logger.error(f"Get forecast error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_forecast_deployment_parameters(
    forecast_model_id: int
) -> Dict[str, Any]:
    """
    Get deployment parameters for a forecast model.
    
    Args:
        forecast_model_id: Forecast model ID
    
    Returns:
        Deployment parameters
    """
    try:
        client = get_apa_client()
        result = await client.get(f"/Forecast/deploymentParameters/{forecast_model_id}")
        
        return {
            "success": True,
            "deployment_parameters": result
        }
    except Exception as e:
        logger.error(f"Get forecast deployment parameters error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def save_forecast_deployment_parameters(
    project_point_id: int
) -> Dict[str, Any]:
    """
    Save deployment parameters for a project point.
    
    Args:
        project_point_id: Project point ID
    
    Returns:
        Operation result
    """
    try:
        client = get_apa_client()
        result = await client.post(f"/Forecast/deploymentParameters/{project_point_id}")
        
        return {
            "success": True,
            "message": "Deployment parameters saved"
        }
    except Exception as e:
        logger.error(f"Save forecast deployment parameters error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def delete_forecast_model(
    forecast_model_id: int
) -> Dict[str, Any]:
    """
    Delete a forecast model.
    
    This action cannot be undone.
    
    Args:
        forecast_model_id: Forecast model ID
    
    Returns:
        Operation result
    """
    try:
        client = get_apa_client()
        result = await client.delete(f"/Forecast/{forecast_model_id}")
        
        return {
            "success": True,
            "message": f"Forecast model {forecast_model_id} deleted"
        }
    except Exception as e:
        logger.error(f"Delete forecast model error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def retrain_forecast_model(
    forecast_model_id: int
) -> Dict[str, Any]:
    """
    Retrain a forecast model and update deployment parameters.
    
    Args:
        forecast_model_id: Forecast model ID
    
    Returns:
        Operation result
    """
    try:
        client = get_apa_client()
        result = await client.post(f"/Forecast/retrainForecastModel/{forecast_model_id}")
        
        return {
            "success": True,
            "message": f"Forecast model {forecast_model_id} retrained"
        }
    except Exception as e:
        logger.error(f"Retrain forecast model error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_deployed_model_results(
    forecast_model_id: int,
    evaluated_time: str = None,
    total_data_points: int = 100
) -> Dict[str, Any]:
    """
    Get deployed forecast model results from Archive Database.
    
    Args:
        forecast_model_id: Forecast model ID
        evaluated_time: Evaluation time
        total_data_points: Number of data points to return
    
    Returns:
        Deployed model results
    """
    try:
        client = get_apa_client()
        
        params = {
            "ForecastModelId": forecast_model_id,
            "totalDataPoints": total_data_points
        }
        if evaluated_time:
            params["evaluatedTime"] = evaluated_time
        
        result = await client.get("/Forecast/deployed-model-results", params=params)
        
        return {
            "success": True,
            "results": result
        }
    except Exception as e:
        logger.error(f"Get deployed model results error: {str(e)}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MCP TOOLS - SENSORS
# ============================================================================

@mcp.tool()
async def get_sensors(
    id: int,
    results_type: int = 0,
    results_format: List[int] = None,
    filters: List[int] = None
) -> Dict[str, Any]:
    """
    Get sensor information.
    
    Retrieves a list of points with sensor-based alerts in list or summary format.
    
    Args:
        id: Asset or project ID
        results_type: 0=All, 1=InAlert, 2=NotInAlert
        results_format: Format types (0=List, 1=Summary)
        filters: Optional filter IDs
    
    Returns:
        Sensor information
    """
    try:
        client = get_apa_client()
        
        data = {
            "ID": id,
            "ResultsType": results_type,
            "ResultsFormat": results_format or [0]
        }
        if filters:
            data["Filters"] = filters
        
        result = await client.post("/Sensors", data=data)
        
        return {
            "success": True,
            "sensors": result
        }
    except Exception as e:
        logger.error(f"Get sensors error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_sensors_in_alert(
    point_ids: List[int]
) -> Dict[str, Any]:
    """
    Get list of sensors in alert state.
    
    Args:
        point_ids: List of point IDs to check
    
    Returns:
        Sensors in alert state
    """
    try:
        client = get_apa_client()
        
        params = {"ids": point_ids}
        result = await client.get("/Sensors/point-selector", params=params)
        
        return {
            "success": True,
            "sensors_in_alert": result
        }
    except Exception as e:
        logger.error(f"Get sensors in alert error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def change_sensor_alert_state(
    point_ids: List[int],
    alert_managed_state: int,
    defer_date_utc: str = None,
    assigned_to_user_id: str = None,
    update_assign_to: bool = False
) -> Dict[str, Any]:
    """
    Change sensor alert state.
    
    Updates the alert state for one or more sensor points.
    
    Args:
        point_ids: List of point IDs
        alert_managed_state: Target state
        defer_date_utc: Defer date for deferred states
        assigned_to_user_id: User ID to assign to
        update_assign_to: Whether to update assignment
    
    Returns:
        Operation result
    """
    try:
        client = get_apa_client()
        
        data = {
            "IDs": point_ids,
            "AlertManagedState": alert_managed_state
        }
        if defer_date_utc:
            data["DeferDateUtc"] = defer_date_utc
        if assigned_to_user_id:
            data["AssignedToUserId"] = assigned_to_user_id
        data["UpdateAssignTo"] = update_assign_to
        
        result = await client.post("/Sensors/alert-state", data=data)
        
        return {
            "success": True,
            "message": f"Updated alert state for {len(point_ids)} sensor(s)"
        }
    except Exception as e:
        logger.error(f"Change sensor alert state error: {str(e)}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MCP TOOLS - HISTORIAN POINTS
# ============================================================================

@mcp.tool()
async def get_historian_points(
    point_ids: List[int]
) -> Dict[str, Any]:
    """
    Get historian point information.
    
    Retrieves information about historian points (project points linked to online historian).
    
    Args:
        point_ids: List of historian point IDs
    
    Returns:
        Historian point information
    """
    try:
        client = get_apa_client()
        
        params = {"ids": point_ids}
        result = await client.get("/HistorianPoints", params=params)
        
        return {
            "success": True,
            "historian_points": result
        }
    except Exception as e:
        logger.error(f"Get historian points error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def update_historian_points(
    points: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Update historian point settings.
    
    Modifies historian point properties like flatline time, out-of-range limits, etc.
    
    Args:
        points: List of point update objects containing:
            - ID: Point ID (required)
            - FlatlineTimeMinutes: Flatline detection time
            - HighOutOfRangeLimit: High limit
            - LowOutOfRangeLimit: Low limit
            - ManualOverride: Override flag
            - RecoveryTimeMinutes: Recovery time
            - Status: Point status
            - Description: Point description
            - DigitalGroupId: Digital group ID
            - ExtendedDescription: Extended description
            - ExtendedId: Extended ID
            - Units: Engineering units
    
    Returns:
        Operation result
    """
    try:
        client = get_apa_client()
        result = await client.put("/HistorianPoints", data=points)
        
        return {
            "success": True,
            "message": f"Updated {len(points)} historian point(s)"
        }
    except Exception as e:
        logger.error(f"Update historian points error: {str(e)}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MCP TOOLS - CALCULATION POINTS
# ============================================================================

@mcp.tool()
async def get_calculation_points(
    point_ids: List[int]
) -> Dict[str, Any]:
    """
    Get calculation point information.
    
    Retrieves information about calculation points (derived formula points).
    
    Args:
        point_ids: List of calculation point IDs
    
    Returns:
        Calculation point information
    """
    try:
        client = get_apa_client()
        
        params = {"ids": point_ids}
        result = await client.get("/CalculationPoints", params=params)
        
        return {
            "success": True,
            "calculation_points": result
        }
    except Exception as e:
        logger.error(f"Get calculation points error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def update_calculation_points(
    points: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Update calculation point settings.
    
    Modifies calculation point properties.
    
    Args:
        points: List of point update objects containing:
            - ID: Point ID (required)
            - Description: Point description
            - DigitalGroupId: Digital group ID
            - ExtendedDescription: Extended description
            - ExtendedId: Extended ID
            - Units: Engineering units
    
    Returns:
        Operation result
    """
    try:
        client = get_apa_client()
        result = await client.put("/CalculationPoints", data=points)
        
        return {
            "success": True,
            "message": f"Updated {len(points)} calculation point(s)"
        }
    except Exception as e:
        logger.error(f"Update calculation points error: {str(e)}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MCP TOOLS - DIGITAL GROUPS
# ============================================================================

@mcp.tool()
async def get_digital_groups() -> Dict[str, Any]:
    """
    Get list of digital point groups.
    
    Retrieves all digital point groups that can be used for project points.
    
    Returns:
        List of digital point groups
    """
    try:
        client = get_apa_client()
        result = await client.get("/DigitalGroups")
        
        return {
            "success": True,
            "digital_groups": result
        }
    except Exception as e:
        logger.error(f"Get digital groups error: {str(e)}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MCP TOOLS - PROJECTS
# ============================================================================

@mcp.tool()
async def get_output_points_archive_statuses(
    project_ids: List[int]
) -> Dict[str, Any]:
    """
    Get output point archive statuses for projects.
    
    Retrieves the types of output points being archived for specified projects.
    
    Args:
        project_ids: List of project IDs
    
    Returns:
        Output point archive statuses
    """
    try:
        client = get_apa_client()
        
        params = {"projectIds": project_ids}
        result = await client.get("/Project/output-points-archive-statuses", params=params)
        
        return {
            "success": True,
            "archive_statuses": result
        }
    except Exception as e:
        logger.error(f"Get output points archive statuses error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_training_dataset_by_project(
    project_id: int
) -> Dict[str, Any]:
    """
    Get training dataset information for a project.
    
    Args:
        project_id: Project ID
    
    Returns:
        Training dataset information
    """
    try:
        client = get_apa_client()
        
        params = {"projectId": project_id}
        result = await client.get("/Project", params=params)
        
        return {
            "success": True,
            "training_dataset": result
        }
    except Exception as e:
        logger.error(f"Get training dataset by project error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_training_dataset(
    dataset_id: int
) -> Dict[str, Any]:
    """
    Get training dataset information by dataset ID.
    
    Args:
        dataset_id: Dataset ID
    
    Returns:
        Training dataset information
    """
    try:
        client = get_apa_client()
        
        params = {"dataSetId": dataset_id}
        result = await client.get("/Project/training-dataset", params=params)
        
        return {
            "success": True,
            "training_dataset": result
        }
    except Exception as e:
        logger.error(f"Get training dataset error: {str(e)}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MCP TOOLS - AUDIT
# ============================================================================

@mcp.tool()
async def get_audit_users() -> Dict[str, Any]:
    """
    Get list of users who have records in audit history.
    
    Returns:
        List of users with audit records
    """
    try:
        client = get_apa_client()
        result = await client.get("/Audit/Get-Audit-Lookup-Users")
        
        return {
            "success": True,
            "users": result
        }
    except Exception as e:
        logger.error(f"Get audit users error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_audit_categories() -> Dict[str, Any]:
    """
    Get list of auditing categories (entity types).
    
    Returns:
        List of audit categories
    """
    try:
        client = get_apa_client()
        result = await client.get("/Audit/Get-Audit-Lookup-EntityTypes")
        
        return {
            "success": True,
            "categories": result
        }
    except Exception as e:
        logger.error(f"Get audit categories error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_audit_history(
    audit_entity_type: int = -1,
    user_sid: str = "-1",
    start_date: str = None,
    end_date: str = None,
    search_text: str = None,
    page_number: int = 1,
    rows_per_page: int = 50
) -> Dict[str, Any]:
    """
    Get audit history records.
    
    Retrieves audit records with optional filtering.
    
    Args:
        audit_entity_type: Entity type filter (-1 for all)
        user_sid: User SID filter (-1 for all)
        start_date: Start date filter
        end_date: End date filter
        search_text: Text search filter
        page_number: Page number (1-based)
        rows_per_page: Records per page
    
    Returns:
        Paginated audit history
    """
    try:
        client = get_apa_client()
        
        params = {
            "AuditEntityTypeEnum": audit_entity_type,
            "UserSid": user_sid,
            "StartDate": start_date or "",
            "EndDate": end_date or "",
            "SearchText": search_text or "",
            "PageNumber": page_number,
            "RowsPerPage": rows_per_page
        }
        
        result = await client.get("/Audit/Get-Audit-Grid-Data", params=params)
        
        return {
            "success": True,
            "audit_history": result
        }
    except Exception as e:
        logger.error(f"Get audit history error: {str(e)}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MCP TOOLS - USER DEFINED PROPERTIES
# ============================================================================

@mcp.tool()
async def get_user_defined_properties(
    property_type_ids: List[int]
) -> Dict[str, Any]:
    """
    Get user-defined property details.
    
    Retrieves details for specified user-defined property types.
    
    Args:
        property_type_ids: List of property type IDs
    
    Returns:
        User-defined property details
    """
    try:
        client = get_apa_client()
        
        params = {"userDefinedPropertyTypeIds": property_type_ids}
        result = await client.get("/UserDefinedProperty", params=params)
        
        return {
            "success": True,
            "properties": result
        }
    except Exception as e:
        logger.error(f"Get user defined properties error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def create_user_defined_property(
    user_defined_property_type_id: int,
    name: str,
    is_enabled: bool = True,
    display_order: int = 0,
    numeric_value: float = None,
    text_value: str = None,
    system_classification: int = 0
) -> Dict[str, Any]:
    """
    Create a new user-defined property detail.
    
    Args:
        user_defined_property_type_id: Parent type ID
        name: Property name
        is_enabled: Whether property is enabled
        display_order: Display order
        numeric_value: Numeric value (for numeric types)
        text_value: Text value (for text types)
        system_classification: System classification code
    
    Returns:
        Operation result
    """
    try:
        client = get_apa_client()
        
        data = {
            "UserDefinedPropertyTypeId": user_defined_property_type_id,
            "Name": name,
            "IsEnabled": is_enabled,
            "DisplayOrder": display_order,
            "SystemClassification": system_classification
        }
        if numeric_value is not None:
            data["NumericValue"] = numeric_value
        if text_value is not None:
            data["TextValue"] = text_value
        
        result = await client.post("/UserDefinedProperty/new-userdefinedproperty", data=data)
        
        return {
            "success": True,
            "message": "User-defined property created"
        }
    except Exception as e:
        logger.error(f"Create user defined property error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def update_user_defined_property(
    property_id: int,
    name: str = None,
    is_enabled: bool = None,
    display_order: int = None,
    numeric_value: float = None,
    text_value: str = None
) -> Dict[str, Any]:
    """
    Update a user-defined property detail.
    
    Args:
        property_id: Property detail ID
        name: New name
        is_enabled: Enabled status
        display_order: Display order
        numeric_value: New numeric value
        text_value: New text value
    
    Returns:
        Operation result
    """
    try:
        client = get_apa_client()
        
        data = [{"ID": property_id}]
        if name is not None:
            data[0]["Name"] = name
        if is_enabled is not None:
            data[0]["IsEnabled"] = is_enabled
        if display_order is not None:
            data[0]["DisplayOrder"] = display_order
        if numeric_value is not None:
            data[0]["NumericValue"] = numeric_value
        if text_value is not None:
            data[0]["TextValue"] = text_value
        
        result = await client.put("/UserDefinedProperty", data=data)
        
        return {
            "success": True,
            "message": f"Updated user-defined property {property_id}"
        }
    except Exception as e:
        logger.error(f"Update user defined property error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def delete_user_defined_property(
    property_id: int
) -> Dict[str, Any]:
    """
    Delete a user-defined property detail.
    
    This action cannot be undone.
    
    Args:
        property_id: Property detail ID to delete
    
    Returns:
        Operation result
    """
    try:
        client = get_apa_client()
        result = await client.delete(f"/UserDefinedProperty/{property_id}")
        
        return {
            "success": True,
            "message": f"Deleted user-defined property {property_id}"
        }
    except Exception as e:
        logger.error(f"Delete user defined property error: {str(e)}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_user_defined_property_types(
    category_id: int = None
) -> Dict[str, Any]:
    """
    Get user-defined property types.
    
    Retrieves all property types, optionally filtered by category.
    
    Args:
        category_id: Optional category ID filter
    
    Returns:
        User-defined property types
    """
    try:
        client = get_apa_client()
        
        params = {}
        if category_id is not None:
            params["categoryId"] = category_id
        
        result = await client.get("/UserDefinedPropertyType", params=params)
        
        return {
            "success": True,
            "property_types": result
        }
    except Exception as e:
        logger.error(f"Get user defined property types error: {str(e)}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MCP TOOLS - SYSTEM HEALTH
# ============================================================================

@mcp.tool()
async def get_apa_system_health() -> Dict[str, Any]:
    """
    Get comprehensive AVEVA Predictive Analytics system health.
    
    Returns system status including authentication state, server uptime,
    and last known errors.
    
    Returns:
        System health information
    """
    try:
        health_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "server_state": server_state,
            "uptime_seconds": (datetime.now() - server_state["startup_time"]).total_seconds(),
            "config": {
                "base_url": config.apa.base_url,
                "api_version": config.apa.api_version,
                "verify_ssl": config.apa.verify_ssl
            }
        }
        
        # Test authentication
        client = get_apa_client()
        if client._access_token:
            health_data["authentication"] = {
                "authenticated": True,
                "token_expires_at": client._token_expires_at.isoformat() if client._token_expires_at else None
            }
        else:
            health_data["authentication"] = {
                "authenticated": False
            }
        
        # Try to get root asset to verify API connectivity
        try:
            root_asset = await client.get("/assets")
            health_data["api_status"] = "connected"
            health_data["root_asset"] = root_asset.get("Description", "Available")
        except Exception as e:
            health_data["api_status"] = "error"
            health_data["api_error"] = str(e)
        
        return health_data
        
    except Exception as e:
        logger.error(f"Get system health error: {str(e)}")
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "error",
            "error": str(e)
        }


# ============================================================================
# MCP PROMPTS
# ============================================================================

@mcp.prompt()
async def anomaly_investigation(
    project_name: str,
    point_names: List[str],
    time_period: str = "24h"
) -> str:
    """
    Generate a prompt for investigating anomalies in PA project.
    
    Args:
        project_name: Name of the PA project
        point_names: List of point names showing anomalies
        time_period: Time period to analyze
    """
    points_list = ", ".join(point_names)
    
    return f"""
Investigate anomaly detection results for the AVEVA Predictive Analytics project: {project_name}

The following points are showing deviations over the last {time_period}:
{points_list}

Please analyze:
1. **Deviation Patterns**
   - What is the magnitude and direction of deviations?
   - Are the deviations persistent or intermittent?
   - Are multiple points deviating together (correlated)?

2. **Contribution Analysis**
   - Which points are contributing most to the OMR?
   - Are the contributions positive or negative?
   - What does the deviation pattern suggest about the root cause?

3. **Fault Signature Matching**
   - Do the deviations match any known fault signatures?
   - What is the confidence level of any matches?
   - What are the recommended next steps from fault diagnostics?

4. **Historical Context**
   - Has this pattern occurred before?
   - Were there any operational changes preceding the deviation?
   - How does current behavior compare to the training period?

5. **Recommended Actions**
   - What immediate actions should be taken?
   - Which equipment or process areas need attention?
   - Should alerts be acknowledged, investigated, or cleared?

Provide a prioritized action plan based on the analysis.
"""


@mcp.prompt()
async def alert_management_workflow(
    resource_type: str,
    resource_id: int,
    current_state: str
) -> str:
    """
    Generate a prompt for managing alert workflow.
    
    Args:
        resource_type: Type of resource (asset, project, or point)
        resource_id: ID of the resource
        current_state: Current alert state
    """
    return f"""
Manage alert workflow for {resource_type} ID: {resource_id}

Current State: {current_state}

Please help determine the appropriate alert state transition:

1. **State Assessment**
   - Is the current alert state appropriate?
   - What evidence supports keeping or changing the state?
   - Are there any pending investigations or actions?

2. **Available Transitions**
   Based on the alert workflow states, determine valid transitions:
   - Clear (StateID 1) - Requires clear type, action type, and classification
   - Pending - Requires expiration date
   - Deferred - Requires expiration date
   - Other operational states

3. **Required Information**
   For state transitions, identify:
   - Notes to document the decision
   - Clear type selection (if clearing)
   - Action type selection (if clearing)
   - Classification type selection (if clearing)
   - Expiration date (if deferring)

4. **Documentation**
   - What should be recorded in the audit trail?
   - Are there any case management actions needed?
   - Should related alerts be updated together?

5. **Follow-up Actions**
   - What monitoring should continue?
   - When should this alert be reviewed again?
   - Are there any notifications to send?

Provide specific recommendations for managing this alert.
"""


@mcp.prompt()
async def forecast_analysis(
    project_point_name: str,
    forecast_horizon: str = "7 days"
) -> str:
    """
    Generate a prompt for analyzing forecast predictions.
    
    Args:
        project_point_name: Name of the project point
        forecast_horizon: Time horizon for forecast
    """
    return f"""
Analyze forecast predictions for project point: {project_point_name}

Forecast Horizon: {forecast_horizon}

Please provide analysis covering:

1. **Forecast Summary**
   - What is the predicted trend (increasing, decreasing, stable)?
   - What are the predicted values and their confidence intervals?
   - Are there any significant changes expected?

2. **Model Quality**
   - How well does the fitted model match historical data?
   - What is the uncertainty range of predictions?
   - Are there any periods with lower confidence?

3. **Threshold Analysis**
   - Will predicted values approach or exceed alert thresholds?
   - When might threshold violations occur?
   - What is the probability of threshold exceedance?

4. **Operational Implications**
   - What operational adjustments might be needed?
   - Are there any maintenance windows to plan around?
   - Should any preventive actions be taken?

5. **Model Recommendations**
   - Should the forecast model be retrained?
   - Are deployment parameters appropriate?
   - What additional data might improve predictions?

Provide actionable insights based on the forecast analysis.
"""


@mcp.prompt()
async def pa_system_health_check() -> str:
    """Generate a prompt for comprehensive PA system health assessment."""
    return """
Perform a comprehensive AVEVA Predictive Analytics system health assessment.

Please analyze:

1. **Authentication & Connectivity**
   - Is the API accessible and authenticated?
   - Are there any connection issues or timeouts?
   - Is the token valid and refreshing properly?

2. **Asset Hierarchy Review**
   - What is the overall structure of monitored assets?
   - How many projects are deployed and running?
   - Are there any projects with issues?

3. **Alert Status Summary**
   - How many assets/projects are in each alert state?
   - What is the distribution of alert severities?
   - Are there any stale or unmanaged alerts?

4. **Model Performance**
   - Are operational profiles executing properly?
   - Is OMR data being archived correctly?
   - Are there any projects with persistent high OMR?

5. **Data Quality**
   - Are historian connections working?
   - Is data flowing for all monitored points?
   - Are there any flatline or out-of-range issues?

6. **Recommendations**
   - What immediate actions are needed?
   - Are there any system configuration improvements?
   - What should be monitored going forward?

Provide a prioritized summary of system health and action items.
"""


# ============================================================================
# SERVER INITIALIZATION AND MAIN
# ============================================================================

async def initialize_server():
    """Initialize the MCP server"""
    logger.info("Initializing AVEVA Predictive Analytics MCP server...")
    
    try:
        # Test authentication
        client = get_apa_client()
        if await client.authenticate():
            logger.info("✅ Successfully authenticated with PA Web API")
            server_state["authenticated"] = True
        else:
            logger.warning("⚠️ Initial authentication failed - tools will require authentication")
        
        server_state["initialization_complete"] = True
        logger.info("✅ Server initialization completed")
        
    except Exception as e:
        error_msg = f"Server initialization error: {str(e)}"
        logger.error(error_msg)
        server_state["last_error"] = error_msg
        server_state["initialization_complete"] = True


async def cleanup():
    """Cleanup function for shutdown"""
    logger.info("Starting cleanup...")
    await cleanup_clients()
    logger.info("Cleanup completed")


if __name__ == "__main__":
    # Validate configuration
    if not config.apa.base_url:
        logger.error("APA_BASE_URL environment variable is required")
        exit(1)
    
    logger.info("Starting AVEVA Predictive Analytics MCP Server...")
    logger.info(f"API URL: {config.apa.base_url}")
    logger.info(f"API Version: {config.apa.api_version}")
    logger.info(f"SSL Verification: {config.apa.verify_ssl}")
    
    try:
        # Run the server
        mcp.run(transport="http", host=config.server_host, port=config.server_port)
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(cleanup())
            loop.close()
        except Exception as cleanup_error:
            logger.error(f"Cleanup error: {cleanup_error}")
    except Exception as e:
        logger.error(f"Server error: {e}")
        exit(1)
