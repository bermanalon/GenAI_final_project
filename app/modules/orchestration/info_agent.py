# app/modules/orchestration/info_agent.py

"""
Info Advisor.

Purpose:
- Answer candidate questions about the role and process
- Maintain engagement
- Help move the conversation toward scheduling
- Detect when the same user message also includes scheduling intent and
  hand off to the Scheduling Advisor

Design:
- Uses the full conversation history via MessagesPlaceholder("history")
- Receives the latest user message separately as "input"
- Receives conversation state as additional context
- Returns structured JSON for the main agent

Current scope:
- Uses simple built-in role facts
- Can later be upgraded to use the job description PDF / vector DB
"""

import json

from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from app.modules.info.retriever import build_context_text

GENERIC_INFO_REPLY = (
    "The next step would usually be to schedule an interview so we can continue the process."
)


def build_info_advisor(model):
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You are the Info Advisor in a recruiting chatbot for a Python Developer position.

Your role:
- Answer candidate questions clearly and briefly
- Assess whether the candidate is relevant for the role
- Maintain engagement and move the conversation toward scheduling when appropriate

Use the FULL conversation history and the conversation state.

Core behavior:

1. Questions:
- If the user asks a job-related question, answer it clearly.
- Use retrieved job information when available.
- If the answer is not in the job description, say so briefly.
- Do not invent details.

2. Candidate relevance:
- If the candidate provides clearly weak experience (e.g., only a few months, beginner level):
  → decision = "INFO"
  → ask one short follow-up question.

- If the candidate provides moderate or strong relevant experience and does NOT ask a question:
  → decision = "INFO"
  → respond with a short natural transition toward scheduling.
  → do NOT set handoff_to = "schedule" in this case.

3. Mixed input:
- If the message includes both a question and scheduling-related content:
  → answer ONLY the question.
  → set handoff_to = "schedule".

4. Short inputs:
- If the message is very short (e.g., "ok", "thanks"):
  - If booking_confirmed = False:
    → decision = "INFO"
    → respond briefly and move the conversation forward.
  - If booking_confirmed = True:
    → decision = "NONE"
    → assistant_message = ""

5. After booking:
- If booking_confirmed = True:
  → answer normally if needed.
  → do NOT suggest scheduling again.

Output JSON only:

{{
  "decision": "INFO" or "NONE",
  "assistant_message": "string",
  "handoff_to": "schedule" or null
}}

Rules:
- If decision = "NONE", assistant_message must be empty.
- Do not mention internal workflow, routing, or advisors.
- Keep responses concise, natural, and professional.

Examples:

User: "I have 3 years of experience with Python and Flask"
Output:
{{
  "decision": "INFO",
  "assistant_message": "That sounds relevant for the role. The next step would be to schedule an interview.",
  "handoff_to": null
}}

User: "I've been using Python for a couple of months"
Output:
{{
  "decision": "INFO",
  "assistant_message": "Could you tell me more about the types of Python projects you've worked on?",
  "handoff_to": null
}}

User: "Is the position remote?"
Retrieved job information: [no clear mention]
Output:
{{
  "decision": "INFO",
  "assistant_message": "I do not see a clear answer about that in the job description.",
  "handoff_to": null
}}

User: "OK"
booking_confirmed: False
Output:
{{
  "decision": "INFO",
  "assistant_message": "Great — would you like to move forward with scheduling an interview?",
  "handoff_to": null
}}
""".strip()
            ),
            ("system", "Conversation state:\n{conversation_state}"),
            ("system", "Retrieved job information:\n{retrieved_context}"),
            MessagesPlaceholder(variable_name="history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(
        llm=model,
        tools=[],
        prompt=prompt,
    )

    return AgentExecutor(
        agent=agent,
        tools=[],
        verbose=False,
    )


def run_info_advisor(info_advisor, chat_history, state):
    user_message = get_last_user_message(chat_history)
    retrieved_context = build_context_text(user_message, k=3)
    history_messages = convert_to_langchain_messages(chat_history[:-1])

    try:
        response = info_advisor.invoke(
            {
                "input": user_message,
                "history": history_messages,
                "conversation_state": format_info_state_for_prompt(state),
                "retrieved_context": retrieved_context,
                "agent_scratchpad": [],
            }
        )

        raw_output = response.get("output", "")
       
        data = safe_parse_info_output(raw_output)

    except Exception as e:
        print("INFO AGENT ERROR:", repr(e))
        data = default_info_result()

    decision = data.get("decision", "NONE")
    assistant_message = data.get("assistant_message", "").strip()
    handoff_to = data.get("handoff_to")

    if decision == "INFO" and not assistant_message:
        assistant_message = GENERIC_INFO_REPLY

    return {
        "decision": decision,
        "assistant_message": assistant_message,
        "handoff_to": handoff_to,
        "state_update": {
            "info_state": {
                "last_info_decision": decision,
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


def format_info_state_for_prompt(state):
    schedule_state = state.get("schedule_state", {})
    return "\n".join(
        [
            f"status: {state.get('status')}",
            f"last_action: {state.get('last_action')}",
            f"schedule_active: {schedule_state.get('active')}",
            f"booking_confirmed: {schedule_state.get('booking_confirmed')}",
            f"last_offered_slots: {schedule_state.get('last_offered_slots')}",
            f"selected_slot: {schedule_state.get('selected_slot')}",
        ]
    )


def safe_parse_info_output(text):
    try:
        data = json.loads(text)

        decision = data.get("decision", "NONE")
        if decision not in ["INFO", "NONE"]:
            decision = "NONE"

        handoff_to = data.get("handoff_to")
        if handoff_to not in ["schedule", None]:
            handoff_to = None

        return {
            "decision": decision,
            "assistant_message": data.get("assistant_message", ""),
            "handoff_to": handoff_to,
        }

    except Exception as e:
        print("INFO AGENT JSON PARSE ERROR:", repr(e), "RAW:", repr(text))
        return default_info_result()


def default_info_result():
    return {
        "decision": "INFO",
        "assistant_message": GENERIC_INFO_REPLY,
        "handoff_to": None,
    }