# app/modules/orchestration/main_agent.py

from datetime import datetime, timezone

from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory

from app.modules.orchestration.exit_agent import run_exit_advisor
from app.modules.orchestration.schedule_agent import run_schedule_advisor
from app.modules.orchestration.info_agent import run_info_advisor


MEMORY_STORE = {}
MAX_ADVISOR_CALLS_PER_TURN = 2


def get_history(session_id):
    if session_id not in MEMORY_STORE:
        MEMORY_STORE[session_id] = ChatMessageHistory()
    return MEMORY_STORE[session_id]


def build_main_agent(model):
    routing_instructions = """
You are evaluating the routing decision of a recruiting chatbot.

Given the full conversation so far, return ONLY one of these exact labels:
continue
schedule
end

Definitions:
- continue: the next assistant reply should mainly answer questions, provide information, or gather more details
- schedule: the next assistant reply should mainly handle interview scheduling (propose, validate, confirm, or book a slot)
- end: the conversation should be concluded

Rules:
- If the candidate asks a question not related to scheduling → continue
- If the next assistant reply should gather more information about the candidate → continue
- If the conversation is already in scheduling flow (proposing or confirming slots) → schedule
- If schedule_state.active = true and the user message looks like a response to proposed interview slots,
  → return schedule
- If the candidate provides experience/background but does not explicitly ask to schedule, return continue so the Info Advisor can assess relevance and decide whether to ask more or move toward scheduling.
- If the candidate opts out or asks to stop → return end
- If the candidate clearly wants to stop, is not interested, or the conversation is already fully closed -> end

Important:
- Choose only ONE label
- If unsure between continue and schedule:
  → If scheduling is active, prefer schedule
  → otherwise prefer continue

Return only the label.
""".strip()

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", routing_instructions),
            ("system", "Conversation state:\n{conversation_state}"),
            MessagesPlaceholder(variable_name="history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(model, tools=[], prompt=prompt)
    executor = AgentExecutor(agent=agent, tools=[], verbose=False)

    return RunnableWithMessageHistory(
        executor,
        get_session_history=get_history,
        input_messages_key="input",
        history_messages_key="history",
    )


def run_main_agent(
    main_agent,
    exit_advisor,
    exit_message_model,
    schedule_advisor,
    info_advisor,
    applicant_info,
    chat_history,
    conversation_state,
):
    state = dict(conversation_state)

    if not state.get("session_id"):
        state["session_id"] = "session_1"

    ensure_state(state)
    ensure_logging(state)

    user_message = get_latest_user_message(chat_history).strip()
    append_user_turn(state, user_message)
    state["turn_count"] = state.get("turn_count", 0) + 1

    exit_result = run_exit_advisor(
        exit_advisor=exit_advisor,
        exit_message_model=exit_message_model,
        chat_history=chat_history,
        conversation_state=state,
    )
    
    state = apply_state_update(state, exit_result.get("state_update", {}))

    if exit_result["decision"] == "END":
        assistant_text = exit_result.get("assistant_message", "").strip()
        if not assistant_text:
            assistant_text = "Thank you for the update. I wish you the best."

        append_assistant_turn(state, assistant_text, "end")
        state["status"] = "ended"
        state["last_action"] = "end"
        state["main_state"]["route"] = "end"
        state["main_state"]["final_decision"] = "end"

        return {
            "assistant_message": assistant_text,
            "conversation_state": state,
            "end_session": True,
        }

    route = get_main_route(main_agent, state, user_message)
       
    if route == "end":
        route = "continue"

    state["main_state"]["route"] = route

    advisor_calls = 0
    primary_result = None
    secondary_result = None

    if route == "schedule":
        primary_result = run_schedule_advisor(
            schedule_advisor=schedule_advisor,
            chat_history=chat_history,
            state=state,
        )
    else:
        primary_result = run_info_advisor(
            info_advisor=info_advisor,
            chat_history=chat_history,
            state=state,
        )

    advisor_calls += 1
    state = apply_state_update(state, primary_result.get("state_update", {}))

    handoff_to = primary_result.get("handoff_to")
     
    if handoff_to and advisor_calls < MAX_ADVISOR_CALLS_PER_TURN:
        if handoff_to == "schedule":
            secondary_result = run_schedule_advisor(
                schedule_advisor=schedule_advisor,
                chat_history=chat_history,
                state=state,
                handoff_context=primary_result.get("handoff_context", ""),
            )
        elif handoff_to == "info":
            secondary_result = run_info_advisor(
                info_advisor=info_advisor,
                chat_history=chat_history,
                state=state,
            )

        if secondary_result:
            advisor_calls += 1
            state = apply_state_update(state, secondary_result.get("state_update", {}))
    
    
    
    if (
        route == "schedule"
        and primary_result.get("decision") == "NONE"
        and advisor_calls < MAX_ADVISOR_CALLS_PER_TURN
    ):
        secondary_result = run_info_advisor(
            info_advisor=info_advisor,
            chat_history=chat_history,
            state=state,
        )

        advisor_calls += 1
        state = apply_state_update(state, secondary_result.get("state_update", {}))

    assistant_text = build_final_message(primary_result, secondary_result)
    
    final_decision = decide_final_label(route, primary_result, secondary_result, assistant_text)

            # fallback
    if not assistant_text:
        assistant_text = "Could you please clarify?"
        final_decision = "continue"

    if final_decision == "end":
        state["status"] = "ended"
    elif final_decision == "schedule":
        state["status"] = "scheduled" if state["schedule_state"].get("booking_confirmed") else "scheduling"
    else:
        state["status"] = "active"

    state["last_action"] = final_decision
    state["main_state"]["final_decision"] = final_decision

    append_assistant_turn(state, assistant_text, final_decision)

    return {
        "assistant_message": assistant_text,
        "conversation_state": state,
        "end_session": final_decision == "end",
    }   

def get_main_route(main_agent, state, user_message):
    try:
        response = main_agent.invoke(
            {
                "input": user_message,
                "conversation_state": format_state(state),
            },
            config={
                "configurable": {
                    "session_id": state["session_id"] + "_routing"
                }
            },
        )

        output_text = response["output"].strip().lower()
        if output_text in ["continue", "schedule", "end"]:
            return output_text
    except Exception:
        pass

    return "continue"


def build_final_message(primary_result, secondary_result):
    parts = []

    primary_text = (primary_result or {}).get("assistant_message", "").strip()
    secondary_text = (secondary_result or {}).get("assistant_message", "").strip()

    if primary_text:
        parts.append(primary_text)

    if secondary_text and secondary_text != primary_text:
        parts.append(secondary_text)

    return "\n\n".join(parts).strip()


def decide_final_label(route, primary_result, secondary_result, assistant_text):
    if not assistant_text:
        return "continue"

    booking_confirmed = False

    for result in [primary_result, secondary_result]:
        if result and result.get("booking_confirmed"):
            booking_confirmed = True
            break

    if booking_confirmed:
        handoff_to_info = any(
            result and result.get("handoff_to") == "info"
            for result in [primary_result, secondary_result]
        )

        if handoff_to_info:
            return "continue"

        return "end"

    for result in [primary_result, secondary_result]:
        if result and result.get("decision") == "SCHEDULE":
            return "schedule"

    return "continue"

def apply_state_update(state, update):
    for key, value in update.get("top_level", {}).items():
        state[key] = value

    for section in ["main_state", "exit_state", "schedule_state", "info_state"]:
        state.setdefault(section, {})
        state[section].update(update.get(section, {}))

    return state


def get_latest_user_message(history):
    for message in reversed(history):
        if message["role"] == "user":
            return message["content"]
    return ""


def ensure_state(state):
    for key in ["main_state", "exit_state", "schedule_state", "info_state"]:
        state.setdefault(key, {})
    state.setdefault("status", "active")
    state.setdefault("last_action", "none")
    state.setdefault("turn_count", 0)


def ensure_logging(state):
    state.setdefault("conversation_log", [])
    state.setdefault("log_meta", {"next_turn_id": 1})


def append_user_turn(state, text):
    state["conversation_log"].append(
        {
            "turn_id": state["log_meta"]["next_turn_id"],
            "speaker": "user",
            "text": text,
            "label": None,
            "timestamp_utc": now(),
        }
    )
    state["log_meta"]["next_turn_id"] += 1


def append_assistant_turn(state, text, label):
    state["conversation_log"].append(
        {
            "turn_id": state["log_meta"]["next_turn_id"],
            "speaker": "assistant",
            "text": text,
            "label": label,
            "timestamp_utc": now(),
        }
    )
    state["log_meta"]["next_turn_id"] += 1


def now():
    return datetime.now(timezone.utc).isoformat()


def format_state(state):
    return "\n".join(f"{key}: {value}" for key, value in state.items())