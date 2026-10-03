"""Local event buffering and disconnection/recovery handling."""
from collections import deque
from datetime import datetime, timezone
import json
import os
from typing import List, Dict, Any, Optional


class EventBuffer:
    """
    Simulates a branch/edge local buffer when connectivity to central collector is interrupted.
    Maintains events in memory and optionally persists to local disk to guarantee zero data loss.
    """

    def __init__(self, persistence_file: Optional[str] = None):
        self.persistence_file = persistence_file
        self._buffer: deque = deque()
        self._is_interrupted: bool = False
        self._load_persisted()

    def set_interrupted(self, interrupted: bool):
        """Toggle simulation of network/collector interruption."""
        self._is_interrupted = interrupted

    @property
    def is_interrupted(self) -> bool:
        return self._is_interrupted

    def push(self, event_data: Dict[str, Any]):
        """Store an event in the local buffer."""
        self._buffer.append(event_data)
        if self.persistence_file:
            self._persist()

    def size(self) -> int:
        return len(self._buffer)

    def drain_all(self) -> List[Dict[str, Any]]:
        """
        Drain all buffered events for ordered replay and recovery.
        Sorts buffered events by event_time before returning.
        """
        events = list(self._buffer)
        self._buffer.clear()
        if self.persistence_file and os.path.exists(self.persistence_file):
            try:
                os.remove(self.persistence_file)
            except OSError:
                pass
        return events

    def _persist(self):
        if not self.persistence_file:
            return
        os.makedirs(os.path.dirname(os.path.abspath(self.persistence_file)), exist_ok=True)
        # Convert datetimes to isoformat for storage
        serializable = []
        for item in self._buffer:
            copied = dict(item)
            for k, v in copied.items():
                if isinstance(v, datetime):
                    copied[k] = v.isoformat()
            serializable.append(copied)
        with open(self.persistence_file, "w") as f:
            json.dump(serializable, f)

    def _load_persisted(self):
        if self.persistence_file and os.path.exists(self.persistence_file):
            try:
                with open(self.persistence_file, "r") as f:
                    data = json.load(f)
                    for item in data:
                        for k, v in item.items():
                            if k in ("event_time", "arrival_time", "created_at") and isinstance(v, str):
                                item[k] = datetime.fromisoformat(v)
                        self._buffer.append(item)
            except Exception:
                pass
