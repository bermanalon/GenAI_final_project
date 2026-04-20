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
- continue: continue the conversation, answer questions, gather more information, or send a mainly informational reply
- schedule: actively move the conversation through interview scheduling, including proposing, negotiating, or confirming an interview meeting
- end: end the conversation because the candidate is no longer interested, asked to stop, or the conversation has already been fully concluded with no further substantive reply needed

Important rules:
- If the candidate asks for information or the recruiter is mainly answering a question, return continue
- If the recruiter message mainly provides information, return continue even if it also mentions that the interview is confirmed or booked
- Use end only when the message mainly closes the conversation, such as a short wrap-up after booking, a goodbye, or acknowledging opt-out
- If the conversation is actively choosing, proposing, changing, negotiating, or setting up an interview, return schedule
- If the recruiter’s message is mostly informational and only lightly suggests a future meeting for the first time, prefer continue over schedule
- If the candidate opts out, is no longer interested, asks to stop, or the conversation is clearly concluded, return end

Important adaptation for this system:
- Use the full conversation and decide the single best next action for the chatbot
- Even if both scheduling and information appear in the latest turn, choose only one label:
  - choose continue when the next assistant reply should mainly answer, explain, or gather information
  - choose schedule when the next assistant reply should mainly propose, validate, negotiate, or confirm an interview slot
- Do not return JSON
- Do not explain your answer

Borderline examples:

Example 1:
CHAT:
RECRUITER: Hi, thanks for submitting your application for our Python Developer role. Could you share a bit about your Python experience?
CANDIDATE: I've been using Python professionally for five years, mostly for data analysis.
RECRUITER: Our engineering manager can interview you Wednesday at 10 AM or Thursday at 2 PM. Which works best?
CANDIDATE: Tuesday at 10 AM works. But can I get more details about the position?
RECRUITER: Great, your interview is confirmed. Sure, We're looking for a skilled Python Developer with expertise in Python 3 and experience working with frameworks such as Django, Flask, or FastAPI. The ideal candidate should be familiar with building RESTful APIs, working with SQL or NoSQL databases, and using version control systems like Git.

LABEL:
continue

Example 2:
CHAT:
RECRUITER: Hi, thanks for submitting your application for our Python Developer role. Could you share a bit about your Python experience?
CANDIDATE: I have three years' experience with Pyhon and AWS.
RECRUITER: Could you elaborate on your experience with cloud platforms like AWS?
CANDIDATE: I've worked a bit with AWS, mainly for deploying small apps and managing storage, but I'm still gaining experience and open to learning more.
RECRUITER: I see, the role focuses on building backend services in Python, mainly FastAPI.
CANDIDATE: Sounds very interesting, I'm confident I can handle it
RECRUITER: Great, Can we set up a meeting next Tuesday

LABEL:
schedule

Return only the label, with no explanation.
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

    # 1. EXIT ADVISOR FIRST
    exit_result = run_exit_advisor(
        exit_advisor=exit_advisor,
        chat_history=chat_history,
        conversation_state=state,
    )

    state = apply_state_update(state, exit_result.get("state_update", {}))

    if exit_result["decision"] == "END":
        assistant_text = exit_result["assistant_message"].strip()

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

    # 2. MAIN ROUTING
    route = get_main_route(
        main_agent=main_agent,
        state=state,
        user_message=user_message,
    )

    # Exit remains owned by the exit advisor
    if route == "end":
        route = "continue"

    state["main_state"]["route"] = route

    # 3. EXECUTE ONE PRIMARY ADVISOR ONLY
    if route == "schedule":
        advisor_result = run_schedule_advisor(
            schedule_advisor=schedule_advisor,
            chat_history=chat_history,
            state=state,
        )

        state = apply_state_update(state, advisor_result.get("state_update", {}))

        assistant_text = advisor_result.get("assistant_message", "").strip()

        if assistant_text:
            final_decision = "schedule"
            label = "schedule"

            if state["schedule_state"].get("booking_confirmed"):
                state["status"] = "scheduled"
            else:
                state["status"] = "scheduling"

            state["last_action"] = "schedule"
        else:
            info_result = run_info_advisor(
                info_advisor=info_advisor,
                chat_history=chat_history,
                state=state,
            )
            state = apply_state_update(state, info_result.get("state_update", {}))

            assistant_text = info_result.get("assistant_message", "").strip()
            final_decision = "continue"
            label = "continue"
            state["status"] = "active"
            state["last_action"] = "continue"

    else:
        info_result = run_info_advisor(
            info_advisor=info_advisor,
            chat_history=chat_history,
            state=state,
        )

        state = apply_state_update(state, info_result.get("state_update", {}))

        assistant_text = info_result.get("assistant_message", "").strip()
        final_decision = "continue"
        label = "continue"
        state["status"] = "active"
        state["last_action"] = "continue"

    if not assistant_text:
        assistant_text = "Could you please clarify?"

    state["main_state"]["final_decision"] = final_decision
    append_assistant_turn(state, assistant_text, label)

    return {
        "assistant_message": assistant_text,
        "conversation_state": state,
        "end_session": False,
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