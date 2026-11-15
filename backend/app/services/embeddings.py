import asyncio
from typing import List, Optional
import httpx
from app.core.config import settings
from app.core.logging import logger


class FeatureDisabled(Exception):
    pass


class EmbeddingService:
    def __init__(self):
        self.settings = settings

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not self.settings.FEATURE_SEMANTIC_SEARCH or not self.settings.EMBEDDING_API_KEY:
            raise FeatureDisabled("Semantic search is disabled or EMBEDDING_API_KEY is not configured.")

        # Truncate each text to ~8,000 chars
        truncated = [t[:8000] for t in texts]
        batch_size = 64
        all_embeddings: List[List[float]] = []

        headers = {
            "Authorization": f"Bearer {self.settings.EMBEDDING_API_KEY}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(0, len(truncated), batch_size):
                batch = truncated[i : i + batch_size]
                payload = {
                    "input": batch,
                    "model": self.settings.EMBEDDING_MODEL,
                }
                # Retry with exponential backoff
                for attempt in range(3):
                    try:
                        resp = await client.post(
                            "https://api.openai.com/v1/embeddings",
                            headers=headers,
                            json=payload,
                        )
                        if resp.status_code == 200:
                            data = resp.json().get("data", [])
                            # Sort by index
                            data.sort(key=lambda x: x["index"])
                            for item in data:
                                all_embeddings.append(item["embedding"])
                            break
                        else:
                            logger.warning(
                                "Embedding API request failed (attempt %d, status=%d).",
                                attempt + 1,
                                resp.status_code,
                            )
                            if attempt == 2:
                                raise FeatureDisabled(f"Embedding failed: {resp.status_code}")
                            await asyncio.sleep(2**attempt)
                    except httpx.RequestError as e:
                        if attempt == 2:
                            raise FeatureDisabled("Embedding connection failed.") from e
                        await asyncio.sleep(2**attempt)

        return all_embeddings

    async def embed_query(self, query: str) -> List[float]:
        res = await self.embed_texts([query])
        return res[0] if res else []
