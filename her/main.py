"""Her - Entry point."""

import sys

from her.infra.llm import LLMConfig, Provider
from her.ui.app import run_app


def main():
    """Main entry point."""
    # Default configuration - can be customized
    config = LLMConfig(
        provider=Provider.OPENAI,
        model="gpt-4o",
    )
    
    try:
        run_app(llm_config=config)
    except KeyboardInterrupt:
        print("\n再见！")
        sys.exit(0)


if __name__ == "__main__":
    main()
