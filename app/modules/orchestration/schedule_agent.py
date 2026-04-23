# app/modules/orchestration/schedule_agent.py

"""
Scheduling Advisor.

Purpose:
- Handle all interview scheduling interactions within the recruiting chatbot
- Interpret candidate intent related to proposing, confirming, or modifying interview times
- Use tool calling to:
    - retrieve available slots
    - validate requested slots
    - book confirmed interviews

Design:
- Uses LangChain tool-calling agent with access to scheduling tools
- Receives full conversation history via MessagesPlaceholder ("history")
- Receives the latest user message separately as "input"
- Returns structured JSON output for the main agent to consume

Responsibilities:
- Detect whether a scheduling action should be performed
- Propose available time slots when needed
- Validate and confirm candidate-selected slots
- Book interviews when confirmation is clear
- Handle partial scheduling + information requests via handoff_to="info"

Output Contract:
{
  "decision": "SCHEDULE" or "NONE",
  "assistant_message": "string",
  "selected_slot": {"date": "...", "time": "..."} or null,
  "offered_slots": [...],
  "booking_confirmed": true/false,
  "handoff_to": "info" or null,
  "state_update": {...}
}

Notes:
- "SCHEDULE" means active scheduling flow
- "NONE" means no scheduling action should be taken in this turn
- The main agent is responsible for orchestration and combining responses
"""

import json

from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from app.modules.scheduling.schedule_tools import execute_schedule_tool


DEFAULT_POSITION = "Python Dev"


@tool
def get_slots(start_date: str):
    """
    Get the 3 nearest available interview slots starting from a given date.
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

You are called when scheduling is the primary action for this turn.

Use FULL chat history.

Important:
- Short replies like "yes", "ok", "that works", "Wednesday works" may confirm a previously suggested time
- Interpret short confirmations using context
- If the candidate proposes a date and time, validate that slot
- If the candidate wants to schedule but no exact slot is confirmed yet, offer the 3 nearest available slots
- If a slot is available and clearly selected, book it
- If the requested slot is not available, offer alternatives
- If the candidate also asks a job-related question, handle the scheduling part and set handoff_to = "info"

Closing behavior (very important):

- When booking_confirmed = true AND the user message does NOT include any additional question:
  - The assistant_message MUST include:
    1. the booking confirmation
    2. a short polite closing remark (e.g., "Looking forward to speaking with you.")

- When booking_confirmed = true AND the user message ALSO includes an information question:
  - The assistant_message MUST include ONLY the booking confirmation
  - DO NOT include a closing remark
  - DO NOT answer the information question
  - DO NOT mention handoff, routing, or that another part will be handled separately
  - Set handoff_to = "info"

Return JSON ONLY in this exact shape:

{{
  "decision": "SCHEDULE" or "NONE",
  "assistant_message": "string",
  "selected_slot": {{"date": "YYYY-MM-DD", "time": "HH:MM:SS"}} or null,
  "offered_slots": [{{"date": "YYYY-MM-DD", "time": "HH:MM:SS"}}],
  "booking_confirmed": true or false,
  "handoff_to": "info" or null
}}

Rules:
- If you are actively proposing, negotiating, validating, or confirming interview time, decision = "SCHEDULE"
- If you cannot perform a scheduling step from the current message, decision = "NONE"
- If decision = "NONE", assistant_message should be empty
- Return valid JSON only
If the message also includes an information question, handle ONLY the scheduling part in assistant_message.
Do not answer the information question.
Do not mention handoff, team, routing, or that another part of the message will be handled separately.
Set handoff_to = "info" internally when needed.
""".strip(),
            ),
            MessagesPlaceholder(variable_name="history"),
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
    history_messages = convert_to_langchain_messages(chat_history[:-1])

    response = schedule_advisor.invoke(
        {
            "input": user_message,
            "history": history_messages,
            "agent_scratchpad": [],
        }
    )

    data = safe_parse(response.get("output", ""))

    decision = data.get("decision", "NONE")
    assistant_message = data.get("assistant_message", "").strip()
    selected_slot = data.get("selected_slot")
    offered_slots = data.get("offered_slots", [])
    booking_confirmed = data.get("booking_confirmed", False)
    handoff_to = data.get("handoff_to")

    return {
        "decision": decision,
        "assistant_message": assistant_message,
        "selected_slot": selected_slot,
        "offered_slots": offered_slots,
        "booking_confirmed": booking_confirmed,
        "handoff_to": handoff_to,
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


def convert_to_langchain_messages(history):
    messages = []

    for message in history:
        role = message.get("role")
        content = message.get("content", "")

        if not content:
            continue

        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    return messages


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
            "handoff_to": None,
        }