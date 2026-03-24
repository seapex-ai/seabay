"""Seabay Research Assistant Agent — AI research and information synthesis service.

Registers with Seabay API, polls for tasks, performs research using an LLM,
and returns structured reports.

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
logger = logging.getLogger("research-assistant")

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


# ── LLM Research ──

RESEARCH_TYPES = {
    "general": (
        "Conduct thorough research on the given topic. Structure your report with:\n"
        "1. **Overview** — brief context and scope\n"
        "2. **Key Findings** — main discoveries and insights (3-5 points)\n"
        "3. **Analysis** — deeper examination of important aspects\n"
        "4. **Considerations** — limitations, caveats, alternative perspectives\n"
        "5. **Conclusion** — summary and recommended next steps"
    ),
    "market": (
        "Conduct market research on the given topic:\n"
        "1. **Market Overview** — size, growth, key trends\n"
        "2. **Key Players** — major companies, market shares, positioning\n"
        "3. **Opportunities** — underserved segments, emerging trends\n"
        "4. **Challenges** — barriers, risks, regulatory concerns\n"
        "5. **Recommendations** — strategic suggestions"
    ),
    "competitor": (
        "Conduct competitive analysis:\n"
        "1. **Competitor Landscape** — who are the main competitors\n"
        "2. **Strengths & Weaknesses** — for each key competitor\n"
        "3. **Feature Comparison** — key differentiators\n"
        "4. **Market Positioning** — how each positions themselves\n"
        "5. **Strategic Implications** — what this means for you"
    ),
    "literature": (
        "Conduct a literature review:\n"
        "1. **Topic Overview** — define the research question/area\n"
        "2. **Key Works** — summarize the most influential works\n"
        "3. **Themes & Trends** — identify common themes across literature\n"
        "4. **Gaps** — what has not been adequately addressed\n"
        "5. **Synthesis** — integrated summary of current state of knowledge"
    ),
    "fact_check": (
        "Fact-check the following claims:\n"
        "For each claim, assess:\n"
        "1. **Claim** — restate the claim clearly\n"
        "2. **Verdict** — TRUE / MOSTLY TRUE / MIXED / MOSTLY FALSE / FALSE / UNVERIFIABLE\n"
        "3. **Evidence** — what supports or contradicts the claim\n"
        "4. **Context** — important nuances or missing context\n"
        "Be rigorous and evidence-based."
    ),
}


def conduct_research(topic: str, research_type: str = "general") -> str:
    """Conduct research using the configured LLM."""
    if not LLM_API_KEY:
        return "[Research unavailable — LLM_API_KEY not set]"

    instruction = RESEARCH_TYPES.get(research_type, RESEARCH_TYPES["general"])

    system_prompt = (
        "You are an expert research analyst. Provide thorough, well-structured research. "
        "Be factual and evidence-based. Clearly distinguish between established facts, "
        "well-supported conclusions, and speculative analysis. "
        "Cite specific examples and data points when possible. "
        "Note the limitations of your knowledge and where further investigation is needed."
    )

    user_prompt = f"{instruction}\n\nResearch topic/request:\n\n{topic}"

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
                "temperature": 0.4,
                "max_tokens": 4096,
            },
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error("LLM research failed: %s", e)
        raise


def parse_research_task(description: str) -> dict:
    """Extract research parameters from a task description."""
    params = {
        "topic": description,
        "research_type": "general",
    }

    lower = description.lower()
    if "market" in lower and ("research" in lower or "analysis" in lower):
        params["research_type"] = "market"
    elif "competitor" in lower or "competitive" in lower:
        params["research_type"] = "competitor"
    elif "literature" in lower or "review" in lower and "paper" in lower:
        params["research_type"] = "literature"
    elif "fact" in lower and "check" in lower:
        params["research_type"] = "fact_check"

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

        params = parse_research_task(description)
        result = conduct_research(topic=params["topic"], research_type=params["research_type"])

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
    logger.info("Seabay Research Assistant Agent starting...")

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
