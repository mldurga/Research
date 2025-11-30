"""
PI System API endpoints
"""

from fastapi import APIRouter, Request, HTTPException, Query
from loguru import logger
from typing import List, Optional

from app.models.pi_system import (
    PIElement,
    PIAttribute,
    PIValue,
    ElementSearchRequest,
    AttributeValueRequest,
    RecordedValuesRequest,
    PIPointValueRequest
)
from app.services.security.auth import SecurityService

router = APIRouter()
security_service = SecurityService()


@router.post("/elements/search", response_model=List[PIElement])
async def search_elements(search_request: ElementSearchRequest, request: Request):
    """
    Search for AF elements

    Searches the PI Asset Framework for elements matching the query.
    Results are filtered based on user permissions.
    """
    try:
        af_client = request.app.state.af_client if hasattr(request.app.state, 'af_client') else None

        if not af_client:
            raise HTTPException(status_code=503, detail="AF SDK not available")

        # Search elements
        elements = af_client.search_elements(
            query=search_request.query,
            max_results=search_request.max_results,
            search_full_hierarchy=search_request.search_full_hierarchy
        )

        # TODO: Filter by user permissions
        # user_identity = security_service.get_user_identity(request.user)
        # elements = security_service.filter_elements_by_permission(user_identity, elements)

        # Convert to PIElement model
        result = []
        for elem in elements:
            result.append(PIElement(
                name=elem.get("name", ""),
                path=elem.get("path", ""),
                description=elem.get("description"),
                template=elem.get("template"),
                categories=elem.get("categories", []),
                has_children=elem.get("hasChildren", False)
            ))

        logger.info(f"Found {len(result)} elements for query: {search_request.query}")
        return result

    except Exception as e:
        logger.error(f"Error searching elements: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/elements/{element_path:path}/attributes", response_model=List[PIAttribute])
async def get_element_attributes(element_path: str, request: Request):
    """
    Get attributes of an AF element

    Returns all attributes for the specified element.
    """
    try:
        af_client = request.app.state.af_client if hasattr(request.app.state, 'af_client') else None

        if not af_client:
            raise HTTPException(status_code=503, detail="AF SDK not available")

        # Get attributes
        attributes = af_client.get_element_attributes(element_path)

        # Convert to PIAttribute model
        result = []
        for attr in attributes:
            result.append(PIAttribute(
                name=attr.get("name", ""),
                path=attr.get("path", ""),
                description=attr.get("description"),
                type=attr.get("type", ""),
                data_reference=attr.get("dataReference"),
                uom=attr.get("uom")
            ))

        return result

    except Exception as e:
        logger.error(f"Error getting element attributes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/attributes/value", response_model=PIValue)
async def get_attribute_value(value_request: AttributeValueRequest, request: Request):
    """
    Get attribute value (snapshot or current)

    Returns the current or snapshot value for the specified attribute.
    """
    try:
        af_client = request.app.state.af_client if hasattr(request.app.state, 'af_client') else None

        if not af_client:
            raise HTTPException(status_code=503, detail="AF SDK not available")

        # Get value
        value = af_client.get_attribute_value(
            element_path=value_request.element_path,
            attribute_name=value_request.attribute_name,
            snapshot=value_request.snapshot
        )

        if not value:
            raise HTTPException(status_code=404, detail="Attribute not found or no value available")

        return PIValue(
            value=value.get("value"),
            timestamp=value.get("timestamp"),
            uom=value.get("uom"),
            good=value.get("good", True)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting attribute value: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/attributes/recorded", response_model=List[PIValue])
async def get_recorded_values(values_request: RecordedValuesRequest, request: Request):
    """
    Get recorded values for an attribute

    Returns historical values for the specified time range.
    """
    try:
        af_client = request.app.state.af_client if hasattr(request.app.state, 'af_client') else None

        if not af_client:
            raise HTTPException(status_code=503, detail="AF SDK not available")

        # Get recorded values
        values = af_client.get_recorded_values(
            element_path=values_request.element_path,
            attribute_name=values_request.attribute_name,
            start_time=values_request.start_time,
            end_time=values_request.end_time,
            max_count=values_request.max_count
        )

        # Convert to PIValue model
        result = []
        for val in values:
            result.append(PIValue(
                value=val.get("value"),
                timestamp=val.get("timestamp"),
                uom=val.get("uom"),
                good=val.get("good", True)
            ))

        return result

    except Exception as e:
        logger.error(f"Error getting recorded values: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/points/value", response_model=PIValue)
async def get_pi_point_value(point_request: PIPointValueRequest, request: Request):
    """
    Get PI Point value directly

    Returns the current or snapshot value for the specified PI Point.
    """
    try:
        af_client = request.app.state.af_client if hasattr(request.app.state, 'af_client') else None

        if not af_client:
            raise HTTPException(status_code=503, detail="AF SDK not available")

        # Get point value
        value = af_client.get_pi_point_value(
            point_name=point_request.point_name,
            snapshot=point_request.snapshot
        )

        if not value:
            raise HTTPException(status_code=404, detail="PI Point not found or no value available")

        return PIValue(
            value=value.get("value"),
            timestamp=value.get("timestamp"),
            uom=value.get("uom"),
            good=value.get("good", True)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting PI Point value: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/points/search")
async def search_pi_points(
    query: str = Query(..., description="Search query"),
    max_results: int = Query(100, description="Maximum results"),
    request: Request = None
):
    """
    Search for PI Points

    Searches PI Data Archive for points matching the query.
    """
    try:
        # TODO: Implement PI Point search
        # This would require additional AF SDK methods or PI Web API

        return {
            "message": "PI Point search not yet implemented",
            "query": query
        }

    except Exception as e:
        logger.error(f"Error searching PI Points: {e}")
        raise HTTPException(status_code=500, detail=str(e))
