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

from datetime import date

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
            ("system", "Current date: {current_date}"),
            ("system", "Conversation state:\n{conversation_state}"),
            ("system", "Handoff context:\n{handoff_context}"),
            ("system",
"""
You are the Scheduling Advisor in a recruiting chatbot.

Your role:
Handle all scheduling-related interactions and move the conversation toward booking an interview.

You are called when scheduling is the primary action for this turn.
Use the FULL chat history.


---------------------
DECISION PRIORITY
---------------------

Always follow this order:

0. Determine if scheduling is required:
- If handoff_context is provided, scheduling is required for this turn.
- If handoff_context is empty AND the user message is clearly unrelated to scheduling OR scheduling is already completed:
  → decision = "NONE"

1. Identify the scheduling intent:
   - new request
   - proposing a date/time
   - selecting from offered slots
   - relative date request

2. Resolve the date/time:
   - interpret relative dates using Current date

3. Use tools:
    - get_slots → when proposing availability
    - validate → when checking availability of a specific slot
    - book → when booking a slot
    
4. Base your response strictly on tool results.

5. Only then generate the final response (tone + wording)

---------------------
SCHEDULING BEHAVIOR
---------------------
0. Scheduling rule:
- Interviews cannot be scheduled on the same day as the chat.
- The earliest valid interview slot is the day after the chat date.
- Whenever availability is needed, call a scheduling tool.

1. Proposing slots:
- If the candidate wants to schedule but no specific date/time is given:
  → call get_slots using one day after current date as start_date
  → offer the 3 nearest available slots

2. Handling specific date/time:
- If the candidate proposes a specific date/time:
  → validate it using validate_slot

- If available:
  → call book
  → then confirm the booking

- If not available:
  → clearly say it is not available
  → suggest other alternatives later in time

3. Selecting from offered slots:
- If the candidate selects one of the offered slots by time, day, or option number:
  → call book(date, time) immediately
  → if booked=true, confirm the booking to the user
  → set booking_confirmed=true
   
4. If the candidate rejects all offered slots:
→ call get_slots again using the day after the latest offered slot as start_date
→ offer the next 3 available slots.

5. Relative dates:
- Interpret relative dates using Current date:
  ("next Friday" means "current Friday")

- For relative date requests:
  → resolve the date
  → call get_slots with that date as start_date
  → offer the nearest available slots

---------------------
BOOKING RULES
---------------------

- Always book BEFORE confirming
- Never say the interview is confirmed unless book_slot returned booked = true
- After successful booking:
  → clearly state the interview is confirmed

- If booking_confirmed = true AND no additional question:
  → include confirmation + short polite closing

- If booking_confirmed = true AND there is also a question:
  → include ONLY confirmation
  → set handoff_to = "info"


---------------------
INTERPRETING USER INPUT
---------------------

- Short replies like:
  "yes", "ok", "that works", "Wednesday works"
  → may confirm a previously suggested slot

- Use conversation context to interpret them


---------------------
MIXED INPUT
---------------------

- If the message includes scheduling + job question:
  → handle ONLY scheduling
  → set handoff_to = "info"

- Scheduling-related questions include:
  date, time, availability, booking, rescheduling

- Only set handoff_to = "info" for job-related questions
  (role, requirements, technologies, benefits, etc.)


---------------------
COMMUNICATION STYLE
---------------------

- Natural, human recruiter tone
- Concise and clear
- Do NOT reuse fixed templates

- Use affirmative tone (e.g., "Great", "Sure") ONLY when:
  → the slot is available OR successfully booked

- Do NOT use affirmative wording if the slot is not available

- Do not explain availability from your own reasoning.



---------------------
DECISION RULES
---------------------

- If proposing, validating, or booking → decision = "SCHEDULE"
- Return "NONE" only if scheduling is not appropriate or already completed
- If decision = "NONE" → assistant_message must be empty


---------------------
OUTPUT FORMAT (JSON ONLY)
---------------------

{{
  "decision": "SCHEDULE" or "NONE",
  "assistant_message": "string",
  "selected_slot": {{"date": "YYYY-MM-DD", "time": "HH:MM:SS"}} or null,
  "offered_slots": [{{"date": "YYYY-MM-DD", "time": "HH:MM:SS"}}],
  "booking_confirmed": true or false,
  "handoff_to": "info" or null
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


def run_schedule_advisor(schedule_advisor, chat_history, state, handoff_context=None):
    user_message = get_last_user_message(chat_history)
    history_messages = convert_to_langchain_messages(chat_history[:-1])

    response = schedule_advisor.invoke(
        {
            "input": user_message,
            "history": history_messages,
            "current_date": date.today().isoformat(),
            "conversation_state": format_state(state),
            "handoff_context": handoff_context or "",
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
        
def format_state(state):
    return "\n".join(f"{key}: {value}" for key, value in state.items())