"""
WebSocket 流式问答测试脚本
"""
import websockets
import asyncio
import json


async def test_ws_chat():
    uri = "ws://localhost:8000/ws/chat?session_id=test123"
    
    print("连接 WebSocket...")
    async with websockets.connect(uri) as ws:
        # 发送问题
        question = {"question_text": "如何登录管理后台", "top_k": 6}
        print(f"发送问题: {question['question_text']}")
        await ws.send(json.dumps(question))
        
        # 接收响应
        full_answer = ""
        async for msg in ws:
            data = json.loads(msg)
            msg_type = data.get("type")
            
            if msg_type == "meta":
                print(f"\n[META] trace_id={data.get('trace_id')}")
                print(f"  检索到 {data.get('retrieved_count', 0)} 条文档")
                print(f"  上下文 tokens: {data.get('context_tokens', 0)}")
                print("\n回答: ", end="", flush=True)
                
            elif msg_type == "token":
                text = data.get("text", "")
                print(text, end="", flush=True)
                full_answer += text
                
            elif msg_type == "done":
                print(f"\n\n[DONE] 耗时 {data.get('total_ms')}ms, tokens={data.get('total_tokens')}")
                break
                
            elif msg_type == "error":
                print(f"\n[ERROR] {data.get('message')}")
                break
        
        print(f"\n完整回答长度: {len(full_answer)} 字符")


if __name__ == "__main__":
    asyncio.run(test_ws_chat())
