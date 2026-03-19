from src.utils import extract_zip, resolve_template


async def check_fee_approved(executor, session) -> str:
    company = executor.playbook.get("meta", {}).get("company_name", "us")
    if executor.collected.get("fee_approved", "").lower() in ("no", "n", "decline"):
        executor.outcome = "declined"
        await session.say(
            f"No problem at all. Thank you for calling {company}. Have a great day."
        )
        return "[call_ended]"
    return await executor.advance(session)


async def check_service_area(executor, session) -> str:
    company = executor.playbook.get("meta", {}).get("company_name", "us")
    address = executor.collected.get("address", "")
    zip_code = extract_zip(address)
    if zip_code is None or zip_code not in executor.playbook["service_areas"]:
        executor.outcome = "out_of_area"
        await session.say(
            "Unfortunately we don't service that area. "
            "I'd recommend searching online for providers near you. "
            f"Thank you for calling {company}."
        )
        return "[call_ended]"
    return await executor.advance(session)


async def confirm_booking(executor, session) -> str:
    closing = resolve_template(
        executor.playbook["scripts"]["closing_booked"], executor.collected
    )
    executor.outcome = "booked"
    await session.say(closing)
    return "[call_ended]"


async def take_message(executor, session) -> str:
    closing = resolve_template(
        executor.playbook["scripts"]["closing_message"], executor.collected
    )
    executor.outcome = "message_taken"
    await session.say(closing)
    return "[call_ended]"


ACTION_REGISTRY = {
    "check_fee_approved": check_fee_approved,
    "check_service_area": check_service_area,
    "confirm_booking": confirm_booking,
    "take_message": take_message,
}
