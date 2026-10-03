"""Read-only GitHub repository metadata lookup. Never clones or executes repo code."""
import re
from urllib.parse import urlsplit

import httpx


GITHUB_API = "https://api.github.com"
_OWNER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def canonicalize_github_url(value: str) -> tuple[str, str, str]:
    """Accept only a GitHub HTTPS repository URL; reject subpaths and URL tricks."""
    try:
        parsed = urlsplit(value.strip())
        if (
            parsed.scheme.lower() != "https"
            or (parsed.hostname or "").lower() != "github.com"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError
        parts = parsed.path.strip("/").split("/")
        if len(parts) != 2:
            raise ValueError
        owner, repository = parts
        if repository.lower().endswith(".git"):
            repository = repository[:-4]
        if not _OWNER.fullmatch(owner) or not _REPOSITORY.fullmatch(repository) or repository in {".", ".."}:
            raise ValueError
        return owner, repository, f"https://github.com/{owner}/{repository}"
    except (AttributeError, ValueError):
        raise ValueError("Enter a GitHub repository URL such as https://github.com/owner/repository.") from None


class GitHubRepositoryError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


async def fetch_repository_preview(url: str, access_token: str | None = None) -> dict:
    """Fetch basic repo metadata and manifest filenames via fixed GitHub API URLs."""
    owner, repository, canonical_url = canonicalize_github_url(url)
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "NexPulse-Repository-Connector",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    timeout = httpx.Timeout(6.0, connect=2.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            response = await client.get(f"{GITHUB_API}/repos/{owner}/{repository}", headers=headers)
            if response.status_code == 404:
                message = "Repository not found or inaccessible. For a private repository, provide a read-only token with access to it."
                raise GitHubRepositoryError(404, message)
            if response.status_code == 401:
                raise GitHubRepositoryError(401, "GitHub rejected the read-only token. Check that it is valid and not expired.")
            if response.status_code == 403:
                if response.headers.get("X-RateLimit-Remaining") == "0":
                    raise GitHubRepositoryError(429, "GitHub API rate limit reached. Wait before fetching this repository again.")
                raise GitHubRepositoryError(403, "GitHub denied repository access. Check the token's repository selection and read permissions.")
            if response.status_code != 200:
                raise GitHubRepositoryError(502, "GitHub could not provide repository metadata right now.")
            metadata = response.json()
            if not isinstance(metadata, dict):
                raise GitHubRepositoryError(502, "GitHub returned an invalid repository response.")

            contents = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repository}/contents",
                params={"ref": metadata.get("default_branch") or "main", "per_page": 100},
                headers=headers,
            )
            if contents.status_code == 403 and contents.headers.get("X-RateLimit-Remaining") == "0":
                raise GitHubRepositoryError(429, "GitHub API rate limit reached. Wait before fetching this repository again.")
            if contents.status_code != 200 or not isinstance(contents.json(), list):
                raise GitHubRepositoryError(502, "GitHub returned repository metadata but could not list its root files.")
            manifest_names = sorted(
                item["name"] for item in contents.json()
                if isinstance(item, dict) and item.get("type") == "file" and isinstance(item.get("name"), str)
                and item["name"] in {
                    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
                    "requirements.txt", "pyproject.toml", "Pipfile", "go.mod",
                    "Cargo.toml", "pom.xml", "build.gradle", "Gemfile", "composer.json",
                }
            )
    except GitHubRepositoryError:
        raise
    except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError):
        raise GitHubRepositoryError(503, "Could not reach GitHub. Try again shortly.") from None
    except (ValueError, TypeError, KeyError):
        raise GitHubRepositoryError(502, "GitHub returned an invalid repository response.") from None

    if metadata.get("disabled"):
        raise GitHubRepositoryError(422, "This GitHub repository is disabled and cannot be connected.")

    return {
        "full_name": metadata.get("full_name") or f"{owner}/{repository}",
        "repository_url": canonical_url,
        "description": metadata.get("description"),
        "default_branch": metadata.get("default_branch") or "main",
        "language": metadata.get("language"),
        "private": bool(metadata.get("private")),
        "archived": bool(metadata.get("archived")),
        "manifest_files": manifest_names,
    }
