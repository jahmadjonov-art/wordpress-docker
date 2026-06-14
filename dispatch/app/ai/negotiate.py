"""Draft a broker negotiation letter with Claude.

Dormant until ANTHROPIC_API_KEY is set. When configured, it feeds the load
facts, the lane benchmark, our cost, and the suggested target rate to the model
and asks for a short, professional rate-negotiation email the driver can send.
"""
from .. import config, models


class NotConfigured(Exception):
    """Raised when no Anthropic API key is available."""


def configured() -> bool:
    return bool(config.ANTHROPIC_API_KEY)


def _money(cents) -> str:
    if cents is None:
        return "unknown"
    return f"${cents / 100:,.2f}"


def _build_prompt(load: models.Load, score: models.LoadScore | None) -> str:
    lane = f"{load.origin_city}, {load.origin_state} -> {load.dest_city}, {load.dest_state}"
    lines = [
        f"Lane: {lane}",
        f"Equipment: {load.equipment}",
        f"Loaded miles: {round(load.loaded_miles) if load.loaded_miles else 'unknown'}",
        f"Deadhead miles: {round(load.deadhead_miles or 0)}",
        f"Broker's offered rate: {_money(load.rate_total_cents)}",
    ]
    if load.rate_per_mile_cents:
        lines.append(f"Offered rate per mile: ${load.rate_per_mile_cents / 100:.2f}")
    if load.commodity:
        lines.append(f"Commodity: {load.commodity}")
    if load.weight_lbs:
        lines.append(f"Weight: {load.weight_lbs} lbs")
    if score:
        if score.median_rpm_cents:
            lines.append(f"Market median for this lane: ${score.median_rpm_cents / 100:.2f}/mi "
                         f"(from {score.lane_comp_count} comparable loads)")
        lines.append(f"Our estimated all-in cost to run it: {_money(score.est_cost_cents)}")
        lines.append(f"Our target rate (covers cost + margin): {_money(score.suggested_target_rate_cents)}")
        lines.append(f"Our 0-100 load score: {score.score}")
    if load.broker_name:
        lines.append(f"Broker: {load.broker_name}")
    if load.notes:
        lines.append(f"Notes: {load.notes}")
    facts = "\n".join(lines)

    return (
        "You are an experienced freight dispatcher negotiating a truckload rate "
        "on behalf of an owner-operator. Write a short, professional, confident "
        "email to the broker negotiating a higher rate. Reference concrete "
        "justification (lane market average, miles, deadhead, operating cost) "
        "where it helps, but stay friendly and concise (under 180 words). Ask "
        "for the target rate, and signal willingness to book quickly if they can "
        "meet it. Do not invent facts not given. Output only the email body.\n\n"
        f"Load details:\n{facts}"
    )


def generate_letter(load: models.Load, score: models.LoadScore | None) -> str:
    if not configured():
        raise NotConfigured("ANTHROPIC_API_KEY is not set")

    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": _build_prompt(load, score)}],
    )
    parts = [b.text for b in message.content if getattr(b, "type", None) == "text"]
    return "\n".join(parts).strip()
