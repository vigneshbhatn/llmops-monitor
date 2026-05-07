import asyncio
import httpx

async def main():
    try:
        async with httpx.AsyncClient(timeout=0.01) as client:
            await client.post("http://localhost:11434/v1/chat/completions", json={"model": "gemma2", "messages": [{"role": "user", "content": "hi"}]})
    except Exception as e:
        print("str:", repr(str(e)))
        print("repr:", repr(e))

asyncio.run(main())
