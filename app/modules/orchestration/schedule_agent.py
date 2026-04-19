# app/modules/orchestration/schedule_agent.py

"""
Scheduling Advisor.

Simple tool-calling agent version.

Responsibilities:
- Read full chat history
- Decide whether the user is in a scheduling flow
- Infer referenced date/time from conversation context if needed
- Use tools to get slots / validate / book
- Return one simple structured result to the main agent
"""

import json
from datetime import datetime

from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import tool

from app.modules.scheduling.schedule_tools import execute_schedule_tool


DEFAULT_POSITION = "Python Dev"


@tool
def get_nearest_slots_tool(start_date: str, position: str = DEFAULT_POSITION, limit: int = 3) -> str:
    """
    Get the nearest available interview slots on or after start_date.
    Use this when the candidate wants to schedule or asks for available times.
    start_date must be in YYYY-MM-DD format.
    """
    result = execute_schedule_tool(
        "get_nearest_slots",
        {
            "start_date": start_date,
            "position": position,
            "limit": limit,
        }
    )
    return json.dumps(result)


@tool
def validate_slot_tool(date: str, time: str, position: str = DEFAULT_POSITION) -> str:
    """
    Validate whether a specific interview slot is available.
    Use this when the candidate proposes or selects a specific date/time.
    date must be YYYY-MM-DD and time must be HH:MM:SS.
    """
    result = execute_schedule_tool(
        "validate_slot",
        {
            "date": date,
            "time": time,
            "position": position,
        }
    )
    return json.dumps(result)


@tool
def book_slot_tool(date: str, time: str, position: str = DEFAULT_POSITION) -> str:
    """
    Book a validated interview slot.
    Use this only after a slot was checked and found available.
    date must be YYYY-MM-DD and time must be HH:MM:SS.
    """
    result = execute_schedule_tool(
        "book_slot",
        {
            "date": date,
            "time": time,
            "position": position,
        }
    )
    return json.dumps(result)


def build_schedule_advisor(model):
    """
    Build the scheduling advisor as a LangChain tool-calling agent.
    """
    tools = [
        get_nearest_slots_tool,
        validate_slot_tool,
        book_slot_tool,
    ]

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            """
You are the Scheduling Advisor in a recruiting chatbot for a Python Developer position.

Your job:
- Decide whether the current user turn is about scheduling.
- If it is about scheduling, use the available tools.
- If it is not about scheduling, do not use tools.

You must use the full chat history and the conversation state.

Important rules:
- If the user wants to schedule but does not give a specific slot, get the nearest 3 available slots.
- If the user refers to a date in natural language, infer the exact date from the conversation context and today's date.
- If the user selects or proposes a specific slot, validate it.
- If the slot is available, book it.
- If the slot is not available, offer the nearest 3 available alternatives.
- If the message is only about job information, return NONE and do not use scheduling tools.

Today's date:
{today}

Position:
{position}

Return a final answer as valid JSON only with this schema:
{{
  "decision": "SCHEDULE" or "NONE",
  "assistant_message": "string",
  "selected_slot": {{"date": "YYYY-MM-DD", "time": "HH:MM:SS"}} or null,
  "offered_slots": [{{"date": "YYYY-MM-DD", "time": "HH:MM:SS"}}] or [],
  "booking_confirmed": true or false,
  "last_sub_intent": "none" or "offer_slots" or "validate_slot" or "book_slot"
}}

Examples:
1.
User: "I'd like to schedule an interview."
Return JSON with decision="SCHEDULE", use get_nearest_slots_tool, and offer 3 slots.

2.
User: "Tuesday at 10 AM works for me."
If you can infer the exact date from context, validate it.
If available, book it.

3.
User: "Those times don't work. Anything next week?"
Use get_nearest_slots_tool again.

4.
User: "Is the role hybrid?"
Return:
{{"decision":"NONE","assistant_message":"","selected_slot":null,"offered_slots":[],"booking_confirmed":false,"last_sub_intent":"none"}}
"""
        ),
        ("system", "Conversation state:\n{conversation_state}"),
        ("system", "Chat history:\n{chat_history}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
        ("user", "{input}"),
    ])

    agent = create_tool_calling_agent(
        llm=model,
        tools=tools,
        prompt=prompt,
    )

    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
    )

    return executor


def run_schedule_advisor(schedule_advisor, chat_history, conversation_state):
    """
    Run the scheduling advisor on the latest user message.

    Returns:
    {
        "decision": "SCHEDULE" or "NONE",
        "assistant_message": "...",
        "state_update": {...}
    }
    """
    latest_user_message = get_latest_user_message(chat_history).strip()

    response = schedule_advisor.invoke(
        {
            "input": latest_user_message,
            "chat_history": format_chat_history(chat_history),
            "conversation_state": format_schedule_state(conversation_state),
            "today": get_today_date_string(),
            "position": DEFAULT_POSITION,
        }
    )

    parsed = parse_schedule_output(response.get("output", ""))

    decision = parsed.get("decision", "NONE")
    assistant_message = parsed.get("assistant_message", "")
    selected_slot = parsed.get("selected_slot")
    offered_slots = parsed.get("offered_slots", [])
    booking_confirmed = parsed.get("booking_confirmed", False)
    last_sub_intent = parsed.get("last_sub_intent", "none")

    if decision not in ["SCHEDULE", "NONE"]:
        decision = "NONE"

    return {
        "decision": decision,
        "assistant_message": assistant_message,
        "state_update": {
            "top_level": {
                "status": "scheduled" if booking_confirmed else ("scheduling" if decision == "SCHEDULE" else conversation_state.get("status", "active")),
                "last_action": (
                    "confirm_booking" if booking_confirmed
                    else "offer_slots" if decision == "SCHEDULE"
                    else conversation_state.get("last_action", "none")
                ),
            },
            "main_state": {},
            "exit_state": {},
            "schedule_state": {
                "active": decision == "SCHEDULE",
                "last_schedule_decision": decision,
                "last_sub_intent": last_sub_intent,
                "last_offered_slots": offered_slots,
                "selected_slot": selected_slot,
                "booking_confirmed": booking_confirmed,
            },
            "info_state": {},
        }
    }


def get_latest_user_message(chat_history):
    """
    Return the latest user message from full chat history.
    """
    for msg in reversed(chat_history):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return ""


def format_chat_history(chat_history):
    """
    Convert full chat history into a readable text block.
    """
    lines = []
    for msg in chat_history:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def format_schedule_state(conversation_state):
    """
    Keep the schedule context compact.
    """
    schedule_state = conversation_state.get("schedule_state", {})

    lines = []
    lines.append(f"status: {conversation_state.get('status')}")
    lines.append(f"last_action: {conversation_state.get('last_action')}")
    lines.append(f"booking_confirmed: {schedule_state.get('booking_confirmed')}")
    lines.append(f"selected_slot: {schedule_state.get('selected_slot')}")
    lines.append(f"last_offered_slots: {schedule_state.get('last_offered_slots')}")
    return "\n".join(lines)


def parse_schedule_output(output_text):
    """
    Parse the agent JSON output safely.
    """
    try:
        parsed = json.loads(output_text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    return {
        "decision": "NONE",
        "assistant_message": "",
        "selected_slot": None,
        "offered_slots": [],
        "booking_confirmed": False,
        "last_sub_intent": "none",
    }


def get_today_date_string():
    """
    Return today's date in YYYY-MM-DD format.
    """
    return datetime.now().strftime("%Y-%m-%d")