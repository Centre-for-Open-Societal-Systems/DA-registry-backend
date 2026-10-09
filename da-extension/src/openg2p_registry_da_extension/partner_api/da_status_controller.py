import logging
from typing import Optional

from fastapi import HTTPException
from openg2p_fastapi_common.context import async_session_maker
from openg2p_fastapi_common.controller import BaseController

from ..config import Settings
from ..register_domain.services.push_status import lookup_push_status

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class DAPushStatusController(BaseController):
    """GET /partner/da/status: what happened to a DA that DA Services pushed.

    Looked up by the correlation_id the push returned, or by DA Services' own
    reference_id (latest push wins). See register_domain/services/push_status.py
    for the states.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.router.tags += ["/partner"]
        self.router.prefix = "/partner"
        self.router.add_api_route("/da/status", self.get_status, methods=["GET"])

    async def get_status(self, correlation_id: Optional[str] = None, reference_id: Optional[str] = None) -> dict:
        if not correlation_id and not reference_id:
            raise HTTPException(status_code=400, detail="Give correlation_id or reference_id")
        async with async_session_maker.get()() as session:
            status = await lookup_push_status(session, correlation_id=correlation_id, reference_id=reference_id)
        if status is None:
            raise HTTPException(status_code=404, detail="No DA push found for this correlation_id / reference_id")
        return status
