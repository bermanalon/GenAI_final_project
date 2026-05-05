# Conversation State & Agent Output Schema

## Overview
This document defines the structure of:
- `conversation_state`
- `state_update`
- agent outputs

It defines how agents communicate and update shared state for orchestrating the multi-agent recruiting chatbot.

---

## Conversation State Schema

```python
conversation_state = {
    "status": "new",         # new | active | scheduling | scheduled | ended
    "last_action": "none",   # none | continue | schedule | end
    "turn_count": 0,
    "session_id": None,

    # Optional structured logging (used for debugging / analysis)
    "conversation_log": [],
    "log_meta": {
        "next_turn_id": 1
    },

    # Agents sections
    "main_state": {
        "route": None,
        "final_decision": None,
    },

    "exit_state": {
        "last_exit_decision": "CONTINUE",
    },

    "schedule_state": {
        "active": False,
        "last_schedule_decision": "NONE",
        "last_offered_slots": [],
        "selected_slot": None,
        "booking_confirmed": False,
    },

    "info_state": {
        "last_info_decision": "NONE",
    }
}
```
---

### Logging (Optional)

The system maintains a structured conversation log for debugging and analysis.

Each turn includes:
- speaker (user / assistant)
- message text
- decision label
- timestamp
---

## Agent Handoff

Advisors can request that the Main Agent invokes another advisor.

Fields:

- `handoff_to`: "schedule" | "info" | null  
- `handoff_context`: optional string

Used when:
- Info → Schedule (candidate ready for scheduling)
- Schedule → Info (user asked question while in scheduling)

---

## Agent Output Schema

All agents (Exit, Schedule, Info, Main) must return:

```python
{
    "decision": "...",
    "assistant_message": "...",
    "handoff_to": "...",      # optional (Info/Schedule only)
    "handoff_context": "...", # optional
    "state_update": {...}
}
```

### Decision Values per Agent

- Exit Advisor: END | CONTINUE
- Scheduling Advisor: SCHEDULE | NONE
- Info Advisor: INFO | NONE
- Main Agent (final): continue | schedule | end
---

## State Update Rules

### General

- Python merges updates into `conversation_state`

### Merge Logic
- Scalars → replace the existing value
- Dicts → shallow merge (update only provided fields)
- Lists → replace entirely

---

## Design Principles

- Chat history = natural language memory
- conversation_state = structured operational memory
- Agents decide → Python executes
- Each advisor updates only its own state section
- Main agent updates top-level decisions

---


