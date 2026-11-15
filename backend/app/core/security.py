import re
from typing import Optional, Tuple
from app.core.errors import AppError


GITHUB_URL_REGEX = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]{1,100})/(?P<repo>[A-Za-z0-9_.-]{1,100})(?:/tree/(?P<branch>[^/\s]+(?:/[^/\s]+)*))?/?$"
)

GITHUB_ISSUE_URL_REGEX = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]{1,100})/(?P<repo>[A-Za-z0-9_.-]{1,100})/issues/(?P<number>\d+)/?$"
)


def parse_github_url(url: str) -> Tuple[str, str, Optional[str]]:
    url = url.strip()
    match = GITHUB_URL_REGEX.match(url)
    if not match:
        raise AppError(
            code="INVALID_URL",
            message="Invalid GitHub repository URL. Must be in format https://github.com/owner/repo",
            status_code=400,
        )
    owner = match.group("owner")
    repo = match.group("repo")
    if repo.endswith(".git"):
        repo = repo[:-4]
    branch = match.group("branch")
    return owner, repo, branch


def parse_github_issue_url(url: str) -> Tuple[str, str, int]:
    url = url.strip()
    match = GITHUB_ISSUE_URL_REGEX.match(url)
    if not match:
        raise AppError(
            code="INVALID_URL",
            message="Invalid GitHub issue URL. Must be in format https://github.com/owner/repo/issues/123",
            status_code=400,
        )
    owner = match.group("owner")
    repo = match.group("repo")
    if repo.endswith(".git"):
        repo = repo[:-4]
    number = int(match.group("number"))
    return owner, repo, number
