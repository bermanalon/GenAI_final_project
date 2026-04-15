# app/main.py

"""
Application entry point for the recruiting chatbot.

First test version:
- create LangChain chat model
- build the main agent with message history
- provide default Streamlit session state
- delegate one turn to main_agent
"""


import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.modules.orchestration.main_agent import build_main_agent, run_main_agent


def bootstrap_app():
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing in .env")

    model_name = os.getenv("OPENAI_MODEL", "gpt-5.4")

    model = ChatOpenAI(
        model=model_name,
        api_key=api_key,
    )

    main_agent = build_main_agent(model)
    return main_agent


def create_initial_session_state():
    return {
        "registration_submitted": False,
        "applicant_info": {},
        "messages": [],
        "api_error": "",
        "conversation_state": {
            "status": "new",
            "last_action": "none",
            "turn_count": 0,
            "session_id": None,
            "restart_requested": False,
        },
    }


def process_user_message(main_agent, applicant_info, chat_history, conversation_state):
    return run_main_agent(
        agent=main_agent,
        applicant_info=applicant_info,
        chat_history=chat_history,
        conversation_state=conversation_state,
    )