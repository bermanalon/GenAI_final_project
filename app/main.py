import os
import uuid
from dotenv import load_dotenv
from openai import OpenAI


def bootstrap_app() -> OpenAI:
    """
    Load environment variables, validate API key, and return OpenAI client.
    """
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is missing. Add it to your .env file or environment variables."
        )

    client = OpenAI()
    return client


def create_initial_session_state() -> dict:
    """
    Return initial session data for a new applicant session.
    """
    return {
        "session_id": str(uuid.uuid4()),
        "registration_submitted": False,
        "applicant_info": {
            "first_name": "",
            "last_name": "",
            "email": "",
            "phone_number": "",
        },
        "messages": [],
        "api_error": "",
    }