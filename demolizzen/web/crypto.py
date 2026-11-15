"""Encrypts what the panel keeps in the session cookie."""

# Standard Library
import base64
import json
from functools import lru_cache

# Third Party
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# Django
from django.conf import settings


@lru_cache(maxsize=4)
def _cipher(secret_key: str) -> Fernet:
    """The cipher for a secret key. The encryption key is derived from it, so
    it is never used directly and differs from the key that signs the cookie."""
    key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"demolizzen.web.session",
        info=b"session cookie encryption",
    ).derive(secret_key.encode())
    return Fernet(base64.urlsafe_b64encode(key))


class EncryptedJSONSerializer:
    """Session serializer: JSON, encrypted with a key derived from ``SECRET_KEY``.

    Django signs the session cookie, which protects it from being changed but
    leaves it readable. The session holds the user's Discord token, so the
    content is encrypted as well (Fernet: AES with an integrity check). Without
    the secret key nobody can read it, the visitor included.
    """

    def dumps(self, obj) -> bytes:
        data = json.dumps(obj, separators=(",", ":")).encode()
        return _cipher(settings.SECRET_KEY).encrypt(data)

    def loads(self, data: bytes):
        return json.loads(_cipher(settings.SECRET_KEY).decrypt(data))
