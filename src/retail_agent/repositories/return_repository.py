from __future__ import annotations

from ..core.db import UnitOfWork


class ReturnRepository:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def returned_quantities(self, order_id: str) -> dict[str, int]:
        """Quantity already returned per SKU (AD-9, the only implementation).

        Until US-102 creates ``returns``/``return_lines`` there is nothing to
        sum, so this returns ``{}``. It still requires an open transaction so
        callers already follow the US-102 contract.
        """
        _ = self._uow.connection
        return {}
