"""Simple CLI to test LLM providers."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from yom.providers import create_provider, Message, CompletionConfig


async def chat(
    prompt: str,
    model: str,
    provider: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    system: str | None = None,
    stream: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 4096,
):
    """Send a chat request to the LLM."""
    p = create_provider(
        model=model,
        provider=provider,
        api_key=api_key,
        base_url=base_url,
    )

    messages = []
    if system:
        messages.append(Message(role="system", content=system))
    messages.append(Message(role="user", content=prompt))

    config = CompletionConfig(
        temperature=temperature,
        max_tokens=max_tokens,
    )

    print(f"[Model: {model}]", file=sys.stderr)

    if stream:
        print("Streaming response:", file=sys.stderr)
        full_content = ""
        async for chunk in p.stream(messages, model, config):
            if chunk.content:
                print(chunk.content, end="", flush=True)
                full_content += chunk.content
        print()  # newline after stream
        return full_content
    else:
        response = await p.complete(messages, model, config)
        print(response.content)
        if response.usage:
            print(f"\n[Input tokens: {response.usage.input_tokens}]", file=sys.stderr)
            print(f"[Output tokens: {response.usage.output_tokens}]", file=sys.stderr)
        return response.content


def main():
    parser = argparse.ArgumentParser(description="Chat with an LLM")
    parser.add_argument("prompt", help="The prompt to send")
    parser.add_argument("--model", "-m", default=os.getenv("YOM_MODEL", "claude-3-5-sonnet-latest"),
                        help="Model to use (default: from YOM_MODEL env or claude-3-5-sonnet-latest)")
    parser.add_argument("--provider", "-p", default=None,
                        help="Provider (auto-detected if not specified)")
    parser.add_argument("--api-key", "-k", default=None,
                        help="API key (from env if not specified)")
    parser.add_argument("--base-url", "-b", default=None,
                        help="Base URL for custom endpoints")
    parser.add_argument("--system", "-s", default=None,
                        help="System prompt")
    parser.add_argument("--stream", action="store_true",
                        help="Stream the response")
    parser.add_argument("--temperature", "-t", type=float, default=0.7,
                        help="Temperature (default: 0.7)")
    parser.add_argument("--max-tokens", type=int, default=4096,
                        help="Max tokens (default: 4096)")

    args = parser.parse_args()

    try:
        asyncio.run(chat(
            prompt=args.prompt,
            model=args.model,
            provider=args.provider,
            api_key=args.api_key,
            base_url=args.base_url,
            system=args.system,
            stream=args.stream,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        ))
    except KeyboardInterrupt:
        print("\n[Interrupted]", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
