# app/modules/orchestration/schedule_agent.py

import json

from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import tool

from app.modules.scheduling.schedule_tools import execute_schedule_tool


DEFAULT_POSITION = "Python Dev"


@tool
def get_slots(start_date: str):
    """
    Get the 3 nearest available interview slots starting from a given date.

    Use this when the candidate wants to schedule or asks for available times.
    """
    return json.dumps(
        execute_schedule_tool(
            "get_nearest_slots",
            {
                "start_date": start_date,
                "position": DEFAULT_POSITION,
                "limit": 3,
            },
        )
    )


@tool
def validate(date: str, time: str):
    """
    Check if a specific interview slot is available.

    Use this when the candidate proposes or confirms a date and time.
    """
    return json.dumps(
        execute_schedule_tool(
            "validate_slot",
            {
                "date": date,
                "time": time,
                "position": DEFAULT_POSITION,
            },
        )
    )


@tool
def book(date: str, time: str):
    """
    Book an interview slot if it is available.

    Use this only after validating that the slot is available.
    """
    return json.dumps(
        execute_schedule_tool(
            "book_slot",
            {
                "date": date,
                "time": time,
                "position": DEFAULT_POSITION,
            },
        )
    )


def build_schedule_advisor(model):
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You are the scheduling advisor for a recruiting chatbot.

You are called only when the main agent has already decided that scheduling
is the primary action for this turn.

Use FULL chat history.

Important:
- "yes", "ok", "that works", "Wednesday works", and similar short replies may confirm a previously suggested time
- You MUST interpret short confirmations from context
- If the candidate proposes a date and time, validate that slot
- If the candidate asks to schedule but no exact slot is confirmed yet, offer the 3 nearest available slots
- If a slot is available and the candidate clearly selected it, book it
- If the requested slot is not available, offer alternatives
- Return NONE only if scheduling truly cannot proceed from the current message

Return JSON ONLY in this exact shape:

{{
  "decision": "SCHEDULE" or "NONE",
  "assistant_message": "string",
  "selected_slot": {{"date": "YYYY-MM-DD", "time": "HH:MM:SS"}} or null,
  "offered_slots": [{{"date": "YYYY-MM-DD", "time": "HH:MM:SS"}}],
  "booking_confirmed": true or false
}}

Rules:
- If you are actively proposing, negotiating, validating, or confirming an interview time, decision = "SCHEDULE"
- If you cannot perform a scheduling step from the current message, decision = "NONE"
- If decision = "NONE", assistant_message should be an empty string
- Return valid JSON only
""".strip(),
            ),
            ("system", "Chat history:\n{chat_history}"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    tools = [get_slots, validate, book]

    agent = create_tool_calling_agent(
        llm=model,
        tools=tools,
        prompt=prompt,
    )   

    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
    )


def run_schedule_advisor(schedule_advisor, chat_history, state):
    user_message = get_last_user_message(chat_history)

    response = schedule_advisor.invoke(
        {
            "input": user_message,
            "chat_history": format_history(chat_history),
            "agent_scratchpad": [],
        }
    )

    data = safe_parse(response.get("output", ""))

    decision = data.get("decision", "NONE")
    assistant_message = data.get("assistant_message", "")
    selected_slot = data.get("selected_slot")
    offered_slots = data.get("offered_slots", [])
    booking_confirmed = data.get("booking_confirmed", False)

    return {
        "decision": decision,
        "assistant_message": assistant_message,
        "selected_slot": selected_slot,
        "offered_slots": offered_slots,
        "booking_confirmed": booking_confirmed,
        "state_update": {
            "schedule_state": {
                "active": decision == "SCHEDULE" and not booking_confirmed,
                "last_schedule_decision": decision,
                "last_offered_slots": offered_slots,
                "selected_slot": selected_slot,
                "booking_confirmed": booking_confirmed,
            }
        },
    }


def get_last_user_message(history):
    for message in reversed(history):
        if message["role"] == "user":
            return message["content"]
    return ""


def format_history(history):
    return "\n".join(
        f"{message['role'].upper()}: {message['content']}"
        for message in history
    )


def safe_parse(text):
    try:
        return json.loads(text)
    except Exception:
        return {
            "decision": "NONE",
            "assistant_message": "",
            "selected_slot": None,
            "offered_slots": [],
            "booking_confirmed": False,
        }