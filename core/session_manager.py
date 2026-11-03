"""In-memory session registry with a lock for thread safety."""
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


@dataclass
class Session:
    id: str
    url: str
    filename: Optional[str] = None
    platform: str = "generic"
    chat_title: Optional[str] = None      # NEW: extracted chat name
    status: str = "starting"
    message: str = ""
    pdf_path: Optional[str] = None
    vnc_url: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    procs: list = field(default_factory=list)
    cancel_requested: bool = False
    pinned: bool = False

    def touch(self, status: str = None, message: str = None):
        if status is not None:
            self.status = status
        if message is not None:
            self.message = message
        self.updated_at = datetime.utcnow()


class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()

    def add(self, session: Session):
        with self._lock:
            self._sessions[session.id] = session

    def get(self, sid: str) -> Optional[Session]:
        with self._lock:
            return self._sessions.get(sid)

    def remove(self, sid: str):
        with self._lock:
            self._sessions.pop(sid, None)

    def all(self):
        with self._lock:
            return list(self._sessions.values())

    def active_count(self) -> int:
        with self._lock:
            return sum(
                1 for s in self._sessions.values()
                if s.status not in ("done", "failed")
            )

    def sweepable(self, max_age_seconds: int):
        now = datetime.utcnow()
        with self._lock:
            return [
                s for s in self._sessions.values()
                if not s.pinned
                and (now - s.created_at).total_seconds() > max_age_seconds
                and s.status not in ("starting", "loading", "rendering",
                                     "awaiting_captcha")
            ]


manager = SessionManager()
