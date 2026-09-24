"""Cliente opcional da API oficial FIRST para avatares de equipes FRC."""

from __future__ import annotations

import base64
import os

from .apiclient import get_json
from . import config as C

BASE = "https://frc-api.firstinspires.org/v3.0"
AVATAR_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "web", "assets", "avatars")


def _credentials() -> tuple[str | None, str | None]:
    values = {
        "FIRST_API_USERNAME": os.environ.get("FIRST_API_USERNAME"),
        "FIRST_API_AUTH_KEY": os.environ.get("FIRST_API_AUTH_KEY"),
    }
    env_path = os.path.join(os.path.dirname(__file__), os.pardir, ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                for key in values:
                    if not values[key] and line.startswith(key + "="):
                        values[key] = line.split("=", 1)[1].strip().strip('"').strip("'")
    return values["FIRST_API_USERNAME"], values["FIRST_API_AUTH_KEY"]


def enabled() -> bool:
    return all(_credentials())


def _headers() -> dict:
    username, auth_key = _credentials()
    if not username or not auth_key:
        raise RuntimeError("Defina FIRST_API_USERNAME e FIRST_API_AUTH_KEY")
    token = base64.b64encode(f"{username}:{auth_key}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Accept": "application/json"}


def _avatar_record(payload: dict, team_number: int) -> dict | None:
    rows = payload.get("teams") or payload.get("Teams") or payload.get("avatars") or []
    for row in rows:
        number = row.get("teamNumber") or row.get("TeamNumber") or row.get("team")
        if str(number) == str(team_number):
            return row
    return rows[0] if len(rows) == 1 else None


def avatar_for_team(team_number: int, rookie_year: int | None = None) -> str | None:
    """Baixa o avatar mais recente disponível e retorna sua URL pública local."""
    if not enabled():
        return None
    os.makedirs(AVATAR_DIR, exist_ok=True)
    output = os.path.join(AVATAR_DIR, f"{team_number}.png")
    if os.path.exists(output):
        return f"/assets/avatars/{team_number}.png"

    first_season = max(C.FIRST_SEASON, rookie_year or C.FIRST_SEASON)
    for season in range(C.LAST_SEASON, first_season - 1, -1):
        url = f"{BASE}/{season}/avatars?teamNumber={team_number}"
        # Avatar ausente é comum; uma tentativa curta evita atrasar todo o build.
        payload = get_json(
            url, headers=_headers(), allow_empty_on_fail=True, retries=1, timeout=8)
        row = _avatar_record(payload or {}, team_number)
        encoded = (row or {}).get("encodedAvatar") or (row or {}).get("avatar") or (row or {}).get("Avatar")
        if not encoded:
            continue
        if "," in encoded and encoded.lower().startswith("data:"):
            encoded = encoded.split(",", 1)[1]
        try:
            image = base64.b64decode(encoded)
        except (ValueError, TypeError):
            continue
        if not image.startswith(b"\x89PNG\r\n\x1a\n"):
            continue
        tmp = output + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(image)
        os.replace(tmp, output)
        return f"/assets/avatars/{team_number}.png"
    return None
