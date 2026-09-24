"""
Cliente HTTP minimalista com cache em disco e retry. Só stdlib (urllib).

Cache: data/raw/<slug>.json   (ative/desative com use_cache)
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

RAW_DIR = os.path.join(os.path.dirname(__file__), "raw")
os.makedirs(RAW_DIR, exist_ok=True)

# Quando True, ignora o cache em disco para leitura (mas continua gravando).
FORCE_REFRESH = False
CACHE_ONLY = False


class HttpError(Exception):
    def __init__(self, status, url, body=""):
        super().__init__(f"HTTP {status} em {url}")
        self.status = status
        self.url = url
        self.body = body


def _slug(url: str) -> str:
    p = urllib.parse.urlparse(url)
    raw = (p.path + ("?" + p.query if p.query else "")).strip("/")
    safe = "".join(c if c.isalnum() or c in "-._" else "_" for c in raw)
    return safe[:180] or "root"


def get_json(
    url: str,
    headers: dict | None = None,
    *,
    use_cache: bool = True,
    cache_dir: str = RAW_DIR,
    retries: int = 4,
    backoff: float = 2.0,
    timeout: int = 30,
    allow_empty_on_fail: bool = False,
):
    """
    GET url -> objeto JSON. Cacheia respostas 200 em disco.
    allow_empty_on_fail: se todas as tentativas falharem, retorna None em vez de levantar.
    """
    cache_path = os.path.join(cache_dir, _slug(url) + ".json")
    if use_cache and not FORCE_REFRESH and os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    if CACHE_ONLY:
        if allow_empty_on_fail:
            return None
        raise RuntimeError("Dados não disponíveis no cache: " + url)

    req = urllib.request.Request(url, headers=headers or {})
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            tmp = f"{cache_path}.{os.getpid()}.{threading.get_ident()}.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
            os.replace(tmp, cache_path)  # troca atômica -> seguro entre threads
            return payload
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            last_err = HttpError(e.code, url, body)
            # 404 não adianta repetir
            if e.code == 404:
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
        if attempt < retries:
            time.sleep(backoff * attempt)

    if allow_empty_on_fail:
        return None
    raise last_err
