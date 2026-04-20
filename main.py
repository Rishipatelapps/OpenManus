import argparse
import asyncio

from app.agent.manus import Manus
from app.logger import logger
from app.tool.voice_tool import format_voices_list, _load_voices


def _handle_slash_command(command: str) -> bool:
    """Handle built-in slash commands. Returns True if command was handled."""
    cmd = command.strip().lower()
    if cmd == "/voices":
        print(format_voices_list(_load_voices()))
        return True
    return False


async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run Manus agent with a prompt")
    parser.add_argument(
        "--prompt", type=str, required=False, help="Input prompt for the agent"
    )
    args = parser.parse_args()

    # Create and initialize Manus agent
    agent = await Manus.create()
    try:
        # Use command line prompt if provided, otherwise ask for input
        prompt = args.prompt if args.prompt else input("Enter your prompt: ")
        if not prompt.strip():
            logger.warning("Empty prompt provided.")
            return

        if _handle_slash_command(prompt):
            return

        logger.warning("Processing your request...")
        await agent.run(prompt)
        logger.info("Request processing completed.")
    except KeyboardInterrupt:
        logger.warning("Operation interrupted.")
    finally:
        # Ensure agent resources are cleaned up before exiting
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
