"""
main.py (UI TEST VERSION)

Purpose:
- Provide minimal backend so Streamlit UI can run
- No real LLM, no agents
- Deterministic responses for testing UI flow

Next step:
- Replace process_user_message with real orchestration
"""

import os


# --------------------------------------------------
# Bootstrap (mock)
# --------------------------------------------------

def bootstrap_app():
    """
    For now, return a dummy client object.
    Later this will initialize OpenAI client.
    """
    return {"mode": "test"}


# --------------------------------------------------
# Session state defaults
# --------------------------------------------------

def create_initial_session_state():
    return {
        "registration_submitted": False,
        "applicant_info": {},
        "messages": [],
        "api_error": "",
        "conversation_state": {
            "status": "collecting",
            "last_action": "none",
            "ended": False,
            "scheduled": False,
            "turn_count": 0,
        },
    }


# --------------------------------------------------
# Fake chatbot logic (for UI testing only)
# --------------------------------------------------

def process_user_message(client, applicant_info, chat_history, conversation_state):
    """
    Very simple rule-based logic to test UI behavior.
    """

    user_message = get_latest_user_message(chat_history).lower()

    updated_state = dict(conversation_state)
    updated_state["turn_count"] += 1

    # ---- Exit cases ----
    if any(x in user_message for x in ["not interested", "stop", "remove", "bye"]):
        updated_state["status"] = "ended"
        updated_state["last_action"] = "end"
        updated_state["ended"] = True

        return {
            "assistant_message": "Understood. Thank you for your time. Have a great day!",
            "conversation_state": updated_state,
        }

    # ---- Scheduling cases ----
    if any(x in user_message for x in ["interview", "schedule", "meeting"]):
        updated_state["status"] = "scheduling"
        updated_state["last_action"] = "schedule"

        return {
            "assistant_message": (
                "Sure! Here are some available time slots:\n"
                "- Tuesday at 10 AM\n"
                "- Wednesday at 2 PM\n"
                "- Thursday at 4 PM\n"
                "Which one works for you?"
            ),
            "conversation_state": updated_state,
        }

    if any(x in user_message for x in ["works", "good", "ok", "yes"]):
        updated_state["status"] = "scheduled"
        updated_state["last_action"] = "schedule"
        updated_state["scheduled"] = True

        return {
            "assistant_message": (
                "Great, your interview is confirmed. "
                "You'll receive a calendar invite shortly."
            ),
            "conversation_state": updated_state,
        }

    # ---- Info cases ----
    if any(x in user_message for x in ["role", "job", "position", "stack"]):
        updated_state["status"] = "collecting"
        updated_state["last_action"] = "continue"

        return {
            "assistant_message": (
                "This is a Python Developer role focused on backend development, "
                "data pipelines, and working with technologies like Python, SQL, and cloud platforms. "
                "Would you like to schedule an interview?"
            ),
            "conversation_state": updated_state,
        }

    # ---- Default ----
    updated_state["status"] = "collecting"
    updated_state["last_action"] = "continue"

    return {
        "assistant_message": (
            "Thanks for your message! I can help with information about the role "
            "or schedule an interview. What would you like to do?"
        ),
        "conversation_state": updated_state,
    }


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def get_latest_user_message(chat_history):
    for msg in reversed(chat_history):
        if msg["role"] == "user":
            return msg["content"]
    return ""