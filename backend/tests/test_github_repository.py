import pytest

from app.services.github_repository import (
    GitHubRepositoryError,
    canonicalize_github_url,
    fetch_repository_preview,
)
from app.schemas.service import ServiceCreate


def test_canonicalize_github_repository_urls():
    assert canonicalize_github_url(" https://github.com/OpenAI/codex.git ") == (
        "OpenAI", "codex", "https://github.com/OpenAI/codex"
    )


def test_service_input_normalizes_and_validates_linked_repository():
    service = ServiceCreate(
        identifier="sample-app",
        name="Sample App",
        repository_url="https://github.com/OpenAI/codex.git",
    )
    assert service.repository_url == "https://github.com/OpenAI/codex"
    with pytest.raises(ValueError):
        ServiceCreate(identifier="sample-app", name="Sample App", repository_url="https://attacker.example/owner/repo")


@pytest.mark.parametrize("url", [
    "http://github.com/owner/repo",
    "https://github.com.attacker.example/owner/repo",
    "https://user:password@github.com/owner/repo",
    "https://github.com/owner/repo/tree/main",
    "https://github.com/owner%2Frepo/project",
    "https://github.com/owner/repo?redirect=attacker.example",
    "https://github.com:8443/owner/repo",
])
def test_rejects_noncanonical_or_unsafe_github_urls(url):
    with pytest.raises(ValueError):
        canonicalize_github_url(url)


class FakeResponse:
    def __init__(self, status_code, data, headers=None):
        self.status_code = status_code
        self._data = data
        self.headers = headers or {}

    def json(self):
        return self._data


class FakeGitHubClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        if url.endswith("/repos/owner/repo"):
            return FakeResponse(200, {
                "full_name": "owner/repo",
                "default_branch": "main&other=value",
                "language": "Python",
                "private": True,
                "archived": False,
                "disabled": False,
            })
        return FakeResponse(200, [
            {"type": "file", "name": "pyproject.toml"},
            {"type": "file", "name": "README.md"},
            {"type": "dir", "name": "requirements.txt"},
            {"type": "file", "name": "unrecognized.txt"},
        ])


@pytest.mark.asyncio
async def test_preview_uses_fixed_github_host_encodes_branch_and_only_returns_manifest_names(monkeypatch):
    import app.services.github_repository as github

    clients = []
    monkeypatch.setattr(github.httpx, "AsyncClient", lambda **kwargs: clients.append(FakeGitHubClient(**kwargs)) or clients[-1])

    result = await fetch_repository_preview("https://github.com/owner/repo", "one-time-token")
    client = clients[0]

    assert result["full_name"] == "owner/repo"
    assert result["manifest_files"] == ["pyproject.toml"]
    assert client.kwargs["follow_redirects"] is False
    assert client.kwargs["trust_env"] is False
    assert all(request[0].startswith("https://api.github.com/") for request in client.requests)
    assert client.requests[0][1]["headers"]["Authorization"] == "Bearer one-time-token"
    assert client.requests[1][1]["params"]["ref"] == "main&other=value"


@pytest.mark.asyncio
async def test_private_repository_failure_is_safe_and_does_not_echo_token(monkeypatch):
    import app.services.github_repository as github

    class NotFoundClient(FakeGitHubClient):
        async def get(self, url, **kwargs):
            return FakeResponse(404, {"message": "Not Found"})

    monkeypatch.setattr(github.httpx, "AsyncClient", lambda **kwargs: NotFoundClient())
    secret = "github_pat_never_echo_this"
    with pytest.raises(GitHubRepositoryError) as error:
        await fetch_repository_preview("https://github.com/owner/repo", secret)
    assert "not found or inaccessible" in error.value.message.lower()
    assert secret not in error.value.message
