"""In-memory session store with simple TTL cleanup.

Sufficient for the single-instance free-tier demo deployment. For multi-user
production use, replace with Redis or a database (see SECURITY.md).
"""

from __future__ import annotations

import threading
import time

from app.rag.pipeline import Session, new_session

SESSION_TTL_SECONDS = 2 * 60 * 60  # 2 hours
MAX_SESSIONS = 500


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, tuple[Session, float]] = {}
        self._lock = threading.Lock()

    def create(self) -> Session:
        session = new_session()
        with self._lock:
            self._cleanup_locked()
            self._sessions[session.session_id] = (session, time.time())
        return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry is None:
                return None
            session, _ts = entry
            self._sessions[session_id] = (session, time.time())  # touch
            return session

    def reset(self, session: Session) -> None:
        fresh = new_session()
        fresh.session_id = session.session_id
        with self._lock:
            self._sessions[session.session_id] = (fresh, time.time())
        session.status = "empty"
        session.document_name = None
        session.document_type = None
        session.chunk_count = 0
        session.chunks_by_id = {}
        session.store = None
        session.retriever = None
        session.history = []
        session.error = None

    def _cleanup_locked(self) -> None:
        now = time.time()
        expired = [sid for sid, (_s, ts) in self._sessions.items() if now - ts > SESSION_TTL_SECONDS]
        for sid in expired:
            del self._sessions[sid]
        while len(self._sessions) >= MAX_SESSIONS:
            oldest = min(self._sessions.items(), key=lambda kv: kv[1][1])[0]
            del self._sessions[oldest]


store = SessionStore()
