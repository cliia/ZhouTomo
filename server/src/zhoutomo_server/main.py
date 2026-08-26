"""Console entry point for the ZhouTomo server."""

import asyncio

from run_agent import main as _legacy_main


def main() -> None:
    asyncio.run(_legacy_main())
