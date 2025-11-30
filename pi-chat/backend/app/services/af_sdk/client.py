"""
AF SDK Client - Python bridge to AVEVA AF SDK using pythonnet
"""

import sys
from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger

try:
    import clr
    import System
    from System import String, DateTime, TimeSpan
    from System.Collections.Generic import List as DotNetList
except ImportError:
    logger.error("pythonnet not installed. Install with: pip install pythonnet")
    raise

from app.core.config import settings


class AFSDKClient:
    """Client for interacting with AVEVA PI System via AF SDK"""

    def __init__(self):
        """Initialize AF SDK connection"""
        self.af_server = None
        self.pi_server = None
        self.database = None
        self._load_af_sdk()
        self._connect()

    def _load_af_sdk(self):
        """Load AF SDK assemblies using pythonnet"""
        try:
            logger.info("Loading AF SDK assemblies...")

            # Add AF SDK DLL references
            # Typical installation path: C:\Program Files\AVEVA\PI System\AF\PublicAssemblies\4.0
            af_sdk_path = Path("C:/Program Files/AVEVA/PI System/AF/PublicAssemblies/4.0")

            if not af_sdk_path.exists():
                # Try alternative path
                af_sdk_path = Path("C:/Program Files (x86)/AVEVA/PI System/AF/PublicAssemblies/4.0")

            if not af_sdk_path.exists():
                raise FileNotFoundError(
                    "AF SDK not found. Please install AVEVA PI AF Client or update the path."
                )

            # Add to .NET path
            sys.path.append(str(af_sdk_path))

            # Load AF SDK assemblies
            clr.AddReference("OSIsoft.AFSDK")

            # Import AF SDK namespaces
            from OSIsoft.AF import PISystem, AFDatabase, AFElement, AFAttribute
            from OSIsoft.AF.Asset import AFAttributeList
            from OSIsoft.AF.Search import AFSearchMode, AFSearchField
            from OSIsoft.AF.Data import AFValue, AFValues, AFBoundaryType, AFTime
            from OSIsoft.AF.PI import PIPoint, PIServer
            from OSIsoft.AF.Time import AFTimeRange, AFTimeSpan

            # Store references
            self.PISystem = PISystem
            self.AFDatabase = AFDatabase
            self.AFElement = AFElement
            self.AFAttribute = AFAttribute
            self.AFAttributeList = AFAttributeList
            self.AFSearchMode = AFSearchMode
            self.AFSearchField = AFSearchField
            self.AFValue = AFValue
            self.AFValues = AFValues
            self.AFBoundaryType = AFBoundaryType
            self.AFTime = AFTime
            self.AFTimeRange = AFTimeRange
            self.AFTimeSpan = AFTimeSpan
            self.PIPoint = PIPoint
            self.PIServer = PIServer

            logger.success("AF SDK assemblies loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load AF SDK: {e}")
            raise

    def _connect(self):
        """Connect to AF Server and PI Data Archive"""
        try:
            logger.info(f"Connecting to AF Server: {settings.pi_system.af_server}")

            # Connect to AF Server
            pi_systems = self.PISystem.PISystem.GetPISystems()
            self.af_server = pi_systems[settings.pi_system.af_server]

            if not self.af_server:
                raise ConnectionError(f"Could not find AF Server: {settings.pi_system.af_server}")

            # Connect (uses Windows authentication by default)
            self.af_server.Connect()
            logger.success(f"Connected to AF Server: {self.af_server.Name}")

            # Connect to database
            self.database = self.af_server.Databases[settings.pi_system.default_database]
            if not self.database:
                raise ConnectionError(
                    f"Could not find database: {settings.pi_system.default_database}"
                )

            logger.success(f"Connected to database: {self.database.Name}")

            # Connect to PI Data Archive
            logger.info(f"Connecting to PI Server: {settings.pi_system.pi_data_archive}")
            self.pi_server = self.PIServer.FindPIServer(settings.pi_system.pi_data_archive)

            if not self.pi_server:
                raise ConnectionError(
                    f"Could not find PI Server: {settings.pi_system.pi_data_archive}"
                )

            self.pi_server.Connect()
            logger.success(f"Connected to PI Server: {self.pi_server.Name}")

        except Exception as e:
            logger.error(f"Failed to connect to PI System: {e}")
            raise

    def get_element_by_path(self, path: str) -> Optional[Any]:
        """
        Get AF Element by path

        Args:
            path: Element path (e.g., "\\\\ElementName\\ChildElement")

        Returns:
            AF Element object or None
        """
        try:
            element = self.AFElement.FindElementsByPath([path], self.database)[0]
            return element
        except Exception as e:
            logger.error(f"Error getting element by path {path}: {e}")
            return None

    def search_elements(
        self,
        query: str,
        max_results: int = 100,
        search_full_hierarchy: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search for AF Elements

        Args:
            query: Search query string
            max_results: Maximum number of results
            search_full_hierarchy: Search entire hierarchy

        Returns:
            List of element dictionaries
        """
        try:
            logger.debug(f"Searching elements with query: {query}")

            # Create AF element search
            search_token = self.database.CreateSearchToken()

            # Build search query
            search_results = self.database.FindElements(
                searchRoot=self.database.Elements,
                nameFilter=f"*{query}*",
                searchFullHierarchy=search_full_hierarchy,
                sortField=self.AFSearchField.Name,
                sortOrder=self.AFSearchMode.Inclusive,
                maxCount=max_results
            )

            elements = []
            for element in search_results:
                elements.append(self._element_to_dict(element))

            logger.debug(f"Found {len(elements)} elements")
            return elements

        except Exception as e:
            logger.error(f"Error searching elements: {e}")
            return []

    def get_element_attributes(self, element_path: str) -> List[Dict[str, Any]]:
        """
        Get all attributes of an element

        Args:
            element_path: Path to the element

        Returns:
            List of attribute dictionaries
        """
        try:
            element = self.get_element_by_path(element_path)
            if not element:
                return []

            attributes = []
            for attribute in element.Attributes:
                attributes.append(self._attribute_to_dict(attribute))

            return attributes

        except Exception as e:
            logger.error(f"Error getting element attributes: {e}")
            return []

    def get_attribute_value(
        self,
        element_path: str,
        attribute_name: str,
        snapshot: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get attribute value (snapshot or current)

        Args:
            element_path: Path to the element
            attribute_name: Name of the attribute
            snapshot: If True, get snapshot value; otherwise current value

        Returns:
            Value dictionary or None
        """
        try:
            element = self.get_element_by_path(element_path)
            if not element:
                return None

            attribute = element.Attributes[attribute_name]
            if not attribute:
                logger.warning(f"Attribute {attribute_name} not found")
                return None

            if snapshot:
                value = attribute.GetValue()
            else:
                value = attribute.GetValue(self.AFTime("*"))

            return self._value_to_dict(value)

        except Exception as e:
            logger.error(f"Error getting attribute value: {e}")
            return None

    def get_recorded_values(
        self,
        element_path: str,
        attribute_name: str,
        start_time: str,
        end_time: str,
        max_count: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get recorded values for an attribute

        Args:
            element_path: Path to the element
            attribute_name: Name of the attribute
            start_time: Start time string (e.g., "*-1d", "2024-01-01")
            end_time: End time string (e.g., "*", "2024-01-02")
            max_count: Maximum number of values

        Returns:
            List of value dictionaries
        """
        try:
            element = self.get_element_by_path(element_path)
            if not element:
                return []

            attribute = element.Attributes[attribute_name]
            if not attribute:
                return []

            # Create time range
            time_range = self.AFTimeRange(
                self.AFTime(start_time),
                self.AFTime(end_time)
            )

            # Get recorded values
            values = attribute.Data.RecordedValues(
                timeRange=time_range,
                boundaryType=self.AFBoundaryType.Inside,
                filterExpression="",
                includeFilteredValues=False,
                maxCount=max_count
            )

            result = []
            for value in values:
                result.append(self._value_to_dict(value))

            logger.debug(f"Retrieved {len(result)} recorded values")
            return result

        except Exception as e:
            logger.error(f"Error getting recorded values: {e}")
            return []

    def get_pi_point_value(self, point_name: str, snapshot: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get PI Point value directly

        Args:
            point_name: PI Point name
            snapshot: If True, get snapshot value

        Returns:
            Value dictionary or None
        """
        try:
            point = self.PIPoint.FindPIPoint(self.pi_server, point_name)
            if not point:
                logger.warning(f"PI Point {point_name} not found")
                return None

            if snapshot:
                value = point.Snapshot()
            else:
                value = point.CurrentValue()

            return self._value_to_dict(value)

        except Exception as e:
            logger.error(f"Error getting PI Point value: {e}")
            return None

    def check_element_security(self, element_path: str, user_identity: str) -> bool:
        """
        Check if user has access to element

        Args:
            element_path: Path to the element
            user_identity: User identity (domain\\username)

        Returns:
            True if user has access, False otherwise
        """
        try:
            element = self.get_element_by_path(element_path)
            if not element:
                return False

            # Get security
            security = element.Security
            # Check read permission
            # This is a simplified check - you may need to implement more detailed checks
            return True  # Placeholder - implement actual security check

        except Exception as e:
            logger.error(f"Error checking element security: {e}")
            return False

    def _element_to_dict(self, element: Any) -> Dict[str, Any]:
        """Convert AF Element to dictionary"""
        return {
            "name": str(element.Name),
            "path": str(element.GetPath()),
            "description": str(element.Description) if element.Description else "",
            "template": str(element.Template.Name) if element.Template else None,
            "categories": [str(cat.Name) for cat in element.Categories],
            "hasChildren": element.Elements.Count > 0,
        }

    def _attribute_to_dict(self, attribute: Any) -> Dict[str, Any]:
        """Convert AF Attribute to dictionary"""
        return {
            "name": str(attribute.Name),
            "description": str(attribute.Description) if attribute.Description else "",
            "path": str(attribute.GetPath()),
            "type": str(attribute.Type),
            "dataReference": str(attribute.DataReferenceType) if attribute.DataReference else None,
            "uom": str(attribute.DefaultUOM) if attribute.DefaultUOM else None,
        }

    def _value_to_dict(self, value: Any) -> Dict[str, Any]:
        """Convert AF Value to dictionary"""
        return {
            "value": self._convert_value(value.Value),
            "timestamp": str(value.Timestamp) if value.Timestamp else None,
            "uom": str(value.UOM) if value.UOM else None,
            "good": value.IsGood,
        }

    def _convert_value(self, value: Any) -> Any:
        """Convert .NET value to Python value"""
        if value is None:
            return None

        # Handle different value types
        value_type = value.GetType().Name

        if value_type in ["Int32", "Int64", "Double", "Single"]:
            return float(value) if "." in str(value) else int(value)
        elif value_type == "String":
            return str(value)
        elif value_type == "Boolean":
            return bool(value)
        else:
            return str(value)

    def disconnect(self):
        """Disconnect from PI System"""
        try:
            if self.af_server:
                self.af_server.Disconnect()
                logger.info("Disconnected from AF Server")

            if self.pi_server:
                self.pi_server.Disconnect()
                logger.info("Disconnected from PI Server")

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
