# app/modules/orchestration/main_agent.py

"""
Main Agent (Orchestrator).

Responsible for handling each user turn. Applies the following flow:
1. Checks with Exit Advisor to avoid unnecessary interaction.
2. Detects user intent (schedule / info / both).
3. Routes the request to the appropriate advisor(s).
4. Composes the final response and decision (CONTINUE / SCHEDULE / END).

This is the core decision-making component of the system.
"""
from langchain_openai import ChatOpenAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory

MEMORY_STORE = {}


def get_history(session_id):
    if session_id not in MEMORY_STORE:
        MEMORY_STORE[session_id] = ChatMessageHistory()
    return MEMORY_STORE[session_id]


def build_main_agent(model):
    main_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a recruiting chatbot for a Python Developer position.\n"
            "Be professional, concise, warm, and clear.\n"
            "Use the conversation history naturally.\n"
            "Answer questions and keep the conversation flowing.\n"
            "Do not mention system design or internal logic."
        ),
        ("system", "Applicant info:\n{applicant_info}"),
        ("system", "Conversation state:\n{conversation_state}"),
        MessagesPlaceholder(variable_name="history"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
        ("user", "{input}")
    ])

    main_agent = create_tool_calling_agent(model, tools=[], prompt=main_prompt)
    main_executor = AgentExecutor(agent=main_agent, tools=[], verbose=False)

    main_agent_with_memory = RunnableWithMessageHistory(
        main_executor,
        get_session_history=get_history,
        input_messages_key="input",
        history_messages_key="history"
    )

    return main_agent_with_memory


def run_main_agent(agent, applicant_info, chat_history, conversation_state):
    updated_state = dict(conversation_state)

    if not updated_state.get("session_id"):
        updated_state["session_id"] = build_session_id(applicant_info)

    latest_user_message = get_latest_user_message(chat_history).strip()

    if latest_user_message.lower() == "exit":
        updated_state["status"] = "ended"
        updated_state["last_action"] = "exit"

        return {
            "assistant_message": (
                "Thank you for the conversation. I will end this chat here. "
                "You can start over whenever you are ready."
            ),
            "conversation_state": updated_state,
            "end_session": True,
        }

    response = agent.invoke(
        {
            "input": latest_user_message,
            "applicant_info": format_applicant_info(applicant_info),
            "conversation_state": format_state(updated_state),
        },
        config={
            "configurable": {
                "session_id": updated_state["session_id"]
            }
        },
    )

    assistant_text = response["output"]

    updated_state["turn_count"] = updated_state.get("turn_count", 0) + 1
    updated_state["status"] = "in_conversation"
    updated_state["last_action"] = "reply"

    return {
        "assistant_message": assistant_text,
        "conversation_state": updated_state,
        "end_session": False,
    }

def build_session_id(applicant_info):
    email = applicant_info.get("email", "").strip()
    return f"user_{email}"


def format_applicant_info(applicant_info):
    return "\n".join([f"{k}: {v}" for k, v in applicant_info.items()])


def format_state(state):
    return "\n".join([f"{k}: {v}" for k, v in state.items()])


def get_latest_user_message(chat_history):
    for msg in reversed(chat_history):
        if msg["role"] == "user":
            return msg["content"]
    return ""