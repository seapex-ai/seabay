"""Interactive chat loop for Seabay Shell."""

from __future__ import annotations

from typing import Optional

from seabay_shell.commands import SeabayAPI, execute_tool, handle_command
from seabay_shell.config import ShellConfig
from seabay_shell.history import ChatHistory
from seabay_shell.llm import LLMClient
from seabay_shell.renderer import TerminalRenderer

# Maximum number of consecutive tool-call rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 5


class ChatLoop:
    """Main interactive chat loop that bridges user input, LLM, and Seabay API."""

    def __init__(self, config: ShellConfig):
        self.config = config
        self.api = SeabayAPI(config)
        self.renderer = TerminalRenderer(use_rich=True)
        self.history = ChatHistory(max_messages=config.max_history)
        self.llm: Optional[LLMClient] = None
        self._agent_info: Optional[dict] = None

        if config.has_llm:
            self.llm = LLMClient(config)

    def initialize(self) -> bool:
        """Connect to Seabay API and initialize the session.

        Returns True if successful, False otherwise.
        """
        # Fetch agent info
        try:
            self._agent_info = self.api.get_my_agent()
            self.config.agent_id = self._agent_info.get("id")
            self.config.agent_slug = self._agent_info.get("slug")
            self.config.agent_name = self._agent_info.get("display_name")
        except Exception as e:
            self.renderer.render_error(f"Failed to connect to Seabay API: {e}")
            self.renderer.render_info("Continuing without agent identity. Some features may not work.")
            self._agent_info = None

        # Initialize chat with system prompt
        system_prompt = LLMClient.get_system_prompt(self._agent_info)
        self.history.add("system", system_prompt)

        return True

    def run(self) -> None:
        """Run the interactive chat loop."""
        self._print_welcome()

        try:
            self._input_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()

    def _input_loop(self) -> None:
        """Main input loop using prompt_toolkit or basic input."""
        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.history import InMemoryHistory

            session = PromptSession(history=InMemoryHistory())
            def get_input():
                return session.prompt("you> ")
        except ImportError:
            def get_input():
                return input("you> ")

        while True:
            try:
                user_input = get_input().strip()
            except EOFError:
                break
            except KeyboardInterrupt:
                self.renderer.render_info("\nUse /quit to exit.")
                continue

            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                result = handle_command(user_input, self.api, self.renderer, self.config)
                if result == "quit":
                    break
                elif result == "clear":
                    # Reset history but keep system prompt
                    self.history.clear()
                continue

            # Natural language processing
            self._process_message(user_input)

    def _process_message(self, user_input: str) -> None:
        """Process a natural language message through the LLM."""
        self.history.add("user", user_input)

        if not self.llm:
            # No LLM configured — try to handle as a simple keyword dispatch
            self._fallback_dispatch(user_input)
            return

        try:
            # Send to LLM with tool definitions
            messages = self.history.get_llm_messages()
            choice = self.llm.get_response(messages)

            # Process tool calls if present (may loop multiple rounds)
            rounds = 0
            while LLMClient.has_tool_calls(choice) and rounds < MAX_TOOL_ROUNDS:
                rounds += 1
                tool_calls = LLMClient.extract_tool_calls(choice)

                # Record assistant message with tool calls
                raw_message = choice.get("message", {})
                self.history.add_assistant_with_tools(
                    content=raw_message.get("content", ""),
                    tool_calls=raw_message.get("tool_calls", []),
                )

                # Execute each tool call
                for tc in tool_calls:
                    if self.config.show_tool_calls:
                        self.renderer.render_tool_call(tc["name"], tc["arguments"])

                    result = execute_tool(self.api, tc["name"], tc["arguments"])
                    self.history.add_tool_call(
                        tool_call_id=tc["id"],
                        name=tc["name"],
                        content=result,
                    )

                # Get LLM's follow-up response
                messages = self.history.get_llm_messages()
                choice = self.llm.get_response(messages)

            # Final text response
            content = LLMClient.get_content(choice)
            if content:
                self.history.add("assistant", content)
                self.renderer.render_text(content)

        except Exception as e:
            self.renderer.render_error(f"LLM error: {e}")
            self.renderer.render_info("Try using slash commands directly (e.g. /search, /inbox)")

    def _fallback_dispatch(self, user_input: str) -> None:
        """Simple keyword-based dispatch when no LLM is configured."""
        lower = user_input.lower()

        if any(w in lower for w in ["search", "find", "look for", "discover"]):
            # Extract search terms (remove common words)
            terms = user_input
            for word in ["search", "find", "look for", "discover", "agent", "agents",
                         "for", "me", "a", "an", "the", "please", "can", "you"]:
                terms = terms.replace(word, "")
            terms = terms.strip()
            if terms:
                try:
                    result = self.api.search_agents(q=terms)
                    agents = result.get("data", [])
                    self.renderer.render_match_results(agents, f"Search results for '{terms}':")
                except Exception as e:
                    self.renderer.render_error(f"Search failed: {e}")
            else:
                self.renderer.render_info("What would you like to search for? Try: /search <query>")
            return

        if any(w in lower for w in ["inbox", "tasks", "pending", "my tasks"]):
            try:
                result = self.api.get_inbox()
                tasks = result.get("data", [])
                self.renderer.render_inbox(tasks, result.get("has_more", False))
            except Exception as e:
                self.renderer.render_error(f"Failed to get inbox: {e}")
            return

        if any(w in lower for w in ["status", "who am i", "my agent"]):
            try:
                agent = self.api.get_my_agent()
                self.renderer.render_agent(agent)
            except Exception as e:
                self.renderer.render_error(f"Failed to get status: {e}")
            return

        # Default: suggest configuring LLM
        self.renderer.render_info(
            "Natural language mode requires an LLM. "
            "Set SEABAY_LLM_API_KEY and SEABAY_LLM_URL, "
            "or use slash commands (/help for list)."
        )
        self.history.add("assistant", "Please configure an LLM or use slash commands.")

    def _print_welcome(self) -> None:
        """Print welcome banner."""
        self.renderer.render_text("---")
        self.renderer.render_text("**Seabay Shell** — Natural language interface for the Seabay Agent platform")
        self.renderer.render_text("")

        if self._agent_info:
            name = self._agent_info.get("display_name", "Unknown")
            slug = self._agent_info.get("slug", "?")
            self.renderer.render_info(f"Connected as: {name} (@{slug})")
        else:
            self.renderer.render_info("Not connected to an agent identity.")

        if not self.llm:
            self.renderer.render_info("LLM not configured — using slash commands only. Set SEABAY_LLM_API_KEY to enable natural chat.")

        self.renderer.render_text("")
        self.renderer.render_info("Type naturally or use /help for commands. /quit to exit.")
        self.renderer.render_text("---")

    def _cleanup(self) -> None:
        """Clean up resources."""
        self.renderer.render_info("\nGoodbye!")
        try:
            self.history.save()
        except Exception:
            pass
        self.api.close()
        if self.llm:
            self.llm.close()
