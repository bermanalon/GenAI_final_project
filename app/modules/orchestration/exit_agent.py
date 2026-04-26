# app/modules/orchestration/exit_agent.py

"""
Exit Advisor.

Purpose:
- Decide whether the conversation should end
- Use the fine-tuned model for the decision
- If ending is appropriate, formulate the final assistant message


"""

from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage


def build_exit_advisor(model):
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You are the Exit Advisor in a recruiting chatbot for a Python Developer position.

Your task:
Decide whether the chatbot should END the conversation now or CONTINUE the conversation.

Return:
END or CONTINUE

Return END only when the conversation should clearly be concluded, for example:
- The candidate says they are not interested
- The candidate asks to stop being contacted
- The candidate says they found another job
- The interaction has naturally concluded after scheduling or final closure
- The candidate softly disengages or cools off, for example:
  "I'll reach out if it becomes relevant",
  "I'll get back to you",
  "I'll contact you if my availability changes"

Return CONTINUE when:
- the candidate is still engaged or participating in the process
- the candidate asks questions or wants more information
- the candidate is discussing availability or scheduling, even if a specific time does not work

Rules:
- Prefer CONTINUE if unsure, EXCEPT when the candidate clearly signals they want to pause, delay, or disengage from the process.
- Return only END or CONTINUE.
- Do not explain your answer.

Implementation notes:
- Use the full conversation history
- Consider the conversation state
- Do not assume END just because booking was confirmed
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
    
def run_exit_advisor(exit_advisor, exit_message_model, chat_history, conversation_state):
    """
    Run the Exit Advisor.

    Returns:
    {
        "decision": "END" or "CONTINUE",
        "assistant_message": "...",
        "state_update": {...}
    }
    """

    user_message = get_last_user_message(chat_history)
    history_messages = convert_to_langchain_messages(chat_history[:-1])

    try:
        response = exit_advisor.invoke(
            {
                "input": user_message,
                "history": history_messages,
                "conversation_state": format_state_for_prompt(conversation_state),
                "agent_scratchpad": [],
            }
        )
        raw_output = response.get("output", "").strip().upper()
    except Exception:
        raw_output = "CONTINUE"

    decision = raw_output if raw_output in ["END", "CONTINUE"] else "CONTINUE"

    if decision == "END":
        assistant_message = generate_exit_message(
            model=exit_message_model,
            chat_history=chat_history,
            conversation_state=conversation_state,
        )
        if not assistant_message:
            assistant_message = assistant_message = "Thank you. Wishing you all the best."
    else:
        assistant_message = ""

    return {
        "decision": decision,
        "assistant_message": assistant_message,
        "state_update": {
            "top_level": {
                "status": "ended" if decision == "END" else conversation_state.get("status", "active"),
                "last_action": "end" if decision == "END" else conversation_state.get("last_action", "none"),
            },
            "main_state": {},
            "exit_state": {
                "last_exit_decision": decision,
            },
            "schedule_state": {},
            "info_state": {},
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

def build_exit_message_prompt(chat_history, conversation_state):
    return f"""
You are a recruiting assistant.

The conversation should now end.

Write one short, polite closing message to the candidate.

Use the full conversation history when writing the message.
Make the message fit the conversation outcome:
- if an interview was scheduled, close positively
- if the candidate is no longer interested or asked to stop, close respectfully

Rules:
- be concise
- do not ask a question
- do not continue the conversation
- return only the message text

Conversation state:
{format_state_for_prompt(conversation_state)}

Chat history:
{format_chat_history(chat_history)}
""".strip()

def generate_exit_message(model, chat_history, conversation_state):
    """
    Generate a polite closing message using the general model,
    based on full chat history and conversation state.
    """

    prompt = build_exit_message_prompt(chat_history, conversation_state)

    try:
        response = model.invoke(prompt)
        return response.content.strip()
    except Exception:
        return ""
    
def format_chat_history(chat_history):
    lines = []

    for msg in chat_history:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")
        lines.append(f"{role}: {content}")

    return "\n".join(lines)

def format_state_for_prompt(state):
    lines = []

    lines.append(f"status: {state.get('status')}")
    lines.append(f"last_action: {state.get('last_action')}")

    schedule_state = state.get("schedule_state", {})
    lines.append(f"booking_confirmed: {schedule_state.get('booking_confirmed')}")
    lines.append(f"selected_slot: {schedule_state.get('selected_slot')}")

    return "\n".join(lines)

