"""Limitation de débit par adresse IP, en fenêtre glissante, en mémoire du processus.

Complète le blocage par poste (`device_id`, choisi par le client) des PIN faux : ici, toutes
les tentatives comptent, quel que soit le poste annoncé. Chaque processus gunicorn a son
propre compteur : avec `-w 2`, la limite effective peut aller jusqu'au double.
"""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Request

from caisse.config import get_settings
from caisse.errors import RateLimitExceededError


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: float) -> int:
        """Enregistre une requête ; 0 si elle passe, sinon l'attente en secondes."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return max(1, int(hits[0] + window_seconds - now + 0.999))
            hits.append(now)
            return 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def per_ip(setting: str, window_seconds: int = 60) -> Callable[[Request], None]:
    """Dépendance FastAPI : `setting` nomme la limite dans `Settings` (requêtes par minute)."""

    def _check(request: Request) -> None:
        limit = int(getattr(get_settings(), setting))
        ip = request.client.host if request.client else "inconnue"
        retry_after = limiter.hit(f"{request.url.path}:{ip}", limit, window_seconds)
        if retry_after:
            raise RateLimitExceededError(retry_after, limit=limit, window_seconds=window_seconds)

    return _check
