#!/usr/bin/env python3
"""
Interactive demonstration of the LLM fallback system.

This script provides a comprehensive demo of the LLM fallback system features
including provider fallback, cost tracking, error handling, and different strategies.
"""

import json
import os
import sys
import time
from typing import Any, Dict, List

# Add the parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import contextlib

from leadfactory.llm import (
    AllProvidersFailedError,
    FallbackStrategy,
    LLMClient,
    LLMConfig,
    LLMError,
    LLMQuotaExceededError,
    LLMRateLimitError,
    ProviderConfig,
)


def print_header(title: str):
    """Print a formatted header."""


def print_section(title: str):
    """Print a formatted section header."""


def demo_basic_usage():
    """Demonstrate basic LLM client usage."""
    print_header("BASIC USAGE DEMO")

    client = LLMClient()

    # Check available providers
    providers = client.get_available_providers()

    if not providers:
        return

    # Get provider status
    print_section("Provider Status")
    status = client.get_provider_status()
    for _provider, info in status.items():
        "✅" if info["enabled"] else "❌"
        "✅" if info["available"] else "❌"

    # Make a simple request
    print_section("Basic Chat Completion")
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France? Answer briefly."},
    ]

    with contextlib.suppress(Exception):
        client.chat_completion(messages=messages, temperature=0.7, max_tokens=50)


def demo_fallback_strategies():
    """Demonstrate different fallback strategies."""
    print_header("FALLBACK STRATEGIES DEMO")

    strategies = [
        (FallbackStrategy.SMART_FALLBACK, "Smart Fallback (Default)"),
        (FallbackStrategy.COST_OPTIMIZED, "Cost Optimized"),
        (FallbackStrategy.QUALITY_OPTIMIZED, "Quality Optimized"),
        (FallbackStrategy.ROUND_ROBIN, "Round Robin"),
        (FallbackStrategy.FAIL_FAST, "Fail Fast"),
    ]

    for strategy, description in strategies:
        print_section(description)

        # Create config with this strategy
        config = LLMConfig.from_environment()
        config.fallback_strategy = strategy

        # Show provider order
        config.get_provider_order()

        # Create client and test
        client = LLMClient(config)

        messages = [{"role": "user", "content": "Say 'Hello' in one word."}]

        with contextlib.suppress(Exception):
            client.chat_completion(messages, max_tokens=10)


def demo_cost_management():
    """Demonstrate cost tracking and management."""
    print_header("COST MANAGEMENT DEMO")

    # Create config with low cost limits for demo
    config = LLMConfig.from_environment()
    config.cost_config.max_cost_per_request = 0.1
    config.cost_config.daily_cost_limit = 0.5

    client = LLMClient(config)

    print_section("Initial Cost Status")
    status = client.get_provider_status()
    for _provider, info in status.items():
        if info["available"]:
            info.get("daily_cost", 0)
            info["cost_per_1k_tokens"]

    print_section("Cost Estimation")
    messages = [{"role": "user", "content": "Explain quantum computing in 100 words."}]
    estimated_tokens = client._estimate_tokens(messages, max_tokens=150)

    for provider_name in client.get_available_providers():
        if provider_name in config.providers:
            config.estimate_request_cost(estimated_tokens, provider_name)

    print_section("Making Requests with Cost Tracking")
    for i in range(3):
        try:
            client.chat_completion(
                messages=[{"role": "user", "content": f"Count to {i + 1}"}],
                max_tokens=20,
            )

        except LLMQuotaExceededError:
            break
        except Exception:
            pass

    print_section("Final Cost Status")
    status = client.get_provider_status()
    for _provider, info in status.items():
        if info["available"]:
            info.get("daily_cost", 0)

    print_section("Resetting Cost Tracking")
    client.reset_cost_tracking()


def demo_error_handling():
    """Demonstrate error handling capabilities."""
    print_header("ERROR HANDLING DEMO")

    # Create a config that will likely fail
    config = LLMConfig()
    config.providers = {
        "fake_provider": ProviderConfig(
            name="fake_provider",
            api_key="invalid_key",  # pragma: allowlist secret
            default_model="non-existent-model",
        )
    }

    client = LLMClient(config)

    print_section("Testing with Invalid Provider")
    messages = [{"role": "user", "content": "Hello"}]

    try:
        client.chat_completion(messages)
    except AllProvidersFailedError as e:
        for _provider, error in e.provider_errors.items():
            pass
    except Exception:
        pass

    print_section("Error Classification Examples")
    from leadfactory.llm.exceptions import classify_error

    error_examples = [
        ("Connection refused", "Network issue"),
        ("Rate limit exceeded", "Rate limiting"),
        ("Invalid API key", "Authentication"),
        ("Model not found", "Model issue"),
        ("Timeout error", "Timeout"),
        ("Unknown error", "Generic error"),
    ]

    for error_msg, _description in error_examples:
        error = Exception(error_msg)
        classify_error(error, "test_provider")


def demo_caching():
    """Demonstrate request caching."""
    print_header("CACHING DEMO")

    config = LLMConfig.from_environment()
    config.enable_caching = True
    client = LLMClient(config)

    messages = [{"role": "user", "content": "What is 2+2?"}]

    print_section("First Request (uncached)")
    start_time = time.time()
    try:
        client.chat_completion(messages, max_tokens=20)
        elapsed1 = time.time() - start_time
    except Exception:
        return

    print_section("Second Request (cached)")
    start_time = time.time()
    try:
        client.chat_completion(messages, max_tokens=20)
        elapsed2 = time.time() - start_time

        if elapsed2 < elapsed1 / 2:
            pass
        else:
            pass

    except Exception:
        pass

    print_section("Cache Statistics")
    len(client._request_cache)

    print_section("Clearing Cache")
    client.clear_cache()


def demo_batch_processing():
    """Demonstrate batch processing with cost monitoring."""
    print_header("BATCH PROCESSING DEMO")

    client = LLMClient()

    # Create a batch of tasks
    tasks = [
        "What is the capital of Spain?",
        "What is 5 x 7?",
        "Name a primary color.",
        "What comes after Wednesday?",
        "What is the largest ocean?",
    ]

    print_section(f"Processing {len(tasks)} Tasks")

    results = []
    total_cost = 0

    for _i, task in enumerate(tasks, 1):

        try:
            response = client.chat_completion(
                messages=[{"role": "user", "content": task}], max_tokens=30
            )

            content = response["choices"][0]["message"]["content"].strip()
            provider = response["provider"]
            tokens = response["usage"]["total_tokens"]

            # Estimate cost (rough approximation)
            if provider in client.config.providers:
                cost = client.config.estimate_request_cost(tokens, provider)
                total_cost += cost
            else:
                pass

            results.append(
                {
                    "task": task,
                    "response": content,
                    "provider": provider,
                    "success": True,
                }
            )

        except Exception as e:
            results.append({"task": task, "error": str(e), "success": False})

    print_section("Batch Results Summary")
    successful = sum(1 for r in results if r["success"])
    len(results) - successful

    # Show provider usage
    providers_used = {}
    for result in results:
        if result["success"]:
            provider = result["provider"]
            providers_used[provider] = providers_used.get(provider, 0) + 1

    if providers_used:
        for provider, _count in providers_used.items():
            pass


def demo_configuration():
    """Demonstrate configuration options."""
    print_header("CONFIGURATION DEMO")

    print_section("Environment Configuration")
    config = LLMConfig.from_environment()

    print_section("Provider Configuration")
    for _name, _provider in config.providers.items():
        pass

    print_section("Cost Configuration")

    print_section("Configuration Validation")
    issues = config.validate()
    if issues:
        for _issue in issues:
            pass
    else:
        pass


def interactive_mode():
    """Interactive mode for testing custom requests."""
    print_header("INTERACTIVE MODE")

    client = LLMClient()

    while True:
        try:
            user_input = input("\n> ").strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                break
            elif user_input.lower() == "help":
                continue
            elif user_input.lower() == "status":
                status = client.get_provider_status()
                for _provider, info in status.items():
                    "✅" if info["available"] else "❌"
                continue
            elif user_input.lower() == "costs":
                status = client.get_provider_status()
                for _provider, info in status.items():
                    if info["available"]:
                        info.get("daily_cost", 0)
                continue
            elif user_input.lower() == "reset":
                client.reset_cost_tracking()
                continue
            elif user_input.lower() == "cache":
                len(client._request_cache)
                continue
            elif user_input.lower() == "clear":
                client.clear_cache()
                continue
            elif not user_input:
                continue

            # Make LLM request
            messages = [{"role": "user", "content": user_input}]

            start_time = time.time()
            response = client.chat_completion(messages, max_tokens=200)
            time.time() - start_time

            response["choices"][0]["message"]["content"]
            response["provider"]
            response["usage"]

        except KeyboardInterrupt:
            break
        except Exception:
            pass


def main():
    """Main demo function."""

    demos = [
        ("1", "Basic Usage", demo_basic_usage),
        ("2", "Fallback Strategies", demo_fallback_strategies),
        ("3", "Cost Management", demo_cost_management),
        ("4", "Error Handling", demo_error_handling),
        ("5", "Caching", demo_caching),
        ("6", "Batch Processing", demo_batch_processing),
        ("7", "Configuration", demo_configuration),
        ("8", "Interactive Mode", interactive_mode),
        ("a", "Run All Demos", None),
        ("q", "Quit", None),
    ]

    while True:
        for key, _title, _ in demos:
            pass

        choice = input("\nEnter choice: ").strip().lower()

        if choice == "q":
            break
        elif choice == "a":
            # Run all demos except interactive
            for key, _title, func in demos[:-3]:  # Exclude 'all', 'interactive', 'quit'
                if func:
                    func()
                    input("\nPress Enter to continue...")
        else:
            # Find and run specific demo
            for key, _title, func in demos:
                if choice == key and func:
                    func()
                    if choice != "8":  # Don't pause after interactive mode
                        input("\nPress Enter to continue...")
                    break
            else:
                pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception:
        import traceback

        traceback.print_exc()
