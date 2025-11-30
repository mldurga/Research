"""
PI Web API Client - REST API client for AVEVA PI Web API
Fallback option when AF SDK is not available
"""

from typing import List, Dict, Any, Optional
import httpx
from loguru import logger

from app.core.config import settings


class PIWebAPIClient:
    """Client for interacting with AVEVA PI System via PI Web API"""

    def __init__(self):
        """Initialize PI Web API client"""
        self.base_url = settings.pi_webapi.base_url.rstrip("/")
        self.auth_mode = settings.pi_webapi.auth_mode
        self.verify_ssl = settings.pi_webapi.verify_ssl

        # Setup authentication
        self.auth = None
        if self.auth_mode == "basic":
            self.auth = (settings.pi_webapi.username, settings.pi_webapi.password)

        # Create httpx client
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=self.auth,
            verify=self.verify_ssl,
            timeout=30.0,
        )

        logger.info(f"PI Web API client initialized: {self.base_url}")

    async def get_dataservers(self) -> List[Dict[str, Any]]:
        """Get list of PI Data Archives"""
        try:
            response = await self.client.get("/dataservers")
            response.raise_for_status()
            data = response.json()
            return data.get("Items", [])
        except Exception as e:
            logger.error(f"Error getting data servers: {e}")
            return []

    async def get_assetservers(self) -> List[Dict[str, Any]]:
        """Get list of AF Servers"""
        try:
            response = await self.client.get("/assetservers")
            response.raise_for_status()
            data = response.json()
            return data.get("Items", [])
        except Exception as e:
            logger.error(f"Error getting asset servers: {e}")
            return []

    async def search_elements(
        self,
        database_web_id: str,
        query: str,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search for AF Elements

        Args:
            database_web_id: Web ID of the database
            query: Search query string
            max_results: Maximum number of results

        Returns:
            List of element dictionaries
        """
        try:
            params = {
                "nameFilter": f"*{query}*",
                "maxCount": max_results,
                "searchFullHierarchy": "true"
            }

            response = await self.client.get(
                f"/assetdatabases/{database_web_id}/elements",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            return data.get("Items", [])

        except Exception as e:
            logger.error(f"Error searching elements: {e}")
            return []

    async def get_element_by_path(
        self,
        web_id: str,
        path: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get AF Element by path

        Args:
            web_id: Web ID of the AF server or database
            path: Element path

        Returns:
            Element dictionary or None
        """
        try:
            params = {"path": path}
            response = await self.client.get(
                f"/elements",
                params=params
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Error getting element by path: {e}")
            return None

    async def get_element_attributes(self, element_web_id: str) -> List[Dict[str, Any]]:
        """
        Get all attributes of an element

        Args:
            element_web_id: Web ID of the element

        Returns:
            List of attribute dictionaries
        """
        try:
            response = await self.client.get(f"/elements/{element_web_id}/attributes")
            response.raise_for_status()
            data = response.json()
            return data.get("Items", [])

        except Exception as e:
            logger.error(f"Error getting element attributes: {e}")
            return []

    async def get_attribute_value(
        self,
        attribute_web_id: str,
        time: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get attribute value

        Args:
            attribute_web_id: Web ID of the attribute
            time: Time for value (None for snapshot)

        Returns:
            Value dictionary or None
        """
        try:
            params = {}
            if time:
                params["time"] = time

            response = await self.client.get(
                f"/attributes/{attribute_web_id}/value",
                params=params
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Error getting attribute value: {e}")
            return None

    async def get_recorded_values(
        self,
        attribute_web_id: str,
        start_time: str,
        end_time: str,
        max_count: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get recorded values for an attribute

        Args:
            attribute_web_id: Web ID of the attribute
            start_time: Start time string
            end_time: End time string
            max_count: Maximum number of values

        Returns:
            List of value dictionaries
        """
        try:
            params = {
                "startTime": start_time,
                "endTime": end_time,
                "maxCount": max_count
            }

            response = await self.client.get(
                f"/attributes/{attribute_web_id}/recordedvalues",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            return data.get("Items", [])

        except Exception as e:
            logger.error(f"Error getting recorded values: {e}")
            return []

    async def get_pi_point_by_name(
        self,
        dataserver_web_id: str,
        point_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get PI Point by name

        Args:
            dataserver_web_id: Web ID of the PI Data Archive
            point_name: PI Point name

        Returns:
            PI Point dictionary or None
        """
        try:
            params = {"nameFilter": point_name}
            response = await self.client.get(
                f"/dataservers/{dataserver_web_id}/points",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            items = data.get("Items", [])
            return items[0] if items else None

        except Exception as e:
            logger.error(f"Error getting PI Point: {e}")
            return None

    async def get_point_value(
        self,
        point_web_id: str,
        time: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get PI Point value

        Args:
            point_web_id: Web ID of the PI Point
            time: Time for value (None for snapshot)

        Returns:
            Value dictionary or None
        """
        try:
            params = {}
            if time:
                params["time"] = time

            response = await self.client.get(
                f"/points/{point_web_id}/value",
                params=params
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Error getting point value: {e}")
            return None

    async def write_point_value(
        self,
        point_web_id: str,
        value: Any,
        timestamp: str = None
    ) -> bool:
        """
        Write value to PI Point

        Args:
            point_web_id: Web ID of the PI Point
            value: Value to write
            timestamp: Timestamp (None for current time)

        Returns:
            True if successful, False otherwise
        """
        try:
            payload = {
                "Value": value,
            }
            if timestamp:
                payload["Timestamp"] = timestamp

            response = await self.client.post(
                f"/points/{point_web_id}/value",
                json=payload
            )
            response.raise_for_status()
            return True

        except Exception as e:
            logger.error(f"Error writing point value: {e}")
            return False

    async def batch_request(self, batch: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute batch request

        Args:
            batch: Batch request dictionary

        Returns:
            Batch response dictionary
        """
        try:
            response = await self.client.post("/batch", json=batch)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Error executing batch request: {e}")
            return {}

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
        logger.info("PI Web API client closed")
