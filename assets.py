"""Descarga y ubicacion de los recursos (sprites animados y gritos).

Los sprites animados salen del repo de PokeAPI (sprites de 5a generacion) y
los gritos de su repo de "cries". Se descargan una sola vez a assets/.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

ASSETS_DIR = Path(__file__).parent / "assets"

SPRITE_URL = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/"
    "versions/generation-v/black-white/animated/{id}.gif"
)
CRY_URL = "https://raw.githubusercontent.com/PokeAPI/cries/main/cries/pokemon/latest/{id}.ogg"

_UA = {"User-Agent": "pokedex-gestual/1.0"}


def sprite_path(pokemon_id: int) -> Path:
    return ASSETS_DIR / f"{pokemon_id}.gif"


def cry_path(pokemon_id: int) -> Path:
    return ASSETS_DIR / f"{pokemon_id}.ogg"


def _download(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = resp.read()
        if not data:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return True
    except (urllib.error.URLError, OSError) as exc:
        print(f"  no pude descargar {url.rsplit('/', 1)[-1]}: {exc}")
        return False


def ensure_assets(pokemon_ids, quiet=False) -> dict[str, int]:
    """Descarga lo que falte. Devuelve un conteo de lo que quedo disponible."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    faltantes = [
        (url.format(id=pid), path)
        for pid in pokemon_ids
        for url, path in ((SPRITE_URL, sprite_path(pid)), (CRY_URL, cry_path(pid)))
        if not path.exists()
    ]
    if faltantes and not quiet:
        print(f"Descargando {len(faltantes)} recursos a {ASSETS_DIR.name}/ ...")
    for url, path in faltantes:
        _download(url, path)

    listos = {
        "sprites": sum(sprite_path(p).exists() for p in pokemon_ids),
        "gritos": sum(cry_path(p).exists() for p in pokemon_ids),
    }
    if faltantes and not quiet:
        print(f"  sprites: {listos['sprites']}/{len(pokemon_ids)} | "
              f"gritos: {listos['gritos']}/{len(pokemon_ids)}")
    return listos


if __name__ == "__main__":
    import config as cfg

    ensure_assets([p["id"] for p in cfg.POKEMON.values()])
