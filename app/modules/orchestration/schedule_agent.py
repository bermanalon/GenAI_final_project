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
You are the Scheduling Advisor in a recruiting chatbot.

You are called when scheduling is the primary action for this turn.

Use the FULL chat history.

Core behavior:

1. Scheduling actions:
- If the candidate proposes a specific date/time → validate it
- If the slot is available → confirm booking
- If not available → suggest alternatives
- If the candidate wants to schedule but no specific time is selected → offer the 3 nearest available slots

2. Interpreting short replies:
- Short replies like "yes", "ok", "that works", "Wednesday works" may confirm a previously suggested time
- Use conversation context to interpret them

3. Mixed input:
- If the user message includes both scheduling and a job-related question:
  → handle ONLY the scheduling part
  → set handoff_to = "info"

4. Booking confirmation:
- If booking_confirmed = true AND no additional question:
  → include:
     - confirmation
     - short polite closing remark (e.g., "Looking forward to speaking with you.")
- If booking_confirmed = true AND there is also a question:
  → include ONLY the confirmation
  → set handoff_to = "info"

Rules:
- If actively proposing, validating, or confirming time → decision = "SCHEDULE"
- return decision = "NONE" only if scheduling does not make sense or not needed anymore
- If decision = "NONE", assistant_message must be empty

Output format (JSON only):

{{
  "decision": "SCHEDULE" or "NONE",
  "assistant_message": "string",
  "selected_slot": {{"date": "YYYY-MM-DD", "time": "HH:MM:SS"}} or null,
  "offered_slots": [{{"date": "YYYY-MM-DD", "time": "HH:MM:SS"}}],
  "booking_confirmed": true or false,
  "handoff_to": "info" or null
}}


Examples:

User: "I have 3 years of Python experience"

Output:
{{
  "decision": "SCHEDULE",
  "assistant_message": "Could we schedule a chat at one of these times?\n- ...\n- ...\n- ...",
  "selected_slot": null,
  "offered_slots": [...],
  "booking_confirmed": false,
  "handoff_to": null
}}

User: "Wednesday at 10 works"
Output:
{{
  "decision": "SCHEDULE",
  "assistant_message": "Great, your interview is confirmed for Wednesday at 10:00.",
  "selected_slot": {{"date": "...", "time": "..."}},
  "offered_slots": [],
  "booking_confirmed": true,
  "handoff_to": null
}}

User: "Can we schedule?"
Output:
{{
  "decision": "SCHEDULE",
  "assistant_message": "Could we schedule an interview at one of these times?\n- ...\n- ...\n- ...",
  "selected_slot": null,
  "offered_slots": [...],
  "booking_confirmed": false,
  "handoff_to": null
}}
""".strip()
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