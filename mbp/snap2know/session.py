"""
Snap2Know Session Management
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Optional
import uuid

router = APIRouter()

# 内存存储（后续可替换为 Redis）
sessions: Dict[str, dict] = {}


class SessionCreate(BaseModel):
    """创建会话请求"""
    name: Optional[str] = None


class SessionResponse(BaseModel):
    """会话响应"""
    session_id: str
    name: Optional[str]
    created_at: str
    image_count: int = 0


class SessionDeleteResponse(BaseModel):
    """删除会话响应"""
    deleted: bool
    session_id: str


@router.post("", response_model=SessionResponse)
async def create_session(request: SessionCreate = None):
    """创建新会话"""
    session_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    
    session_data = {
        "session_id": session_id,
        "name": request.name if request else None,
        "created_at": now,
        "image_count": 0,
        "chunks": []
    }
    
    sessions[session_id] = session_data
    
    return SessionResponse(
        session_id=session_id,
        name=session_data["name"],
        created_at=now,
        image_count=0
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """获取会话详情"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    return SessionResponse(
        session_id=session["session_id"],
        name=session["name"],
        created_at=session["created_at"],
        image_count=session["image_count"]
    )


@router.get("")
async def list_sessions():
    """列出所有会话"""
    return {
        "sessions": [
            SessionResponse(
                session_id=s["session_id"],
                name=s["name"],
                created_at=s["created_at"],
                image_count=s["image_count"]
            )
            for s in sessions.values()
        ],
        "total": len(sessions)
    }


@router.delete("/{session_id}", response_model=SessionDeleteResponse)
async def delete_session(session_id: str):
    """删除会话"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    del sessions[session_id]
    
    return SessionDeleteResponse(deleted=True, session_id=session_id)
