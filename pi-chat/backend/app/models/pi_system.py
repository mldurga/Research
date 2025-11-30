"""
PI System models
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class PIElement(BaseModel):
    """AF Element model"""
    name: str
    path: str
    description: Optional[str] = None
    template: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    has_children: bool = False


class PIAttribute(BaseModel):
    """AF Attribute model"""
    name: str
    path: str
    description: Optional[str] = None
    type: str
    data_reference: Optional[str] = None
    uom: Optional[str] = None


class PIValue(BaseModel):
    """PI Value model"""
    value: Any
    timestamp: Optional[str] = None
    uom: Optional[str] = None
    good: bool = True


class ElementSearchRequest(BaseModel):
    """Element search request"""
    query: str = Field(..., description="Search query")
    max_results: int = Field(default=100, description="Maximum results")
    search_full_hierarchy: bool = Field(default=True)


class AttributeValueRequest(BaseModel):
    """Attribute value request"""
    element_path: str
    attribute_name: str
    snapshot: bool = Field(default=True, description="Get snapshot value")


class RecordedValuesRequest(BaseModel):
    """Recorded values request"""
    element_path: str
    attribute_name: str
    start_time: str = Field(..., description="Start time (e.g., '*-1d')")
    end_time: str = Field(..., description="End time (e.g., '*')")
    max_count: int = Field(default=1000)


class PIPointValueRequest(BaseModel):
    """PI Point value request"""
    point_name: str
    snapshot: bool = Field(default=True)
