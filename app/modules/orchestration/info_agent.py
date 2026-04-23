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
- Acknowledge relevant candidate information when useful
- Help move the conversation toward scheduling

Use the FULL conversation history and the conversation state.

Known facts for this stage:
- The role follows a hybrid work model, with a mix of remote and in-office work
- The role focuses on Python backend development, APIs, databases, and cross-functional collaboration

Important behavior:
- If booking_confirmed is false, do not stop at generic information
- When appropriate, help move the conversation forward toward scheduling
- If the user asks about the next step, explain that the next step is scheduling an interview
- If the user shares relevant background or experience, acknowledge it briefly and naturally, then help move the conversation forward
- If the same user message also includes scheduling confirmation or slot selection, answer the information part and set handoff_to = "schedule"
- If booking_confirmed is true, answer directly and do not suggest scheduling again

Mixed-input rule:
- If the same user message also includes scheduling confirmation, slot selection, or another scheduling request, answer ONLY the information part.
- Do not mention scheduling in assistant_message unless it is directly needed for the information answer.
- Do not mention handoff, routing, advisors, the team, or that another part will be handled separately.
- If scheduling content is present, set handoff_to = "schedule" internally.

Very important:
- Do not mention internal workflow
- Do not mention advisors, handoff, routing, system behavior, or "the team"
- Do not say that you can also help with the question later
- Do not use vague filler replies
- The assistant_message must be fully user-facing, natural, and useful

Return JSON ONLY in this exact shape:

{{
  "decision": "INFO" or "NONE",
  "assistant_message": "string",
  "handoff_to": "schedule" or null
}}

Rules:
- If the user asks a question, requests the next step, shares relevant background, or shows interest in moving forward, decision should usually be "INFO"
- If booking_confirmed is false, prefer a reply that naturally advances the conversation
- If no information-style response is needed, decision = "NONE"
- If decision = "NONE", assistant_message should be empty
- Keep the reply concise and professional
- Return valid JSON only

Examples:

User: "I've been using Python professionally for five years, mostly for data analysis."
Conversation state:
booking_confirmed: False
Output:
{{
  "decision": "INFO",
  "assistant_message": "That sounds like strong relevant experience for this role. The next step would usually be to schedule an interview.",
  "handoff_to": null
}}

User: "what is the next step?"
Conversation state:
booking_confirmed: False
Output:
{{
  "decision": "INFO",
  "assistant_message": "The next step would be to schedule an interview so we can continue the process.",
  "handoff_to": null
}}

User: "Is the position remote?"
Conversation state:
booking_confirmed: False
Output:
{{
  "decision": "INFO",
  "assistant_message": "The role follows a hybrid work model, with a mix of remote and in-office work. If that works for you, the next step would be to schedule an interview.",
  "handoff_to": null
}}

User: "the second option works for me, is the position remote?"
Conversation state:
booking_confirmed: False
Output:
{{
  "decision": "INFO",
  "assistant_message": "The role follows a hybrid work model, with a mix of remote and in-office work.",
  "handoff_to": "schedule"
}}

User: "What's next?"
Conversation state:
booking_confirmed: True
Output:
{{
  "decision": "INFO",
  "assistant_message": "Your interview is already confirmed, so you're all set for the next step.",
  "handoff_to": null
}}
""".strip(),
            ),
            ("system", "Conversation state:\n{conversation_state}"),
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
    history_messages = convert_to_langchain_messages(chat_history[:-1])

    try:
        response = info_advisor.invoke(
            {
                "input": user_message,
                "history": history_messages,
                "conversation_state": format_info_state_for_prompt(state),
                "agent_scratchpad": [],
            }
        )

        raw_output = response.get("output", "")
        print("INFO AGENT RAW OUTPUT:", repr(raw_output))

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