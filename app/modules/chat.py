SYSTEM_PROMPT = """
You are a recruiting chatbot for a Python Developer position.

Your role:
1. Be polite, clear, and professional.
2. Answer applicant questions about the role and process.
3. Help move the applicant toward scheduling a recruiter meeting.
4. Use the applicant information provided to personalize the conversation.
5. Rely on the chat history provided to maintain context.
6. Do not invent facts that were not provided.
"""


def build_input_messages(applicant_info: dict, chat_history: list[dict]) -> list[dict]:
    applicant_context = (
        f"Applicant information:\n"
        f"- First name: {applicant_info.get('first_name', '')}\n"
        f"- Last name: {applicant_info.get('last_name', '')}\n"
        f"- Email: {applicant_info.get('email', '')}\n"
        f"- Phone number: {applicant_info.get('phone_number', '')}\n"
    )

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT + "\n\n" + applicant_context
        }
    ]

    for msg in chat_history:
        messages.append(
            {
                "role": msg["role"],
                "content": msg["content"]
            }
        )

    return messages


def get_chatgpt_response(client, applicant_info: dict, chat_history: list[dict]) -> str:
    input_messages = build_input_messages(applicant_info, chat_history)

    response = client.responses.create(
        model="gpt-5.4",
        input=input_messages
    )

    return response.output_text