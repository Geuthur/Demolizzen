"""Stand-ins for the HTTP session and images used by level card tests."""

# Standard Library
from io import BytesIO

# Third Party
from PIL import Image


def png(size=(32, 32), colour=(200, 30, 30, 255)) -> bytes:
    """A small valid PNG."""
    output = BytesIO()
    Image.new("RGBA", size, colour).save(output, format="PNG")
    return output.getvalue()


class FakeContent:
    def __init__(self, data: bytes):
        self._data = data

    async def iter_chunked(self, size: int):
        for start in range(0, len(self._data), size):
            yield self._data[start : start + size]


class FakeResponse:
    def __init__(self, data: bytes = b"", status: int = 200, error=None):
        self.status = status
        self.content = FakeContent(data)
        self._error = error

    async def __aenter__(self):
        if self._error is not None:
            raise self._error
        return self

    async def __aexit__(self, *exc_info):
        return False


class FakeSession:
    """Answers GET requests from a dict of url -> FakeResponse factory or bytes."""

    def __init__(self, responses=None, default: bytes | None = None):
        self.responses = responses or {}
        self.default = default
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        answer = self.responses.get(url, self.default)
        if isinstance(answer, FakeResponse):
            return answer
        if answer is None:
            return FakeResponse(status=404)
        return FakeResponse(answer)
