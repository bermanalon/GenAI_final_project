# app/modules/orchestration/exit_agent.py

"""
Exit Advisor.

Purpose:
- Decide whether the conversation should end
- Use only the model for the decision
- If ending is appropriate, formulate the final assistant message

This version keeps the same external contract:
- build_exit_advisor(model)
- run_exit_advisor(exit_advisor, chat_history, conversation_state)
"""

import json


def build_exit_advisor(model):
    """
    Build the Exit Advisor.
    """
    return {
        "model": model
    }


def run_exit_advisor(exit_advisor, chat_history, conversation_state):
    """
    Run the Exit Advisor on the full chat history.

    Returns:
        {
            "decision": "END" or "CONTINUE",
            "assistant_message": "...",
            "state_update": {...}
        }
    """
    llm_result = ask_llm_exit_decision(
        model=exit_advisor["model"],
        chat_history=chat_history,
        conversation_state=conversation_state,
    )

    decision = llm_result.get("decision", "CONTINUE")
    assistant_message = llm_result.get("assistant_message", "")

    if decision not in ["END", "CONTINUE"]:
        decision = "CONTINUE"

    if decision == "CONTINUE":
        assistant_message = ""

    if decision == "END" and not assistant_message:
        assistant_message = "Thank you for the conversation. I wish you all the best."

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
                "last_exit_reason": llm_result.get("reason", "llm_decision"),
            },
            "schedule_state": {},
            "info_state": {},
        }
    }


def ask_llm_exit_decision(model, chat_history, conversation_state):
    """
    Ask the model whether the conversation should END or CONTINUE.

    Expected JSON output:
    {
      "decision": "END" or "CONTINUE",
      "assistant_message": "string",
      "reason": "short_reason"
    }
    """
    prompt = build_exit_prompt(chat_history, conversation_state)

    try:
        response = model.invoke(prompt)
        content = extract_text_from_llm_response(response)
        parsed = json.loads(content)

        return {
            "decision": parsed.get("decision", "CONTINUE"),
            "assistant_message": parsed.get("assistant_message", ""),
            "reason": parsed.get("reason", "llm_decision"),
        }

    except Exception:
        return {
            "decision": "CONTINUE",
            "assistant_message": "",
            "reason": "llm_fallback_continue",
        }


def build_exit_prompt(chat_history, conversation_state):
    """
    Build the prompt for the Exit Advisor.
    """
    return f"""
You are the Exit Advisor in a recruiting chatbot for a Python Developer position.

Your task:
Decide whether the chatbot should END the conversation now or CONTINUE the conversation.

Return END only when the conversation should clearly be concluded, for example:
- the candidate says they are not interested
- the candidate asks to stop being contacted
- the candidate says they found another job
- the interaction has naturally concluded after scheduling or final closure

Return CONTINUE when:
- the candidate is still engaged
- the candidate asks questions
- the candidate wants more information
- the candidate wants to schedule or continue the process
- there is any reasonable doubt

Rules:
- Prefer CONTINUE if unsure.
- If decision is CONTINUE, assistant_message must be an empty string.
- If decision is END, assistant_message must contain a short, polite closing message.
- Do not mention internal logic, advisors, routing, labels, or system behavior.
- Return valid JSON only.

Output schema:
{{
  "decision": "END" or "CONTINUE",
  "assistant_message": "string",
  "reason": "short_reason"
}}

Examples:

Example 1:
Candidate message: "Please remove me from your list."
Output:
{{"decision":"END","assistant_message":"Understood. Thank you for the update, and best of luck.","reason":"candidate_opt_out"}}

Example 2:
Candidate message: "Is the position still open?"
Output:
{{"decision":"CONTINUE","assistant_message":"","reason":"candidate_still_engaged"}}

Example 3:
Candidate message: "Sounds great, see you then."
Conversation context: interview already confirmed
Output:
{{"decision":"END","assistant_message":"Great, thank you. We look forward to speaking with you.","reason":"natural_closure_after_confirmation"}}

Conversation state:
{format_conversation_state(conversation_state)}

Chat history:
{format_chat_history(chat_history)}
""".strip()


def format_chat_history(chat_history):
    """
    Convert chat history into a readable text block.
    """
    lines = []

    for msg in chat_history:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")
        lines.append(f"{role}: {content}")

    return "\n".join(lines)


def format_conversation_state(conversation_state):
    """
    Convert relevant state fields into a compact text block.
    """
    lines = []

    lines.append(f"status: {conversation_state.get('status')}")
    lines.append(f"last_action: {conversation_state.get('last_action')}")
    lines.append(f"turn_count: {conversation_state.get('turn_count')}")

    exit_state = conversation_state.get("exit_state", {})
    schedule_state = conversation_state.get("schedule_state", {})

    lines.append(f"last_exit_decision: {exit_state.get('last_exit_decision')}")
    lines.append(f"booking_confirmed: {schedule_state.get('booking_confirmed')}")
    lines.append(f"selected_slot: {schedule_state.get('selected_slot')}")

    return "\n".join(lines)


def extract_text_from_llm_response(response):
    """
    Extract plain text from LangChain model response.
    """
    if hasattr(response, "content"):
        if isinstance(response.content, str):
            return response.content.strip()

        if isinstance(response.content, list):
            parts = []
            for item in response.content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif hasattr(item, "get") and item.get("text"):
                    parts.append(item.get("text", ""))
            return "".join(parts).strip()

    return str(response).strip()