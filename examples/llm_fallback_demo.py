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
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n--- {title} ---")


def demo_basic_usage():
    """Demonstrate basic LLM client usage."""
    print_header("BASIC USAGE DEMO")

    print("Initializing LLM client...")
    client = LLMClient()

    # Check available providers
    providers = client.get_available_providers()
    print(f"Available providers: {providers}")

    if not providers:
        print("⚠️  No providers available. Check your API keys and Ollama setup.")
        return

    # Get provider status
    print_section("Provider Status")
    status = client.get_provider_status()
    for provider, info in status.items():
        enabled = "✅" if info["enabled"] else "❌"
        available = "✅" if info["available"] else "❌"
        print(
            f"{provider}: Enabled={enabled}, Available={available}, Model={info['model']}"
        )

    # Make a simple request
    print_section("Basic Chat Completion")
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France? Answer briefly."},
    ]

    try:
        response = client.chat_completion(
            messages=messages, temperature=0.7, max_tokens=50
        )

        print(f"✅ Success using {response['provider']}")
        print(f"Response: {response['choices'][0]['message']['content']}")
        print(f"Usage: {response['usage']}")

    except Exception as e:
        print(f"❌ Error: {e}")


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
        order = config.get_provider_order()
        print(f"Provider order: {' → '.join(order)}")

        # Create client and test
        client = LLMClient(config)

        messages = [{"role": "user", "content": "Say 'Hello' in one word."}]

        try:
            response = client.chat_completion(messages, max_tokens=10)
            print(
                f"✅ Used {response['provider']}: {response['choices'][0]['message']['content'].strip()}"
            )
        except Exception as e:
            print(f"❌ Failed: {e}")


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
    for provider, info in status.items():
        if info["available"]:
            daily_cost = info.get("daily_cost", 0)
            cost_per_1k = info["cost_per_1k_tokens"]
            print(f"{provider}: ${daily_cost:.4f} today, ${cost_per_1k:.4f}/1k tokens")

    print_section("Cost Estimation")
    messages = [{"role": "user", "content": "Explain quantum computing in 100 words."}]
    estimated_tokens = client._estimate_tokens(messages, max_tokens=150)

    for provider_name in client.get_available_providers():
        if provider_name in config.providers:
            cost = config.estimate_request_cost(estimated_tokens, provider_name)
            print(f"{provider_name}: ~{estimated_tokens} tokens ≈ ${cost:.4f}")

    print_section("Making Requests with Cost Tracking")
    for i in range(3):
        try:
            response = client.chat_completion(
                messages=[{"role": "user", "content": f"Count to {i+1}"}], max_tokens=20
            )
            print(
                f"Request {i+1}: ✅ {response['provider']} - {response['usage']['total_tokens']} tokens"
            )

        except LLMQuotaExceededError as e:
            print(f"Request {i+1}: ❌ Budget exceeded: {e}")
            break
        except Exception as e:
            print(f"Request {i+1}: ❌ Error: {e}")

    print_section("Final Cost Status")
    status = client.get_provider_status()
    for provider, info in status.items():
        if info["available"]:
            daily_cost = info.get("daily_cost", 0)
            print(f"{provider}: ${daily_cost:.4f} spent today")

    print_section("Resetting Cost Tracking")
    client.reset_cost_tracking()
    print("✅ Cost tracking reset for all providers")


def demo_error_handling():
    """Demonstrate error handling capabilities."""
    print_header("ERROR HANDLING DEMO")

    # Create a config that will likely fail
    config = LLMConfig()
    config.providers = {
        "fake_provider": ProviderConfig(
            name="fake_provider",
            api_key="invalid_key",
            default_model="non-existent-model",
        )
    }

    client = LLMClient(config)

    print_section("Testing with Invalid Provider")
    messages = [{"role": "user", "content": "Hello"}]

    try:
        response = client.chat_completion(messages)
        print("✅ Unexpected success")
    except AllProvidersFailedError as e:
        print("❌ All providers failed (expected)")
        for provider, error in e.provider_errors.items():
            print(f"  {provider}: {type(error).__name__} - {error}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

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

    for error_msg, description in error_examples:
        error = Exception(error_msg)
        classified = classify_error(error, "test_provider")
        print(f"{description}: {type(classified).__name__}")


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
        response1 = client.chat_completion(messages, max_tokens=20)
        elapsed1 = time.time() - start_time
        print(f"✅ Response: {response1['choices'][0]['message']['content'].strip()}")
        print(f"⏱️  Time: {elapsed1:.3f}s")
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    print_section("Second Request (cached)")
    start_time = time.time()
    try:
        response2 = client.chat_completion(messages, max_tokens=20)
        elapsed2 = time.time() - start_time
        print(f"✅ Response: {response2['choices'][0]['message']['content'].strip()}")
        print(f"⏱️  Time: {elapsed2:.3f}s")

        if elapsed2 < elapsed1 / 2:
            print("🚀 Cached response was significantly faster!")
        else:
            print("ℹ️  Response time similar (may not be cached)")

    except Exception as e:
        print(f"❌ Error: {e}")

    print_section("Cache Statistics")
    cache_size = len(client._request_cache)
    print(f"Cache entries: {cache_size}")

    print_section("Clearing Cache")
    client.clear_cache()
    print("✅ Cache cleared")


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

    for i, task in enumerate(tasks, 1):
        print(f"\nTask {i}: {task}")

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
                print(f"✅ {provider}: {content} (${cost:.4f})")
            else:
                print(f"✅ {provider}: {content}")

            results.append(
                {
                    "task": task,
                    "response": content,
                    "provider": provider,
                    "success": True,
                }
            )

        except Exception as e:
            print(f"❌ Error: {e}")
            results.append({"task": task, "error": str(e), "success": False})

    print_section("Batch Results Summary")
    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful

    print(f"✅ Successful: {successful}/{len(results)}")
    print(f"❌ Failed: {failed}/{len(results)}")
    print(f"💰 Total estimated cost: ${total_cost:.4f}")

    # Show provider usage
    providers_used = {}
    for result in results:
        if result["success"]:
            provider = result["provider"]
            providers_used[provider] = providers_used.get(provider, 0) + 1

    if providers_used:
        print("\nProvider usage:")
        for provider, count in providers_used.items():
            print(f"  {provider}: {count} requests")


def demo_configuration():
    """Demonstrate configuration options."""
    print_header("CONFIGURATION DEMO")

    print_section("Environment Configuration")
    config = LLMConfig.from_environment()

    print(f"Fallback strategy: {config.fallback_strategy.value}")
    print(f"Max fallback attempts: {config.max_fallback_attempts}")
    print(f"Default temperature: {config.default_temperature}")
    print(f"Default max tokens: {config.default_max_tokens}")
    print(f"Caching enabled: {config.enable_caching}")
    print(f"Request logging: {config.log_requests}")

    print_section("Provider Configuration")
    for name, provider in config.providers.items():
        print(f"\n{name}:")
        print(f"  Enabled: {provider.enabled}")
        print(f"  Model: {provider.default_model}")
        print(f"  Priority: {provider.priority}")
        print(f"  Cost/1k tokens: ${provider.cost_per_1k_tokens:.4f}")
        print(f"  Timeout: {provider.timeout}s")

    print_section("Cost Configuration")
    cost_config = config.cost_config
    print(f"Max cost per request: ${cost_config.max_cost_per_request}")
    print(f"Daily cost limit: ${cost_config.daily_cost_limit}")
    print(f"Monthly cost limit: ${cost_config.monthly_cost_limit}")
    print(f"Cost tracking enabled: {cost_config.cost_tracking_enabled}")
    print(f"Budget alert threshold: {cost_config.budget_alert_threshold}")

    print_section("Configuration Validation")
    issues = config.validate()
    if issues:
        print("⚠️  Configuration issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✅ Configuration is valid")


def interactive_mode():
    """Interactive mode for testing custom requests."""
    print_header("INTERACTIVE MODE")

    client = LLMClient()

    print("Enter 'quit' to exit, 'help' for commands")
    print("Available commands:")
    print("  status - Show provider status")
    print("  costs - Show cost tracking")
    print("  reset - Reset cost tracking")
    print("  cache - Show cache info")
    print("  clear - Clear cache")

    while True:
        try:
            user_input = input("\n> ").strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                break
            elif user_input.lower() == "help":
                print("Commands: status, costs, reset, cache, clear, quit")
                continue
            elif user_input.lower() == "status":
                status = client.get_provider_status()
                for provider, info in status.items():
                    available = "✅" if info["available"] else "❌"
                    print(f"{provider}: {available} {info['model']}")
                continue
            elif user_input.lower() == "costs":
                status = client.get_provider_status()
                for provider, info in status.items():
                    if info["available"]:
                        cost = info.get("daily_cost", 0)
                        print(f"{provider}: ${cost:.4f} today")
                continue
            elif user_input.lower() == "reset":
                client.reset_cost_tracking()
                print("✅ Cost tracking reset")
                continue
            elif user_input.lower() == "cache":
                size = len(client._request_cache)
                print(f"Cache entries: {size}")
                continue
            elif user_input.lower() == "clear":
                client.clear_cache()
                print("✅ Cache cleared")
                continue
            elif not user_input:
                continue

            # Make LLM request
            messages = [{"role": "user", "content": user_input}]

            start_time = time.time()
            response = client.chat_completion(messages, max_tokens=200)
            elapsed = time.time() - start_time

            content = response["choices"][0]["message"]["content"]
            provider = response["provider"]
            usage = response["usage"]

            print(f"\n[{provider}] {content}")
            print(f"\n⏱️  {elapsed:.2f}s | 🔢 {usage['total_tokens']} tokens")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


def main():
    """Main demo function."""
    print("🤖 LLM Fallback System Demo")
    print("=" * 60)

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
        print("\nSelect a demo:")
        for key, title, _ in demos:
            print(f"  {key}. {title}")

        choice = input("\nEnter choice: ").strip().lower()

        if choice == "q":
            print("Goodbye!")
            break
        elif choice == "a":
            # Run all demos except interactive
            for key, title, func in demos[:-3]:  # Exclude 'all', 'interactive', 'quit'
                if func:
                    func()
                    input("\nPress Enter to continue...")
        else:
            # Find and run specific demo
            for key, title, func in demos:
                if choice == key and func:
                    func()
                    if choice != "8":  # Don't pause after interactive mode
                        input("\nPress Enter to continue...")
                    break
            else:
                print("Invalid choice. Please try again.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted. Goodbye!")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback

        traceback.print_exc()
