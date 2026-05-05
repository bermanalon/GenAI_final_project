# app/main.py

"""
Application bootstrap and entry layer.

Responsibilities:
- Load environment configuration
- Initialize LLM models and advisor agents
- Create initial session and conversation state
- Expose the main processing function used by the UI
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
    Initialize models and build all agents.

    Returns:
        dict: Contains initialized agents used by the application.
    """
    
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing in .env")

    model_name = os.getenv("OPENAI_MODEL", "gpt-5.4")
    exit_model_name = os.getenv(
        "OPENAI_EXIT_MODEL",
        "ft:gpt-4.1-2025-04-14:personal::DX9OaOX9",
    )

    general_model = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        temperature=0,
    )
    
    # Separate model for exit decision (fine-tuned)
    exit_decision_model = ChatOpenAI(
        model=exit_model_name,
        api_key=api_key,
        temperature=0,
    )

    return {
        "main_agent": build_main_agent(general_model),
        "exit_advisor": build_exit_advisor(exit_decision_model),
        "exit_message_model": general_model,    # Generates polite closing text
        "schedule_advisor": build_schedule_advisor(general_model),
        "info_advisor": build_info_advisor(general_model),
    }

def create_initial_session_state():
    """
    Create the initial session and conversation state.

    Returns:
        dict: Initial state used by the Streamlit app.
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
            },
            "main_state": {
                "route": None,
                "final_decision": None,
            },
            "exit_state": {
                "last_exit_decision": "continue",
            },
            "schedule_state": {
                "active": False,
                "last_schedule_decision": "none",
                "last_offered_slots": [],
                "selected_slot": None,
                "booking_confirmed": False,
            },
            "info_state": {
                "last_info_decision": "none",
                "last_topic": None,
            },
        },
    }


def process_user_message(agents, applicant_info, chat_history, conversation_state):
    """
    Process a user message through the main agent orchestration.

    Returns:
        dict: Assistant response and updated conversation state.
    """
    return run_main_agent(
        main_agent=agents["main_agent"],
        exit_advisor=agents["exit_advisor"],
        exit_message_model=agents["exit_message_model"],
        schedule_advisor=agents["schedule_advisor"],
        info_advisor=agents["info_advisor"],
        applicant_info=applicant_info,
        chat_history=chat_history,
        conversation_state=conversation_state,
    )