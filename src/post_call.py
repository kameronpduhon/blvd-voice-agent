import asyncio
import logging
import os
import time

import aiohttp

logger = logging.getLogger("agent")

async def post_summary_from_userdata(
    userdata: dict, call_start_time: float, hangup_time: float | None = None
) -> None:
    """Post call summary to Laravel API with retry logic. Reads from session.userdata."""
    backend_url = os.environ.get("BACKEND_URL", "http://localhost:8000")
    end_time = hangup_time or time.time()
    duration = int(end_time - call_start_time) if call_start_time else 0

    payload = {
        "caller_number": userdata.get("sip_caller_number", "")
            or userdata.get("collected", {}).get("phone", ""),
        "callback_number": userdata.get("collected", {}).get("phone", ""),
        "dnis": userdata.get("sip_dnis", ""),
        "intent": userdata.get("intent"),
        "requested_intent": userdata.get("requested_intent") or userdata.get("intent"),
        "outcome": userdata.get("outcome"),
        "collected": userdata.get("collected", {}),
        "transcript": userdata.get("transcript", ""),
        "duration_seconds": duration,
        "time_window": userdata.get("time_window"),
    }

    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as http:
                resp = await http.post(
                    f"{backend_url}/api/call/summary",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                )
                resp.raise_for_status()
                logger.info("Call summary posted successfully")
                return
        except Exception as e:
            if attempt < 2:
                delay = 2**attempt  # 1s, 2s
                logger.warning(
                    f"post_summary attempt {attempt + 1} failed: {e}, retrying in {delay}s"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"Failed to post call summary after 3 attempts: {e}")
