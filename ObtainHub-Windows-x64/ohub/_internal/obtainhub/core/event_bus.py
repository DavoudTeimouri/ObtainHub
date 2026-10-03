"""In-memory EventBus implementation for decoupled event handling."""

from collections import defaultdict
from typing import Any, Callable


class EventBus:
    """Simple in-memory event bus for publish/subscribe pattern."""

    def __init__(self):
        self._handlers: dict[str, list[Callable[[dict], None]]] = defaultdict(list)

    def publish(self, event: str, data: dict) -> None:
        """Publish an event to all subscribers."""
        for handler in self._handlers.get(event, []):
            try:
                handler(data)
            except Exception:
                # Swallow handler errors to not break the publisher
                pass

    def subscribe(self, event: str, handler: Callable[[dict], None]) -> None:
        """Subscribe to an event."""
        self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable[[dict], None]) -> None:
        """Unsubscribe from an event."""
        if event in self._handlers:
            try:
                self._handlers[event].remove(handler)
            except ValueError:
                pass

    def clear(self) -> None:
        """Clear all handlers."""
        self._handlers.clear()


# Global event bus instance
_global_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus


def set_event_bus(bus: EventBus) -> None:
    """Set the global event bus instance (for testing)."""
    global _global_bus
    _global_bus = bus