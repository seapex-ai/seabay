"""Entry point for seabay-shell command."""

from __future__ import annotations

import argparse
import sys

from seabay_shell.config import ShellConfig
from seabay_shell.chat import ChatLoop
from seabay_shell.renderer import TerminalRenderer


def main() -> None:
    """Main entry point for the seabay-shell command."""
    parser = argparse.ArgumentParser(
        prog="seabay-shell",
        description="Seabay Shell — natural language chat interface for the Seabay Agent platform",
    )
    parser.add_argument(
        "--api-url",
        default=None,
        help="Seabay API URL (overrides config/env)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Seabay API key (overrides config/env)",
    )
    parser.add_argument(
        "--llm-url",
        default=None,
        help="LLM API URL (OpenAI-compatible, overrides config/env)",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="LLM model name (overrides config/env)",
    )
    parser.add_argument(
        "--llm-api-key",
        default=None,
        help="LLM API key (overrides config/env)",
    )
    parser.add_argument(
        "--show-tool-calls",
        action="store_true",
        default=False,
        help="Show LLM tool calls in the output",
    )
    parser.add_argument(
        "--no-rich",
        action="store_true",
        default=False,
        help="Disable rich text rendering",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="seabay-shell 0.1.0",
    )

    args = parser.parse_args()

    # Load configuration
    config = ShellConfig.load()

    # Apply CLI overrides
    if args.api_url:
        config.api_url = args.api_url
    if args.api_key:
        config.api_key = args.api_key
    if args.llm_url:
        config.llm_url = args.llm_url
    if args.llm_model:
        config.llm_model = args.llm_model
    if args.llm_api_key:
        config.llm_api_key = args.llm_api_key
    if args.show_tool_calls:
        config.show_tool_calls = True

    # Validate configuration
    issues = config.validate()
    renderer = TerminalRenderer(use_rich=not args.no_rich)

    if not config.is_configured:
        renderer.render_error("Seabay Shell is not configured.")
        renderer.render_text("")
        renderer.render_text("Quick setup:")
        renderer.render_text("  1. Set your Seabay API key:")
        renderer.render_text("     export SEABAY_API_KEY=your_key_here")
        renderer.render_text("")
        renderer.render_text("  2. (Optional) Set LLM for natural language chat:")
        renderer.render_text("     export SEABAY_LLM_API_KEY=your_openai_key")
        renderer.render_text("     export SEABAY_LLM_URL=https://api.openai.com/v1")
        renderer.render_text("     export SEABAY_LLM_MODEL=gpt-4o")
        renderer.render_text("")
        renderer.render_text("  3. Or create ~/.seabay-shell.json:")
        renderer.render_text('     { "api_key": "...", "llm_api_key": "...", "llm_model": "gpt-4o" }')
        renderer.render_text("")
        renderer.render_text("  4. Or use --api-key flag:")
        renderer.render_text("     seabay-shell --api-key YOUR_KEY")
        sys.exit(1)

    for issue in issues:
        renderer.render_info(f"Warning: {issue}")

    # Start chat loop
    chat = ChatLoop(config)
    if not chat.initialize():
        sys.exit(1)

    chat.run()


if __name__ == "__main__":
    main()
