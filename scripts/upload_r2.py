"""Sube un .mp4 al bucket R2 de Firulais y devuelve la URL pública.

Cuenta Cloudflare nueva, bucket nuevo (`sabias-firulais-shorts`), key API nueva.
Todos los valores llegan por env vars que el workflow inyecta desde Secrets.

URL pública la sirve Cloudflare desde el dominio `pub-xxxxxxxx.r2.dev`
(activado en Settings → Public Access del bucket).
"""
from __future__ import annotations

import hashlib
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import boto3
from botocore.config import Config

log = logging.getLogger("firulais.r2")


REQUIRED_ENV_VARS = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
    "R2_PUBLIC_DOMAIN",
)


@dataclass
class R2Config:
    account_id: str
    access_key_id: str
    secret_access_key: str
    bucket: str
    public_domain: str

    @classmethod
    def from_env(cls) -> "R2Config":
        missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
        if missing:
            raise EnvironmentError(f"R2: faltan variables {missing}")
        return cls(
            account_id=os.environ["R2_ACCOUNT_ID"],
            access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            bucket=os.environ["R2_BUCKET"],
            public_domain=os.environ["R2_PUBLIC_DOMAIN"],
        )

    @property
    def endpoint(self) -> str:
        return f"https://{self.account_id}.r2.cloudflarestorage.com"


def _make_client(cfg: R2Config):
    return boto3.client(
        "s3",
        endpoint_url=cfg.endpoint,
        aws_access_key_id=cfg.access_key_id,
        aws_secret_access_key=cfg.secret_access_key,
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


def _slug_for(path: Path) -> str:
    """Genera key única tipo `firulais/<epoch>-<short_hash>-<filename>`."""
    digest = hashlib.sha1(path.read_bytes()).hexdigest()[:10]
    epoch = int(time.time())
    return f"firulais/{epoch}-{digest}-{path.name}"


def upload(path: Path, key: Optional[str] = None, content_type: str = "video/mp4") -> str:
    """Sube el archivo, devuelve URL pública. Levanta si falla."""
    if not path.exists():
        raise FileNotFoundError(path)
    cfg = R2Config.from_env()
    object_key = key or _slug_for(path)
    client = _make_client(cfg)
    log.info("[r2] subiendo %s → %s/%s (%dKB)",
             path.name, cfg.bucket, object_key, path.stat().st_size // 1024)
    client.upload_file(
        str(path),
        cfg.bucket,
        object_key,
        ExtraArgs={
            "ContentType": content_type,
            "CacheControl": "public, max-age=86400",
            "Metadata": {"channel": "sabias-firulais"},
        },
    )
    return f"https://{cfg.public_domain}/{object_key}"


def _cli(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(argv) < 2:
        print("Uso: upload_r2.py <archivo.mp4> [key_opcional]", file=sys.stderr)
        return 2
    path = Path(argv[1])
    key = argv[2] if len(argv) > 2 else None
    print(upload(path, key=key))
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))
