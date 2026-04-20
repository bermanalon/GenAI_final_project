# app/main.py

"""
Application entry point for the recruiting chatbot.

This module:
- loads environment variables
- creates the shared LLM model
- builds all agents explicitly
- provides default Streamlit session state
- delegates one user turn to the main orchestrator
"""

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.modules.orchestration.main_agent import build_main_agent, run_main_agent
from app.modules.orchestration.exit_agent import build_exit_advisor
from app.modules.orchestration.schedule_agent import build_schedule_advisor
from app.modules.orchestration.info_agent import build_info_advisor


def bootstrap_app():
    """
    Load configuration, create the model, and build all agents explicitly.
    """
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing in .env")

    model_name = os.getenv("OPENAI_MODEL", "gpt-5.4")

    model = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        temperature=0,
    )

    agents = {
        "main_agent": build_main_agent(model),
        "exit_advisor": build_exit_advisor(model),
        "schedule_advisor": build_schedule_advisor(model),
        "info_advisor": build_info_advisor(model),
    }

    return agents


def create_initial_session_state():
    """
    Default Streamlit session state for a new conversation.
    """
    return {
        "registration_submitted": False,
        "applicant_info": {},
        "messages": [],
        "api_error": "",
        "end_session": False,
        "conversation_state": {
            "status": "new",
            "last_action": "none",
            "turn_count": 0,
            "session_id": None,
            "conversation_log": [],
            "log_meta": {
                "next_turn_id": 1,
                "last_logged_user_text": None,
            },
            "main_state": {
                "route": None,
                "final_decision": None,
                "last_routing_reason": None,
            },
            "exit_state": {
                "end_signal_count": 0,
                "strong_opt_out_detected": False,
                "last_exit_decision": "continue",
                "last_exit_reason": None,
            },
            "schedule_state": {
                "active": False,
                "last_schedule_decision": "none",
                "last_sub_intent": "none",
                "last_offered_slots": [],
                "rejected_slots": [],
                "selected_slot": None,
                "booking_confirmed": False,
                "last_detected_date_text": None,
                "last_detected_time_text": None,
            },
            "info_state": {
                "last_info_decision": "none",
                "answered_topics": [],
                "open_questions": [],
                "last_topic": None,
            },
        },
    }


def process_user_message(agents, applicant_info, chat_history, conversation_state):
    """
    Delegate one user turn to the main orchestrator.
    """
    return run_main_agent(
        main_agent=agents["main_agent"],
        exit_advisor=agents["exit_advisor"],
        schedule_advisor=agents["schedule_advisor"],
        info_advisor=agents["info_advisor"],
        applicant_info=applicant_info,
        chat_history=chat_history,
        conversation_state=conversation_state,
    )