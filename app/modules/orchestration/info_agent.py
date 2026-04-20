# app/modules/orchestration/info_agent.py

"""
Info Advisor

Purpose:
- Answer candidate questions
- Continue the conversation when the main agent routes to "continue"
- For now this is still a simple stub, but with a stable interface
"""


def build_info_advisor(model):
    return {"model": model}


def run_info_advisor(
    info_advisor,
    chat_history,
    state=None,
    conversation_state=None,
):
    current_state = state if state is not None else conversation_state
    if current_state is None:
        current_state = {}

    return {
        "decision": "CONTINUE",
        "assistant_message": (
            "Thanks for your question. For now, the info advisor is still a stub."
        ),
        "state_update": {
            "top_level": {},
            "main_state": {},
            "exit_state": {},
            "schedule_state": {},
            "info_state": {
                "last_info_decision": "continue",
                "last_topic": "stub",
            },
        },
    }