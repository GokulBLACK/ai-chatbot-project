import httpx
from app.core.config import LLM_API_KEY, LLM_BASE_URL

async def chat_complete(messages: list[dict], model: str) -> str:
    if not LLM_API_KEY:
        return "Set LLM_API_KEY in .env"

    url = f"{LLM_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "temperature": 0.2}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    return data["choices"][0]["message"]["content"]
