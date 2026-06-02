"""Lightweight JSON-backed playlist storage for the music cog.

The original cog expected a small helper module named ``playlist_manager``.  This
implementation keeps the same API and stores server playlists in ``playlists.json``.
It also understands the older simple format used by the previous bot.py:

    {"guild_id": {"Playlist name": ["song query", ...]}}

and normalizes it in memory to the richer format used by ``new_cog.py``.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

PLAYLISTS_FILE = Path("playlists.json")


def _empty_store() -> dict[str, dict[str, dict[str, Any]]]:
    return {}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", (value or "playlist").strip()).strip("-")
    return slug[:48] or "playlist"


def _track_from_legacy_query(query: str) -> dict[str, Any]:
    return {
        "title": str(query or "Unknown title"),
        "uploader": "Unknown",
        "duration": 0,
        "web_url": "",
    }


def _normalize_playlist(pid: str, raw: Any, fallback_name: str = "Playlist") -> dict[str, Any]:
    if isinstance(raw, list):
        return {
            "id": pid,
            "name": fallback_name,
            "uid": 0,
            "creator_id": 0,
            "creator_name": "Unknown",
            "tracks": [_track_from_legacy_query(q) for q in raw],
        }

    if not isinstance(raw, dict):
        raw = {}

    tracks = raw.get("tracks", [])
    if not isinstance(tracks, list):
        tracks = []

    normalized_tracks: list[dict[str, Any]] = []
    for track in tracks:
        if isinstance(track, dict):
            normalized_tracks.append({
                "title": track.get("title") or track.get("name") or "Unknown title",
                "uploader": track.get("uploader") or track.get("author") or "Unknown",
                "duration": int(track.get("duration") or 0),
                "web_url": track.get("web_url") or track.get("url") or "",
            })
        else:
            normalized_tracks.append(_track_from_legacy_query(str(track)))

    creator_id = raw.get("uid") or raw.get("creator_id") or 0
    return {
        "id": raw.get("id") or pid,
        "name": raw.get("name") or fallback_name,
        "uid": creator_id,
        "creator_id": creator_id,
        "creator_name": raw.get("creator_name") or raw.get("creator") or "Unknown",
        "tracks": normalized_tracks,
    }


def _load() -> dict[str, dict[str, dict[str, Any]]]:
    if not PLAYLISTS_FILE.exists():
        return _empty_store()
    try:
        with PLAYLISTS_FILE.open("r", encoding="utf-8") as fp:
            raw = json.load(fp)
    except Exception:
        return _empty_store()

    if not isinstance(raw, dict):
        return _empty_store()

    store: dict[str, dict[str, dict[str, Any]]] = {}
    for guild_id, guild_playlists in raw.items():
        if not isinstance(guild_playlists, dict):
            continue
        normalized: dict[str, dict[str, Any]] = {}
        for key, playlist in guild_playlists.items():
            if isinstance(playlist, dict) and playlist.get("tracks") is not None:
                pid = str(playlist.get("id") or key)
                fallback_name = str(playlist.get("name") or key)
            else:
                pid = _slugify(str(key))
                fallback_name = str(key)
            while pid in normalized:
                pid = f"{pid}-{uuid.uuid4().hex[:6]}"
            normalized[pid] = _normalize_playlist(pid, playlist, fallback_name)
        store[str(guild_id)] = normalized
    return store


def _save(store: dict[str, dict[str, dict[str, Any]]]) -> None:
    with PLAYLISTS_FILE.open("w", encoding="utf-8") as fp:
        json.dump(store, fp, indent=2, ensure_ascii=False)


def get_guild_playlists(guild_id: int | str) -> dict[str, dict[str, Any]]:
    return _load().get(str(guild_id), {})


def get_playlist(guild_id: int | str, playlist_id: str) -> dict[str, Any] | None:
    return get_guild_playlists(guild_id).get(str(playlist_id))


def create_playlist(
    guild_id: int | str,
    name: str,
    creator_id: int | str,
    creator_name: str,
    *,
    max_playlists: int | None = None,
) -> tuple[str | None, str | None]:
    store = _load()
    guild_key = str(guild_id)
    guild_playlists = store.setdefault(guild_key, {})

    if max_playlists is not None and len(guild_playlists) >= max_playlists:
        return None, f"Playlist limit reached ({max_playlists})."

    clean_name = (name or "").strip()
    if not clean_name:
        return None, "Playlist name cannot be empty."

    if any(pl.get("name", "").casefold() == clean_name.casefold() for pl in guild_playlists.values()):
        return None, "A playlist with that name already exists."

    pid = _slugify(clean_name)
    if pid in guild_playlists:
        pid = f"{pid}-{uuid.uuid4().hex[:6]}"

    playlist = {
        "id": pid,
        "name": clean_name,
        "uid": int(creator_id or 0),
        "creator_id": int(creator_id or 0),
        "creator_name": creator_name or "Unknown",
        "tracks": [],
    }
    guild_playlists[pid] = playlist
    _save(store)
    return pid, None


def add_tracks(
    guild_id: int | str,
    playlist_id: str,
    tracks: list[dict[str, Any]],
    *,
    max_tracks: int | None = None,
) -> tuple[int, int]:
    store = _load()
    playlist = store.get(str(guild_id), {}).get(str(playlist_id))
    if playlist is None:
        return 0, len(tracks)

    existing = playlist.setdefault("tracks", [])
    added = 0
    skipped = 0
    for track in tracks:
        if max_tracks is not None and len(existing) >= max_tracks:
            skipped += 1
            continue
        if not isinstance(track, dict):
            skipped += 1
            continue
        existing.append(_normalize_playlist("track", {"tracks": [track]}, "track")["tracks"][0])
        added += 1

    _save(store)
    return added, skipped


def remove_track(guild_id: int | str, playlist_id: str, index: int) -> bool:
    store = _load()
    playlist = store.get(str(guild_id), {}).get(str(playlist_id))
    if playlist is None:
        return False
    tracks = playlist.get("tracks", [])
    if not isinstance(tracks, list) or index < 0 or index >= len(tracks):
        return False
    tracks.pop(index)
    _save(store)
    return True


def move_track(guild_id: int | str, playlist_id: str, old_index: int, new_index: int) -> bool:
    store = _load()
    playlist = store.get(str(guild_id), {}).get(str(playlist_id))
    if playlist is None:
        return False
    tracks = playlist.get("tracks", [])
    if not isinstance(tracks, list):
        return False
    if old_index < 0 or old_index >= len(tracks) or new_index < 0 or new_index >= len(tracks):
        return False
    track = tracks.pop(old_index)
    tracks.insert(new_index, track)
    _save(store)
    return True


def delete_playlist(guild_id: int | str, playlist_id: str) -> bool:
    store = _load()
    guild_playlists = store.get(str(guild_id), {})
    if str(playlist_id) not in guild_playlists:
        return False
    del guild_playlists[str(playlist_id)]
    _save(store)
    return True
