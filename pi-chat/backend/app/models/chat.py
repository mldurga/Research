"""
Chat models
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ChatMessage(BaseModel):
    """Chat message model"""
    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    """Chat request model"""
    message: str = Field(..., description="User message")
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional context (e.g., selected PI elements)"
    )
    conversation_id: Optional[str] = Field(None, description="Conversation ID for history")
    model: Optional[str] = Field(None, description="LLM model to use")
    temperature: Optional[float] = Field(None, description="Sampling temperature")
    stream: bool = Field(default=False, description="Enable streaming response")


class ChatResponse(BaseModel):
    """Chat response model"""
    response: str = Field(..., description="Assistant response")
    conversation_id: str = Field(..., description="Conversation ID")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    sources: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="Source references (PI elements, points, etc.)"
    )


class ConversationHistory(BaseModel):
    """Conversation history model"""
    conversation_id: str
    messages: List[ChatMessage]
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
