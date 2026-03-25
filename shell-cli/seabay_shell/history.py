"""Chat history management for Seabay Shell."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class ChatMessage:
    """A single chat message."""

    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: float = field(default_factory=time.time)
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list[dict]] = None
    name: Optional[str] = None  # tool name for tool messages

    def to_llm_message(self) -> dict:
        """Convert to OpenAI-compatible message format."""
        msg: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.name and self.role == "tool":
            msg["name"] = self.name
        return msg

    def to_dict(self) -> dict:
        """Serialize for persistence."""
        d: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.name:
            d["name"] = self.name
        return d

    @classmethod
    def from_dict(cls, data: dict) -> ChatMessage:
        return cls(
            role=data["role"],
            content=data.get("content", ""),
            timestamp=data.get("timestamp", time.time()),
            tool_call_id=data.get("tool_call_id"),
            tool_calls=data.get("tool_calls"),
            name=data.get("name"),
        )


class ChatHistory:
    """Manages conversation history with persistence."""

    HISTORY_DIR = Path.home() / ".seabay-shell" / "history"

    def __init__(self, max_messages: int = 100, session_id: Optional[str] = None):
        self.max_messages = max_messages
        self.session_id = session_id or f"session_{int(time.time())}"
        self._messages: list[ChatMessage] = []

    @property
    def messages(self) -> list[ChatMessage]:
        return list(self._messages)

    def add(self, role: str, content: str, **kwargs: Any) -> ChatMessage:
        """Add a message to history."""
        msg = ChatMessage(role=role, content=content, **kwargs)
        self._messages.append(msg)
        # Trim if over limit (keep system messages)
        if len(self._messages) > self.max_messages:
            system_msgs = [m for m in self._messages if m.role == "system"]
            other_msgs = [m for m in self._messages if m.role != "system"]
            # Keep last N non-system messages
            keep = self.max_messages - len(system_msgs)
            self._messages = system_msgs + other_msgs[-keep:]
        return msg

    def add_tool_call(self, tool_call_id: str, name: str, content: str) -> ChatMessage:
        """Add a tool response message."""
        return self.add(
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
            name=name,
        )

    def add_assistant_with_tools(self, content: str, tool_calls: list[dict]) -> ChatMessage:
        """Add an assistant message that includes tool calls."""
        return self.add(
            role="assistant",
            content=content or "",
            tool_calls=tool_calls,
        )

    def get_llm_messages(self) -> list[dict]:
        """Get messages in OpenAI-compatible format for LLM calls."""
        return [m.to_llm_message() for m in self._messages]

    def clear(self) -> None:
        """Clear all non-system messages."""
        self._messages = [m for m in self._messages if m.role == "system"]

    def save(self) -> None:
        """Persist current session to disk."""
        self.HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        filepath = self.HISTORY_DIR / f"{self.session_id}.json"
        data = {
            "session_id": self.session_id,
            "messages": [m.to_dict() for m in self._messages],
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load_session(cls, session_id: str, max_messages: int = 100) -> ChatHistory:
        """Load a previous session from disk."""
        history = cls(max_messages=max_messages, session_id=session_id)
        filepath = cls.HISTORY_DIR / f"{session_id}.json"
        if filepath.exists():
            with open(filepath) as f:
                data = json.load(f)
            for msg_data in data.get("messages", []):
                msg = ChatMessage.from_dict(msg_data)
                history._messages.append(msg)
        return history

    @classmethod
    def list_sessions(cls) -> list[str]:
        """List available session IDs."""
        if not cls.HISTORY_DIR.exists():
            return []
        return sorted(
            [p.stem for p in cls.HISTORY_DIR.glob("session_*.json")],
            reverse=True,
        )

    @property
    def message_count(self) -> int:
        return len(self._messages)

    @property
    def user_message_count(self) -> int:
        return sum(1 for m in self._messages if m.role == "user")
