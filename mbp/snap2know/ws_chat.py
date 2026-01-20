"""
Snap2Know WebSocket Chat
Streaming Q&A with RAG retrieval and Claude Sonnet
"""
import time
import uuid
import json
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import httpx
from config import settings
from rag import retrieve_context, build_system_prompt, build_user_prompt, estimate_tokens

router = APIRouter()


async def stream_claude_response(
    websocket: WebSocket,
    question: str,
    context: str,
    trace_id: str
) -> int:
    """
    调用 Claude Sonnet API 并发送回答
    
    注意：由于 API 代理不支持流式，使用非流式 API 并模拟流式输出
    
    Returns:
        生成的总 token 数量
    """
    import anthropic
    import asyncio
    
    # 配置客户端
    client_kwargs = {"api_key": settings.anthropic_api_key}
    
    if settings.anthropic_base_url:
        client_kwargs["base_url"] = settings.anthropic_base_url
    
    if settings.http_proxy or settings.https_proxy:
        client_kwargs["http_client"] = httpx.Client(
            proxy=settings.https_proxy or settings.http_proxy
        )
    
    # 使用同步客户端（非流式 API）
    client = anthropic.Anthropic(**client_kwargs)
    
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(question, context)
    
    # 非流式调用
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2048,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt}
        ]
    )
    
    full_text = response.content[0].text
    total_tokens = len(full_text) // 2  # 估算 token 数
    
    # 模拟流式输出：分块发送
    chunk_size = 5  # 每次发送 5 个字符
    for i in range(0, len(full_text), chunk_size):
        await websocket.send_json({
            "type": "token",
            "text": full_text[i:i+chunk_size]
        })
        # 小延迟使输出看起来更流畅
        await asyncio.sleep(0.01)
    
    return total_tokens


@router.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str = Query(..., description="会话 ID")
):
    """
    WebSocket 流式问答端点
    
    协议：
    1. 客户端发送: {"question_text": "...", "top_k": 6}
    2. 服务端响应:
       - {type: "meta", trace_id, retrieved, context_tokens}
       - {type: "token", text} (多条)
       - {type: "done", total_ms, total_tokens}
       - {type: "error", message} (异常时)
    """
    await websocket.accept()
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            
            try:
                request = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })
                continue
            
            # 解析请求
            question_text = request.get("question_text", "").strip()
            if not question_text:
                await websocket.send_json({
                    "type": "error",
                    "message": "question_text is required"
                })
                continue
            
            top_k = request.get("top_k", 6)
            req_session_id = request.get("session_id", session_id)
            
            # 生成追踪 ID
            trace_id = str(uuid.uuid4())[:8]
            start_time = time.time()
            
            try:
                # 1. 检索相关文档
                results, context = await retrieve_context(
                    question=question_text,
                    session_id=req_session_id,
                    top_k=top_k
                )
                
                # 2. 发送 meta 消息
                context_tokens = estimate_tokens(context)
                await websocket.send_json({
                    "type": "meta",
                    "trace_id": trace_id,
                    "retrieved": [
                        {"text": r.get("text", "")[:200], "score": r.get("score", 0)}
                        for r in results[:3]  # 只返回前 3 条的预览
                    ],
                    "retrieved_count": len(results),
                    "context_tokens": context_tokens
                })
                
                # 3. 流式生成回答
                total_tokens = await stream_claude_response(
                    websocket=websocket,
                    question=question_text,
                    context=context,
                    trace_id=trace_id
                )
                
                # 4. 发送 done 消息
                elapsed_ms = int((time.time() - start_time) * 1000)
                await websocket.send_json({
                    "type": "done",
                    "trace_id": trace_id,
                    "total_ms": elapsed_ms,
                    "total_tokens": total_tokens
                })
                
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "trace_id": trace_id,
                    "message": str(e)
                })
                
    except WebSocketDisconnect:
        if settings.debug:
            print(f"WebSocket disconnected: session_id={session_id}")
    except Exception as e:
        if settings.debug:
            print(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Connection error: {str(e)}"
            })
        except:
            pass
