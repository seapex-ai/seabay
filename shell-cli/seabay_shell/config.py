"""Shell configuration — loads from ~/.seabay-shell.json or environment variables."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

CONFIG_FILE = Path.home() / ".seabay-shell.json"

# Environment variable names
ENV_API_URL = "SEABAY_API_URL"
ENV_API_KEY = "SEABAY_API_KEY"
ENV_LLM_URL = "SEABAY_LLM_URL"
ENV_LLM_MODEL = "SEABAY_LLM_MODEL"
ENV_LLM_API_KEY = "SEABAY_LLM_API_KEY"

# Defaults
DEFAULT_API_URL = "http://localhost:8000/v1"
DEFAULT_LLM_URL = "https://api.openai.com/v1"
DEFAULT_LLM_MODEL = "gpt-4o"


@dataclass
class ShellConfig:
    """Configuration for the Seabay Shell."""

    # Seabay API
    api_url: str = DEFAULT_API_URL
    api_key: str = ""

    # LLM configuration (OpenAI-compatible)
    llm_url: str = DEFAULT_LLM_URL
    llm_model: str = DEFAULT_LLM_MODEL
    llm_api_key: str = ""

    # Agent identity (set after connection)
    agent_id: Optional[str] = None
    agent_slug: Optional[str] = None
    agent_name: Optional[str] = None

    # Shell preferences
    max_history: int = 100
    show_tool_calls: bool = False
    theme: str = "default"

    @classmethod
    def load(cls) -> ShellConfig:
        """Load config from file, then overlay environment variables."""
        config = cls()

        # Load from file if exists
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    data = json.load(f)
                config.api_url = data.get("api_url", config.api_url)
                config.api_key = data.get("api_key", config.api_key)
                config.llm_url = data.get("llm_url", config.llm_url)
                config.llm_model = data.get("llm_model", config.llm_model)
                config.llm_api_key = data.get("llm_api_key", config.llm_api_key)
                config.agent_id = data.get("agent_id")
                config.agent_slug = data.get("agent_slug")
                config.agent_name = data.get("agent_name")
                config.max_history = data.get("max_history", config.max_history)
                config.show_tool_calls = data.get("show_tool_calls", config.show_tool_calls)
                config.theme = data.get("theme", config.theme)
            except (json.JSONDecodeError, OSError):
                pass

        # Also check local .seabay.json for agent credentials
        local_config = Path(".seabay.json")
        if local_config.exists():
            try:
                with open(local_config) as f:
                    data = json.load(f)
                if not config.api_key and data.get("api_key"):
                    config.api_key = data["api_key"]
                if not config.agent_id and data.get("agent_id"):
                    config.agent_id = data["agent_id"]
                if not config.agent_slug and data.get("slug"):
                    config.agent_slug = data["slug"]
                if data.get("api_url"):
                    config.api_url = data["api_url"]
            except (json.JSONDecodeError, OSError):
                pass

        # Environment overrides (highest priority)
        if os.environ.get(ENV_API_URL):
            config.api_url = os.environ[ENV_API_URL]
        if os.environ.get(ENV_API_KEY):
            config.api_key = os.environ[ENV_API_KEY]
        if os.environ.get(ENV_LLM_URL):
            config.llm_url = os.environ[ENV_LLM_URL]
        if os.environ.get(ENV_LLM_MODEL):
            config.llm_model = os.environ[ENV_LLM_MODEL]
        if os.environ.get(ENV_LLM_API_KEY):
            config.llm_api_key = os.environ[ENV_LLM_API_KEY]

        return config

    def save(self) -> None:
        """Persist current config to ~/.seabay-shell.json."""
        data = {
            "api_url": self.api_url,
            "api_key": self.api_key,
            "llm_url": self.llm_url,
            "llm_model": self.llm_model,
            "llm_api_key": self.llm_api_key,
            "agent_id": self.agent_id,
            "agent_slug": self.agent_slug,
            "agent_name": self.agent_name,
            "max_history": self.max_history,
            "show_tool_calls": self.show_tool_calls,
            "theme": self.theme,
        }
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)

    @property
    def is_configured(self) -> bool:
        """Check if minimum config is present."""
        return bool(self.api_key)

    @property
    def has_llm(self) -> bool:
        """Check if LLM is configured."""
        return bool(self.llm_api_key and self.llm_url)

    def validate(self) -> list[str]:
        """Return list of configuration issues."""
        issues = []
        if not self.api_key:
            issues.append("SEABAY_API_KEY not set (or api_key in config file)")
        if not self.llm_api_key:
            issues.append("SEABAY_LLM_API_KEY not set — natural language chat will be limited")
        return issues
