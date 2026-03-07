"""SDK surface: Structured logger for module authors.

Returns a structlog BoundLogger pre-tagged with the module name so all
module log output is easily filterable.

Usage in a module's backend code:

    from makestack_sdk.logger import get_logger

    log = get_logger("inventory-stock")

    log.info("stock_updated", item_id="abc", quantity=5)
    log.warning("low_stock", item_id="abc", quantity=1)
    log.error("sync_failed", error=str(exc))
"""

import structlog


def get_logger(module_name: str | None = None) -> structlog.BoundLogger:
    """Return a structlog BoundLogger pre-tagged with the module name.

    module_name: the module's registered name (e.g., "inventory-stock").
      If None, returns an untagged logger.
    """
    if module_name:
        return structlog.get_logger().bind(module=module_name, component=f"module:{module_name}")
    return structlog.get_logger()


__all__ = ["get_logger"]
