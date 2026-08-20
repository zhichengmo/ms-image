"""Signal-aware lifecycle helpers for long-running Runtime processes."""

from __future__ import annotations

import asyncio
import signal


def install_shutdown_handlers(stop_event: asyncio.Event) -> None:
    """Translate process termination signals into an asyncio stop event."""

    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop_event.set)
        except (NotImplementedError, RuntimeError):
            # Signal handlers are unavailable on some event-loop platforms.
            # The process retains the platform's default termination behavior.
            continue


async def wait_for_shutdown(stop_event: asyncio.Event, timeout: float) -> None:
    """Wait for shutdown, returning after the bounded poll interval."""

    try:
        await asyncio.wait_for(stop_event.wait(), timeout=max(0.1, timeout))
    except TimeoutError:
        return


__all__ = ["install_shutdown_handlers", "wait_for_shutdown"]
