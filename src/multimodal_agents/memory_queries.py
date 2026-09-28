from multimodal_agents.event_store import EventStore


def where_was(
    store: EventStore,
    entity_id: str,
    recorded_by: str,
) -> dict | None:
    event = store.projection(entity_id, recorded_by)
    if event is None:
        return None
    return {
        "answer": event["payload"].get("location"),
        "event_id": event["event_id"],
        "locator": event["locator"],
        "known_by": recorded_by,
    }


def changes(store: EventStore, entity_id: str) -> list[dict]:
    history = store.history(entity_id)
    by_id = {event["event_id"]: event for event in history}
    result = []
    for event in history:
        corrected_id = event["corrects"]
        if corrected_id and corrected_id in by_id:
            previous = by_id[corrected_id]
            result.append(
                {
                    "changed_at": event["recorded_at"],
                    "from": previous["payload"].get("location"),
                    "to": event["payload"].get("location"),
                    "evidence": [previous["event_id"], event["event_id"]],
                }
            )
    return result


def event_order(store: EventStore, entity_id: str) -> list[str]:
    return [event["event_id"] for event in sorted(
        store.history(entity_id),
        key=lambda event: (event["valid_at"], event["sequence"]),
    )]
