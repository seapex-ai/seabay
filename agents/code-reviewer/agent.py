"""Seabay Code Reviewer Agent — AI-powered code review service.

Registers with Seabay API, polls for tasks, reviews code using an LLM,
and returns structured feedback.

Usage:
    export SEABAY_API_URL=http://localhost:8000/v1
    export SEABAY_API_KEY=your_key
    export LLM_API_KEY=your_openai_key
    python agent.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("code-reviewer")

# ── Configuration ──

CONFIG_PATH = Path(__file__).parent / "config.json"
STATE_PATH = Path(__file__).parent / ".agent_state.json"

SEABAY_API_URL = os.environ.get("SEABAY_API_URL", "http://localhost:8000/v1")
SEABAY_API_KEY = os.environ.get("SEABAY_API_KEY", "")
LLM_API_URL = os.environ.get("LLM_API_URL", "https://api.openai.com/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o")


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_state() -> dict:
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


# ── Seabay API client ──

class SeabayAgent:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.Client(
            base_url=self.api_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=30.0,
        )

    def _request(self, method: str, path: str, **kwargs) -> dict:
        resp = self._client.request(method, path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def register(api_url: str, config: dict) -> dict:
        resp = httpx.post(
            f"{api_url}/agents/register",
            json={
                "slug": config["slug"],
                "display_name": config["display_name"],
                "agent_type": config["agent_type"],
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def update_profile(self, config: dict) -> dict:
        return self._request("PATCH", "/agents/me", json={
            "bio": config.get("bio", ""),
            "skills": config.get("skills", []),
            "languages": config.get("languages", []),
            "location_city": config.get("location_city"),
            "location_country": config.get("location_country"),
            "can_offer": config.get("can_offer", []),
            "visibility_scope": config.get("visibility_scope", "public"),
            "contact_policy": config.get("contact_policy", "public_service_only"),
        })

    def get_inbox(self, status: str = "pending_accept", limit: int = 10) -> dict:
        return self._request("GET", "/tasks/inbox", params={"status": status, "limit": str(limit)})

    def accept_task(self, task_id: str) -> dict:
        return self._request("POST", f"/tasks/{task_id}/accept")

    def complete_task(self, task_id: str, notes: str = "", rating: float | None = None) -> dict:
        body: dict = {"notes": notes}
        if rating is not None:
            body["rating"] = rating
        return self._request("POST", f"/tasks/{task_id}/complete", json=body)

    def fail_task(self, task_id: str, reason: str = "") -> dict:
        return self._request("POST", f"/tasks/{task_id}/cancel", json={"reason": reason})

    def health(self) -> dict:
        return self._request("GET", "/health")


# ── LLM Code Review ──

def review_code(code: str, review_type: str = "general") -> str:
    """Review code using the configured LLM."""
    if not LLM_API_KEY:
        return "[Code review unavailable — LLM_API_KEY not set]"

    review_instructions = {
        "general": (
            "Perform a comprehensive code review covering:\n"
            "1. **Bugs & Logic Errors** — identify potential bugs, edge cases, race conditions\n"
            "2. **Security** — check for vulnerabilities (injection, XSS, auth issues, secret leaks)\n"
            "3. **Performance** — identify unnecessary complexity, N+1 queries, memory leaks\n"
            "4. **Style & Readability** — naming, structure, documentation\n"
            "5. **Best Practices** — error handling, testing, type safety\n"
            "6. **Suggestions** — specific improvements with code examples"
        ),
        "security": (
            "Perform a security-focused code review:\n"
            "1. Injection vulnerabilities (SQL, command, template)\n"
            "2. Authentication and authorization issues\n"
            "3. Data validation and sanitization\n"
            "4. Secret/credential exposure\n"
            "5. CORS and CSRF issues\n"
            "6. Dependency vulnerabilities\n"
            "Rate overall security risk: LOW / MEDIUM / HIGH / CRITICAL"
        ),
        "performance": (
            "Perform a performance-focused code review:\n"
            "1. Algorithmic complexity issues\n"
            "2. Memory usage concerns\n"
            "3. Database query optimization\n"
            "4. Caching opportunities\n"
            "5. Concurrency and parallelism\n"
            "6. Resource management (connections, file handles)"
        ),
        "style": (
            "Review code style and readability:\n"
            "1. Naming conventions\n"
            "2. Code structure and organization\n"
            "3. Documentation and comments\n"
            "4. Consistency with common patterns\n"
            "5. Dead code or unnecessary complexity\n"
            "6. Type annotations and contracts"
        ),
    }

    instruction = review_instructions.get(review_type, review_instructions["general"])

    system_prompt = (
        "You are a senior software engineer conducting a code review. "
        "Be thorough, constructive, and specific. "
        "For each issue found, indicate severity (critical/major/minor/suggestion) "
        "and provide a specific fix or improvement. "
        "If the code is good, acknowledge what was done well."
    )

    user_prompt = f"{instruction}\n\nCode to review:\n\n```\n{code}\n```"

    try:
        resp = httpx.post(
            f"{LLM_API_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 4096,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error("LLM code review failed: %s", e)
        raise


def parse_review_task(description: str) -> dict:
    """Extract code review parameters from a task description."""
    params = {
        "code": description,
        "review_type": "general",
    }

    lower = description.lower()
    if "security" in lower or "vulnerability" in lower:
        params["review_type"] = "security"
    elif "performance" in lower or "optimize" in lower:
        params["review_type"] = "performance"
    elif "style" in lower or "lint" in lower or "readability" in lower:
        params["review_type"] = "style"

    return params


# ── Main agent loop ──

def ensure_registered(config: dict) -> tuple[str, str]:
    state = load_state()
    if SEABAY_API_KEY:
        return state.get("agent_id", ""), SEABAY_API_KEY
    if state.get("api_key"):
        return state["agent_id"], state["api_key"]

    logger.info("Registering agent '%s'...", config["slug"])
    try:
        result = SeabayAgent.register(SEABAY_API_URL, config)
        state = {"agent_id": result["id"], "api_key": result["api_key"], "slug": result["slug"]}
        save_state(state)
        logger.info("Registered! Agent ID: %s", result["id"])
        return result["id"], result["api_key"]
    except Exception as e:
        logger.error("Registration failed: %s", e)
        sys.exit(1)


def process_task(agent: SeabayAgent, task: dict) -> None:
    task_id = task["id"]
    description = task.get("description", "")
    logger.info("Processing task %s: %s", task_id, description[:80])

    try:
        agent.accept_task(task_id)
        logger.info("Task %s accepted", task_id)

        params = parse_review_task(description)
        result = review_code(code=params["code"], review_type=params["review_type"])

        agent.complete_task(task_id, notes=result)
        logger.info("Task %s completed", task_id)

    except Exception as e:
        logger.error("Task %s failed: %s", task_id, e)
        try:
            agent.fail_task(task_id, reason=str(e))
        except Exception:
            pass


def run_polling_loop(agent: SeabayAgent, config: dict) -> None:
    poll_interval = config.get("poll_interval_seconds", 5)
    logger.info("Starting polling loop (interval: %ds)...", poll_interval)

    while True:
        try:
            inbox = agent.get_inbox(status="pending_accept")
            tasks = inbox.get("data", [])
            if tasks:
                logger.info("Found %d pending task(s)", len(tasks))
                for task in tasks:
                    process_task(agent, task)
        except httpx.ConnectError:
            logger.warning("Cannot connect to API. Retrying...")
            time.sleep(poll_interval)
        except Exception as e:
            logger.error("Polling error: %s", e)

        time.sleep(poll_interval)


def main():
    config = load_config()
    logger.info("Seabay Code Reviewer Agent starting...")

    agent_id, api_key = ensure_registered(config)
    agent = SeabayAgent(SEABAY_API_URL, api_key)

    try:
        agent.update_profile(config)
        logger.info("Profile updated")
    except Exception as e:
        logger.warning("Profile update failed: %s", e)

    try:
        health = agent.health()
        logger.info("Server: %s v%s", health.get("service", "?"), health.get("version", "?"))
    except Exception:
        logger.warning("Health check failed")

    try:
        run_polling_loop(agent, config)
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
