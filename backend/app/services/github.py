import os
from typing import Any, Dict, List, Optional, Tuple
import httpx
from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import logger


class GitHubService:
    def __init__(self):
        self.settings = settings
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"{self.settings.APP_NAME}/{self.settings.APP_VERSION}",
        }
        if self.settings.GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {self.settings.GITHUB_TOKEN}"

        self.client = httpx.AsyncClient(
            base_url=self.settings.GITHUB_API_BASE,
            headers=headers,
            timeout=self.settings.GITHUB_REQUEST_TIMEOUT_S,
            follow_redirects=True,
        )

    async def close(self):
        await self.client.aclose()

    def _handle_error(self, response: httpx.Response, owner: str, repo: str):
        if response.status_code == 404:
            raise AppError(
                code="REPO_NOT_FOUND",
                message=f"Repository {owner}/{repo} not found on GitHub.",
                status_code=404,
            )
        elif response.status_code == 403:
            remaining = response.headers.get("x-ratelimit-remaining")
            if remaining == "0":
                raise AppError(
                    code="GITHUB_RATE_LIMIT",
                    message="GitHub API rate limit exceeded. Set a GITHUB_TOKEN in backend configuration.",
                    status_code=429,
                )
            raise AppError(
                code="REPO_PRIVATE",
                message=f"Repository {owner}/{repo} is private or inaccessible. RepoPilot supports public repositories.",
                status_code=403,
            )
        elif response.status_code >= 400:
            raise AppError(
                code="INTERNAL_ERROR",
                message=f"GitHub API returned error: {response.status_code}",
                status_code=502,
                details={"status_code": response.status_code, "body": response.text[:200]},
            )

    async def get_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        resp = await self.client.get(f"/repos/{owner}/{repo}")
        self._handle_error(resp, owner, repo)
        data = resp.json()
        if data.get("private"):
            raise AppError(
                code="REPO_PRIVATE",
                message="This repository is private. RepoPilot can analyse public repositories only.",
                status_code=403,
            )
        return data

    async def get_languages(self, owner: str, repo: str) -> Dict[str, int]:
        resp = await self.client.get(f"/repos/{owner}/{repo}/languages")
        if resp.status_code == 200:
            return resp.json()
        return {}

    async def get_branch_sha(self, owner: str, repo: str, branch: str) -> Optional[str]:
        resp = await self.client.get(f"/repos/{owner}/{repo}/commits/{branch}")
        if resp.status_code == 200:
            data = resp.json()
            return data.get("sha")
        return None

    async def get_issue(self, owner: str, repo: str, number: int) -> Dict[str, Any]:
        resp = await self.client.get(f"/repos/{owner}/{repo}/issues/{number}")
        if resp.status_code == 404:
            raise AppError(
                code="NOT_FOUND",
                message=f"Issue #{number} not found in {owner}/{repo}.",
                status_code=404,
            )
        self._handle_error(resp, owner, repo)
        issue_data = resp.json()

        comments = []
        if issue_data.get("comments", 0) > 0:
            comm_resp = await self.client.get(f"/repos/{owner}/{repo}/issues/{number}/comments?per_page=10")
            if comm_resp.status_code == 200:
                comments = [c.get("body", "") for c in comm_resp.json() if c.get("body")]

        return {
            "title": issue_data.get("title", ""),
            "body": issue_data.get("body") or "",
            "number": number,
            "comments": comments,
        }

    async def download_tarball(self, owner: str, repo: str, ref: str, dest_path: str) -> int:
        """
        Streams tarball from GitHub and aborts if it exceeds MAX_REPO_SIZE_MB.
        Returns the downloaded size in bytes.
        """
        max_bytes = self.settings.MAX_REPO_SIZE_MB * 1024 * 1024
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        tarball_url = f"/repos/{owner}/{repo}/tarball/{ref}"
        async with self.client.stream("GET", tarball_url) as response:
            self._handle_error(response, owner, repo)

            total_bytes = 0
            with open(dest_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        f.close()
                        if os.path.exists(dest_path):
                            os.remove(dest_path)
                        raise AppError(
                            code="REPO_TOO_LARGE",
                            message=f"Repository exceeds the {self.settings.MAX_REPO_SIZE_MB} MB limit.",
                            status_code=413,
                        )
                    f.write(chunk)

        logger.info("Downloaded tarball for %s/%s (%d bytes)", owner, repo, total_bytes)
        return total_bytes
