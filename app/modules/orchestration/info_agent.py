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
- Maintain engagement
- Help move the conversation forward toward scheduling when appropriate

Use the FULL conversation history and the conversation state.

Core behavior:

1. Questions:
- If the user asks a question → answer it clearly
- Use retrieved job information when available
- If the answer is not in the job description, say so briefly

2. Relevance handling:
- If the user provides some relevant experience to the job description and does NOT ask a question:
  → do NOT generate an informational reply
  → return:
      decision = "NONE"
      assistant_message = ""
      handoff_to = "schedule"

- If the experience is clearly weak (e.g., only a few months or very limited):
  → continue the conversation (decision = "INFO")
  → ask for more details or encourage elaboration
  → If you judge the user relevance to the job very low, say so politely
  → If the user exhibits eagerness or will to learn or will to continue the process
  → return:
      decision = "NONE"
      assistant_message = ""
      handoff_to = "schedule"
  
3. Mixed input:
- If the message includes both a question AND scheduling-related content:
  → answer ONLY the question
  → set handoff_to = "schedule"

4. Short / empty inputs:
- If the message is very short and not meaningful (e.g., "ok", "thanks"):
  → decision = "NONE"

5. After booking:
- If booking_confirmed = True:
  → answer normally
  → do NOT suggest scheduling again

Output format (JSON only):

{{
  "decision": "INFO" or "NONE",
  "assistant_message": "string",
  "handoff_to": "schedule" or null
}}

Rules:
- If decision = "NONE", assistant_message must be empty
- Do not mention internal workflow, routing, or advisors
- Keep responses concise, natural, and professional

Examples:

User: "I have 3 years of experience with Python and Flask"
booking_confirmed: False
Output:
{{
  "decision": "NONE",
  "assistant_message": "",
  "handoff_to": "schedule"
}}

User: "I've been using Python for a couple of months"
Output:
{{
  "decision": "INFO",
  "assistant_message": "Could you tell me more about the types of projects you've worked on?",
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

User: "The second option works for me, is the position remote?"
Output:
{{
  "decision": "INFO",
  "assistant_message": "I do not see a clear answer about that in the job description.",
  "handoff_to": "schedule"
}}

User: "OK"
Output:
{{
  "decision": "NONE",
  "assistant_message": "",
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