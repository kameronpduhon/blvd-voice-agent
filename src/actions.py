from src.utils import extract_zip, resolve_template


async def check_fee_approved(executor, session) -> str:
    company = executor.company_tts_name
    if executor.collected.get("fee_approved", "").lower() in ("no", "n", "decline"):
        executor.outcome = "declined"
        return f'Say EXACTLY: "No problem at all. Thank you for calling {company}. Have a great day." [call_ended]'
    return await executor.advance(session)


async def check_service_area(executor, session) -> str:
    company = executor.company_tts_name
    address = executor.collected.get("address", "")
    zip_code = extract_zip(address)

    if zip_code is None:
        # Missing zip — stash original address and rewind to address step
        executor.pending_fragments["address_missing_zip"] = address
        for i, step in enumerate(executor.current_steps):
            if step.get("field") == "address":
                executor.current_step_index = i
                return "The address is missing a zip code. Ask the caller for their zip code so you can verify the service area."
        # No address step found (shouldn't happen) — ask generically
        return "The address is missing a zip code. Ask the caller for their zip code so you can verify the service area."

    if zip_code not in executor.playbook["service_areas"]:
        executor.outcome = "out_of_area"
        return (
            "Say EXACTLY: \"Unfortunately we don't service that area. "
            "I'd recommend searching online for providers near you. "
            f'Thank you for calling {company}." [call_ended]'
        )
    return await executor.advance(session)


async def check_booking_confirmed(executor, session) -> str:
    confirmed = executor.collected.get("booking_confirmed", "").lower()
    if confirmed in ("no", "n", "nope", "not yet", "hold on", "wait"):
        # Find the appointment_time step and go back to it
        for i, step in enumerate(executor.current_steps):
            if step.get("field") == "appointment_time":
                executor.current_step_index = i
                return "The caller wants to change something. Ask what they'd like to change — the appointment time, or something else."
        return "The caller wants to change something. Ask what they'd like to change."
    return await executor.advance(session)


async def confirm_booking(executor, session) -> str:
    closing = resolve_template(
        executor.playbook["scripts"]["closing_booked"], executor.collected
    )
    executor.outcome = "booked"
    return f'Say EXACTLY: "{closing}" [call_ended]'


async def take_message(executor, session) -> str:
    closing = resolve_template(
        executor.playbook["scripts"]["closing_message"], executor.collected
    )
    executor.outcome = "message_taken"
    return f'Say EXACTLY: "{closing}" [call_ended]'


async def dispatch_oncall_tech(executor, session) -> str:
    closing = resolve_template(
        executor.playbook["scripts"]["closing_dispatched"], executor.collected
    )
    executor.outcome = "dispatched"
    return f'Say EXACTLY: "{closing}" [call_ended]'


async def check_emergency_confirmed(executor, session) -> str:
    confirmed = executor.collected.get("emergency_confirmed", "").lower()
    if confirmed in ("no", "n", "nope", "not yet", "hold on", "wait"):
        return await take_message(executor, session)
    return await executor.advance(session)


ACTION_REGISTRY = {
    "check_emergency_confirmed": check_emergency_confirmed,
    "check_fee_approved": check_fee_approved,
    "check_service_area": check_service_area,
    "check_booking_confirmed": check_booking_confirmed,
    "confirm_booking": confirm_booking,
    "take_message": take_message,
    "dispatch_oncall_tech": dispatch_oncall_tech,
}
