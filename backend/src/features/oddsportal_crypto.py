"""OddsPortal (centroquote.it) payload decryption.

The encrypted backend feed decrypts as: outer base64 -> split(':', 1) ->
AES-CBC(PKCS7) with PBKDF2-HMAC-SHA256(1000 iters, fixed salt) -> gzip ->
JSON. The keys are fixed site-wide and embedded in the front-end bundle.
"""
from __future__ import annotations

import base64
import gzip
import json

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_PASS_B64 = "Sio4c1EhcCQ3YURfZlIyeVdAZ0huKjNiVnAjc0FkTGRfaw=="
_SALT_B64 = "NWI5YThmMmMzZTZkMWE0YjdjOGU5ZDBmMWEyYjNjNGQ="


def decrypt_payload(raw: bytes | str) -> dict:
    """Decrypt an OddsPortal .dat payload into its JSON dict."""
    if isinstance(raw, str):
        raw = raw.encode("latin-1")
    inner = base64.b64decode(raw).decode("latin-1")
    cipher_b64, iv_hex = inner.split(":", 1)
    ct = base64.b64decode(cipher_b64)
    iv = bytes.fromhex(iv_hex)
    passwd = base64.b64decode(_PASS_B64)
    salt = base64.b64decode(_SALT_B64)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt,
        iterations=1000, backend=default_backend(),
    )
    key = kdf.derive(passwd)
    dec = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend()).decryptor()
    pt = dec.update(ct) + dec.finalize()
    pad = pt[-1]
    if pad and pt[-pad:] == bytes([pad]) * pad:
        pt = pt[:-pad]
    if pt[:2] == b"\x1f\x8b":
        pt = gzip.decompress(pt)
    return json.loads(pt.decode("utf-8"))
