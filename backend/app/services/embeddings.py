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

        provider = getattr(self.settings, "EMBEDDING_PROVIDER", "openai").lower()
        if provider not in {"openai", "gemini"}:
            logger.error("Unsupported embedding provider configured: %s", provider)
            raise FeatureDisabled(f"Unsupported embedding provider: {provider}")
        headers = {"Content-Type": "application/json"}
        if provider == "openai":
            headers["Authorization"] = f"Bearer {self.settings.EMBEDDING_API_KEY}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(0, len(truncated), batch_size):
                batch = truncated[i : i + batch_size]
                if provider == "openai":
                    url = "https://api.openai.com/v1/embeddings"
                    payload = {"input": batch, "model": self.settings.EMBEDDING_MODEL}
                else:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.EMBEDDING_MODEL}:batchEmbedContents"
                    headers["x-goog-api-key"] = self.settings.EMBEDDING_API_KEY
                    payload = {"requests": [
                        {"model": f"models/{self.settings.EMBEDDING_MODEL}",
                         "content": {"parts": [{"text": value}]},
                         "outputDimensionality": getattr(self.settings, "EMBEDDING_DIM", 1536)}
                        for value in batch
                    ]}
                for attempt in range(3):
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        body = resp.json()
                        if provider == "openai":
                            data = body.get("data", [])
                            data.sort(key=lambda item: item["index"])
                            all_embeddings.extend(item["embedding"] for item in data)
                        else:
                            all_embeddings.extend(item.get("values", []) for item in body.get("embeddings", []))
                        break
                    if resp.status_code != 429 and resp.status_code < 500:
                        raise FeatureDisabled(f"Embedding failed: {resp.status_code}")
                    logger.warning("Embedding API request failed (attempt %d, status=%d).", attempt + 1, resp.status_code)
                    if attempt == 2:
                        raise FeatureDisabled(f"Embedding failed: {resp.status_code}")
                    await asyncio.sleep(2 ** attempt)

        return all_embeddings

    async def embed_query(self, query: str) -> List[float]:
        res = await self.embed_texts([query])
        return res[0] if res else []
