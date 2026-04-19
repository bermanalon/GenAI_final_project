# app/modules/orchestration/main_agent.py

"""
Main Agent (Orchestrator).

Responsible for handling each user turn. Applies the following flow:
1. Checks with Exit Advisor to avoid unnecessary interaction.
2. Detects user intent (schedule / info / both).
3. Routes the request to the appropriate advisor(s).
4. Composes the final response and decision (CONTINUE / SCHEDULE / END).

This is the core decision-making component of the system.
"""

from datetime import datetime, timezone

from langchain_openai import ChatOpenAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory

from app.modules.orchestration.exit_agent import run_exit_advisor
from app.modules.orchestration.schedule_agent import run_schedule_advisor
from app.modules.orchestration.info_agent import run_info_advisor

MEMORY_STORE = {}


def get_history(session_id):
    """
    Return message history for a session.
    """
    if session_id not in MEMORY_STORE:
        MEMORY_STORE[session_id] = ChatMessageHistory()
    return MEMORY_STORE[session_id]


def build_main_agent(model):
    """
    Build the main conversational agent with memory.
    """
    main_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a recruiting chatbot for a Python Developer position.\n"
            "Be professional, concise, warm, and clear.\n"
            "Use the conversation history naturally.\n"
            "Answer questions and keep the conversation flowing.\n"
            "Do not mention internal logic, advisors, routing, or system design."
        ),
        ("system", "Applicant info:\n{applicant_info}"),
        ("system", "Conversation state:\n{conversation_state}"),
        MessagesPlaceholder(variable_name="history"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
        ("user", "{input}")
    ])

    main_agent = create_tool_calling_agent(model, tools=[], prompt=main_prompt)
    main_executor = AgentExecutor(agent=main_agent, tools=[], verbose=False)

    main_agent_with_memory = RunnableWithMessageHistory(
        main_executor,
        get_session_history=get_history,
        input_messages_key="input",
        history_messages_key="history",
    )

    return main_agent_with_memory


def run_main_agent(
    main_agent,
    exit_advisor,
    schedule_advisor,
    info_advisor,
    applicant_info,
    chat_history,
    conversation_state,
):
    """
    Handle one user turn.

    Flow:
    1. Ensure session id
    2. Log latest user turn
    3. Run Exit Advisor first
    4. If END -> use Exit Advisor ending message and return
    5. Otherwise run Schedule Advisor
    6. If SCHEDULE -> use Schedule Advisor response and return
    7. Otherwise let the main agent reply normally
    """
    updated_state = dict(conversation_state)

    if not updated_state.get("session_id"):
        updated_state["session_id"] = build_session_id(applicant_info)

    ensure_logging_state(updated_state)

    latest_user_message = get_latest_user_message(chat_history).strip()

    append_user_turn_if_needed(updated_state, latest_user_message)

    # --------------------------------------------------
    # 1) EXIT ADVISOR
    # --------------------------------------------------
    exit_result = run_exit_advisor(
        exit_advisor=exit_advisor,
        chat_history=chat_history,
        conversation_state=updated_state,
    )

    updated_state = apply_state_update(
        updated_state,
        exit_result.get("state_update", {})
    )

    if exit_result.get("decision") == "END":
        assistant_text = exit_result.get(
            "assistant_message",
            "Thank you for the conversation. I will end this chat here."
        )

        updated_state["turn_count"] = updated_state.get("turn_count", 0) + 1
        updated_state["status"] = "ended"
        updated_state["last_action"] = "end"
        updated_state["main_state"]["final_decision"] = "END"
        updated_state["main_state"]["last_routing_reason"] = "exit_advisor_end"

        append_assistant_turn(
            updated_state,
            text=assistant_text,
            label="end",
        )

        return {
            "assistant_message": assistant_text,
            "conversation_state": updated_state,
            "end_session": True,
        }

    # --------------------------------------------------
    # 2) SCHEDULE ADVISOR
    # --------------------------------------------------
    schedule_result = run_schedule_advisor(
        schedule_advisor=schedule_advisor,
        chat_history=chat_history,
        conversation_state=updated_state,
    )

    updated_state = apply_state_update(
        updated_state,
        schedule_result.get("state_update", {})
    )

    if schedule_result.get("decision") == "SCHEDULE":
        assistant_text = schedule_result.get(
            "assistant_message",
            "I can help schedule the interview."
        )

        updated_state["turn_count"] = updated_state.get("turn_count", 0) + 1
        updated_state["main_state"]["final_decision"] = "SCHEDULE"
        updated_state["main_state"]["last_routing_reason"] = "schedule_advisor_schedule"

        append_assistant_turn(
            updated_state,
            text=assistant_text,
            label="schedule",
        )

        return {
            "assistant_message": assistant_text,
            "conversation_state": updated_state,
            "end_session": False,
        }

    # --------------------------------------------------
    # 3) NORMAL MAIN AGENT RESPONSE
    # --------------------------------------------------
    response = main_agent.invoke(
        {
            "input": latest_user_message,
            "applicant_info": format_applicant_info(applicant_info),
            "conversation_state": format_state(updated_state),
        },
        config={
            "configurable": {
                "session_id": updated_state["session_id"]
            }
        },
    )

    assistant_text = response["output"]

    updated_state["turn_count"] = updated_state.get("turn_count", 0) + 1
    updated_state["status"] = "active"
    updated_state["last_action"] = "continue"
    updated_state["main_state"]["final_decision"] = "CONTINUE"
    updated_state["main_state"]["last_routing_reason"] = "main_agent_continue"

    append_assistant_turn(
        updated_state,
        text=assistant_text,
        label="continue",
    )

    return {
        "assistant_message": assistant_text,
        "conversation_state": updated_state,
        "end_session": False,
    }


def apply_state_update(current_state, state_update):
    """
    Apply a structured state_update onto the current conversation state.

    Rules:
    - top_level fields are merged into the root state
    - nested state sections are shallow-merged
    - missing sections are ignored
    """
    updated = dict(current_state)

    top_level = state_update.get("top_level", {})
    for key, value in top_level.items():
        if key == "turn_count_delta":
            updated["turn_count"] = updated.get("turn_count", 0) + value
        else:
            updated[key] = value

    for section in ["main_state", "exit_state", "schedule_state", "info_state"]:
        section_update = state_update.get(section, {})
        if section not in updated:
            updated[section] = {}
        updated[section] = {**updated.get(section, {}), **section_update}

    return updated


def build_session_id(applicant_info):
    """
    Build a stable session id from applicant email.
    """
    email = applicant_info.get("email", "").strip()
    return f"user_{email}"


def format_applicant_info(applicant_info):
    """
    Convert applicant info dict to a readable text block for the prompt.
    """
    return "\n".join([f"{k}: {v}" for k, v in applicant_info.items()])


def format_state(state):
    """
    Convert conversation state dict to a readable text block for the prompt.
    """
    lines = []

    for key, value in state.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for sub_key, sub_value in value.items():
                lines.append(f"  {sub_key}: {sub_value}")
        elif isinstance(value, list):
            lines.append(f"{key}: {len(value)} items")
        else:
            lines.append(f"{key}: {value}")

    return "\n".join(lines)


def get_latest_user_message(chat_history):
    """
    Return the most recent user message from chat history.
    """
    for msg in reversed(chat_history):
        if msg["role"] == "user":
            return msg["content"]
    return ""


def ensure_logging_state(state):
    """
    Ensure logging fields exist in conversation_state.
    """
    if "conversation_log" not in state:
        state["conversation_log"] = []

    if "log_meta" not in state:
        state["log_meta"] = {
            "next_turn_id": 1,
            "last_logged_user_text": None,
        }


def append_user_turn_if_needed(state, text):
    """
    Append the latest user turn only if it was not logged yet.
    """
    if not text:
        return

    ensure_logging_state(state)

    if state["log_meta"].get("last_logged_user_text") == text:
        return

    state["conversation_log"].append({
        "turn_id": state["log_meta"]["next_turn_id"],
        "speaker": "user",
        "text": text,
        "label": None,
        "timestamp_utc": get_utc_timestamp(),
    })

    state["log_meta"]["next_turn_id"] += 1
    state["log_meta"]["last_logged_user_text"] = text


def append_assistant_turn(state, text, label):
    """
    Append an assistant turn with the action label decided by the system.
    """
    ensure_logging_state(state)

    state["conversation_log"].append({
        "turn_id": state["log_meta"]["next_turn_id"],
        "speaker": "assistant",
        "text": text,
        "label": label,
        "timestamp_utc": get_utc_timestamp(),
    })

    state["log_meta"]["next_turn_id"] += 1


def get_utc_timestamp():
    """
    Return current UTC timestamp as ISO string.
    """
    return datetime.now(timezone.utc).isoformat()