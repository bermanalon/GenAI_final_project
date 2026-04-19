# app/modules/orchestration/info_agent.py

"""
Info Advisor (stub version)

Purpose:
- Answer candidate questions (later)
- For now: do nothing
"""


def build_info_advisor(model):
    return {
        "model": model
    }


def run_info_advisor(info_advisor, chat_history, conversation_state):
    """
    Stub logic:
    Always return NONE (no info handling)
    """

    return {
        "decision": "NONE",
        "assistant_message": "",
        "state_update": {
            "top_level": {},
            "main_state": {},
            "exit_state": {},
            "schedule_state": {},
            "info_state": {
                "last_info_decision": "NONE"
            }
        }
    }