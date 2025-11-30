"""
Chat API endpoints
"""

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
import uuid
import json
from typing import Dict, Any

from app.models.chat import ChatRequest, ChatResponse, ChatMessage
from app.services.security.auth import SecurityService

router = APIRouter()
security_service = SecurityService()

# In-memory conversation storage (use database in production)
conversations: Dict[str, Any] = {}


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest, req: Request):
    """
    Send a chat message and get response

    This endpoint processes user messages, queries the PI System if needed,
    and generates responses using the LLM.
    """
    try:
        # Get services from app state
        af_client = req.app.state.af_client if hasattr(req.app.state, 'af_client') else None
        vector_db = req.app.state.vector_db if hasattr(req.app.state, 'vector_db') else None
        ollama = req.app.state.ollama if hasattr(req.app.state, 'ollama') else None

        if not ollama:
            raise HTTPException(status_code=503, detail="LLM service not available")

        # Get or create conversation ID
        conversation_id = request.conversation_id or str(uuid.uuid4())

        # Get conversation history
        if conversation_id in conversations:
            messages = conversations[conversation_id]["messages"]
        else:
            messages = []
            conversations[conversation_id] = {
                "id": conversation_id,
                "messages": messages,
                "created_at": None
            }

        # Add user message to history
        user_message = ChatMessage(role="user", content=request.message)
        messages.append(user_message)

        # Build context from vector DB if available
        context_text = ""
        sources = []

        if vector_db and request.context:
            # Search for relevant PI elements
            search_query = request.message
            results = vector_db.search_elements(search_query, n_results=5)

            if results:
                context_text = "\n\nRelevant PI System elements:\n"
                for result in results:
                    metadata = result.get("metadata", {})
                    context_text += f"- {metadata.get('name', 'Unknown')}: {result.get('document', '')}\n"
                    sources.append({
                        "type": "element",
                        "name": metadata.get("name", ""),
                        "path": metadata.get("path", ""),
                    })

        # Build system prompt
        system_prompt = """You are a helpful AI assistant for AVEVA PI System.
You can help users query PI elements, retrieve data, and analyze process information.
When referring to PI elements or data, be specific and accurate.
If you need to access PI System data, explain what information you need."""

        if context_text:
            system_prompt += context_text

        # Prepare messages for LLM
        llm_messages = [
            {"role": "system", "content": system_prompt},
        ]

        # Add conversation history (last 10 messages)
        for msg in messages[-10:]:
            llm_messages.append({
                "role": msg.role,
                "content": msg.content
            })

        # Get response from LLM
        response = await ollama.chat(
            messages=llm_messages,
            model=request.model,
            temperature=request.temperature,
        )

        assistant_response = response.get("message", {}).get("content", "")

        # Add assistant message to history
        assistant_message = ChatMessage(role="assistant", content=assistant_response)
        messages.append(assistant_message)

        # Update conversation
        conversations[conversation_id]["messages"] = messages

        return ChatResponse(
            response=assistant_response,
            conversation_id=conversation_id,
            sources=sources,
            metadata={
                "model": request.model or "default",
                "context_used": bool(context_text)
            }
        )

    except Exception as e:
        logger.error(f"Error processing chat message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def stream_message(request: ChatRequest, req: Request):
    """
    Send a chat message and stream the response
    """
    async def generate():
        try:
            ollama = req.app.state.ollama if hasattr(req.app.state, 'ollama') else None
            vector_db = req.app.state.vector_db if hasattr(req.app.state, 'vector_db') else None

            if not ollama:
                yield f"data: {json.dumps({'error': 'LLM service not available'})}\n\n"
                return

            # Build context
            context_text = ""
            if vector_db:
                results = vector_db.search_elements(request.message, n_results=5)
                if results:
                    context_text = "\n\nRelevant PI System elements:\n"
                    for result in results:
                        metadata = result.get("metadata", {})
                        context_text += f"- {metadata.get('name', 'Unknown')}: {result.get('document', '')}\n"

            # System prompt
            system_prompt = """You are a helpful AI assistant for AVEVA PI System.
You can help users query PI elements, retrieve data, and analyze process information."""

            if context_text:
                system_prompt += context_text

            # Prepare messages
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.message}
            ]

            # Stream response
            async for chunk in ollama.chat_stream(
                messages=messages,
                model=request.model,
                temperature=request.temperature,
            ):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time chat
    """
    await websocket.accept()
    logger.info("WebSocket connection established")

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            message = data.get("message", "")
            conversation_id = data.get("conversation_id", str(uuid.uuid4()))

            # Simple echo for now
            # TODO: Integrate with LLM and PI System
            response = {
                "response": f"Echo: {message}",
                "conversation_id": conversation_id
            }

            await websocket.send_json(response)

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close()


@router.get("/history/{conversation_id}")
async def get_conversation_history(conversation_id: str):
    """Get conversation history"""
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversations[conversation_id]


@router.delete("/history/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete conversation history"""
    if conversation_id in conversations:
        del conversations[conversation_id]
        return {"status": "deleted"}

    raise HTTPException(status_code=404, detail="Conversation not found")
