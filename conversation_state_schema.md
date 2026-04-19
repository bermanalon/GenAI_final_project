# Conversation State & Agent Output Schema

## Overview
This document defines the structure of:
- `conversation_state`
- `state_update`
- Agent outputs

It is used for orchestrating the multi-agent recruiting chatbot.

---

## Conversation State Schema

```python
conversation_state = {
    "status": "new",                  # new | active | scheduling | scheduled | ended
    "last_action": "none",            # none | continue | answer_info | offer_slots | ask_slot_clarification | confirm_booking | end
    "turn_count": 0,
    "session_id": None,

    "main_state": {
        "final_decision": None,       # CONTINUE | SCHEDULE | END | None
        "last_routing_reason": None,
    },

    "exit_state": {
        "end_signal_count": 0,
        "strong_opt_out_detected": False,
        "last_exit_decision": "CONTINUE",   # CONTINUE | END
        "last_exit_reason": None,
    },

    "schedule_state": {
        "active": False,
        "last_schedule_decision": "NONE",   # NONE | SCHEDULE
        "last_sub_intent": "none",          # propose_slots | validate_slot | book_slot | clarify_time | none

        "last_offered_slots": [],
        "rejected_slots": [],
        "selected_slot": None,
        "booking_confirmed": False,

        "last_detected_date_text": None,
        "last_detected_time_text": None,
    },

    "info_state": {
        "last_info_decision": "NONE",       # NONE | CONTINUE
        "answered_topics": [],
        "open_questions": [],
        "last_topic": None,
    }
}
```

---

## Agent Output Schema

All agents (Exit, Schedule, Info, Main) must return:

```python
{
    "decision": "...",                # CONTINUE | SCHEDULE | END | NONE
    "assistant_message": "...",       # text to show user (can be empty for non-final steps)
    "state_update": {
        "top_level": {},
        "main_state": {},
        "exit_state": {},
        "schedule_state": {},
        "info_state": {}
    }
}
```

---

## State Update Rules

### General
- Only include fields that need to change
- Do not overwrite full state unnecessarily
- Python merges updates into `conversation_state`

### Merge Logic (simple version)
- Scalars → replace
- Dicts → shallow merge
- Lists → replace

---

## Allowed Fields per Section

### top_level
```python
{
    "status": "...",
    "last_action": "...",
    "turn_count_delta": 1
}
```

---

### main_state
```python
{
    "final_decision": "...",
    "last_routing_reason": "..."
}
```

---

### exit_state
```python
{
    "end_signal_count": 0,
    "strong_opt_out_detected": False,
    "last_exit_decision": "...",
    "last_exit_reason": "..."
}
```

---

### schedule_state
```python
{
    "active": False,
    "last_schedule_decision": "...",
    "last_sub_intent": "...",
    "last_offered_slots": [],
    "rejected_slots": [],
    "selected_slot": None,
    "booking_confirmed": False,
    "last_detected_date_text": None,
    "last_detected_time_text": None
}
```

---

### info_state
```python
{
    "last_info_decision": "...",
    "answered_topics": [],
    "open_questions": [],
    "last_topic": None
}
```

---

## Slot Object Format

```python
slot = {
    "date": "YYYY-MM-DD",
    "time": "HH:MM:SS",
    "position": "Python Dev"
}
```

---

## Decision Values

```text
CONTINUE
SCHEDULE
END
NONE
```

---

## Status Values

```text
new
active
scheduling
scheduled
ended
```

---

## last_action Values

```text
none
continue
answer_info
offer_slots
ask_slot_clarification
confirm_booking
end
```

---

## Scheduling Sub-Intent Values

```text
propose_slots
validate_slot
book_slot
clarify_time
none
```

---

## Design Principles

- Chat history = natural language memory
- conversation_state = structured operational memory
- Agents decide → Python executes
- Each advisor updates only its own state section
- Main agent updates top-level decisions

---

## Summary

This schema enables:
- deterministic orchestration
- modular agents
- minimal Python logic
- clear evaluation and debugging

