# app/streamlit_main.py

"""
Streamlit UI for the Recruiting Chatbot.

This module handles:
- Candidate registration
- Chat interface
- Display of conversation history and current state
"""

import os
import sys

import streamlit as st

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.main import (
    bootstrap_app,
    create_initial_session_state,
    process_user_message,
)


st.set_page_config(
    page_title="Recruitment Chatbot",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 0.6rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def initialize_session_state():
    defaults = create_initial_session_state()
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_app():
    defaults = create_initial_session_state()
    st.session_state.clear()
    for key, value in defaults.items():
        st.session_state[key] = value


def validate_registration(first_name, last_name, email, phone_number):
    errors = []

    if not first_name.strip():
        errors.append("First Name is required.")
    if not last_name.strip():
        errors.append("Last Name is required.")
    if not email.strip():
        errors.append("Email is required.")
    if not phone_number.strip():
        errors.append("Phone Number is required.")

    return errors


def format_state(state):
    mapping = {
        "new": "Starting",
        "active": "Conversation in Progress",
        "scheduling": "Scheduling in Progress",
        "scheduled": "Interview Scheduled",
        "ended": "Conversation Completed",
    }
    return mapping.get(state, "Conversation")


def render_registration_screen():
    left_spacer, center_col, right_spacer = st.columns([1, 1.7, 1])

    with center_col:
        with st.container(border=True):
            st.subheader("Registration Form")
            st.write("Please fill in your details for the Python Developer position.")

            with st.form("registration_form", enter_to_submit=False):
                col1, col2 = st.columns(2)

                with col1:
                    first_name = st.text_input("First Name")
                with col2:
                    last_name = st.text_input("Last Name")

                email = st.text_input("Email")
                phone_number = st.text_input("Phone Number")

                submitted = st.form_submit_button("Submit", use_container_width=True)

            if submitted:
                errors = validate_registration(first_name, last_name, email, phone_number)

                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    st.session_state.applicant_info = {
                        "first_name": first_name.strip(),
                        "last_name": last_name.strip(),
                        "email": email.strip(),
                        "phone_number": phone_number.strip(),
                    }

                    full_name = f"{first_name.strip()} {last_name.strip()}"

                    st.session_state.messages = [
                        {
                            "role": "assistant",
                            "content": (
                                f"Hello {full_name}, thank you for applying to the Python Developer position. "
                                "I can answer questions about the role and help with next steps in the process. "
                                "How can I help you today?"
                            ),
                        }
                    ]

                    st.session_state.registration_submitted = True
                    st.rerun()


def render_chat_screen(agents):
    left_col, right_col = st.columns([2.2, 1], gap="medium")

    with left_col:
        with st.container(border=True):
            st.subheader("Conversation")

            chat_area = st.container(height=420)
            with chat_area:
                for msg in st.session_state.messages:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

            if st.session_state.api_error:
                st.error(st.session_state.api_error)

        if st.session_state.end_session:
            st.info("This conversation has ended. To begin a new conversation, click Start Over.")
            user_input = None
        else:
            user_input = st.chat_input("Write your message here...")

        if user_input:
            st.session_state.api_error = ""
            st.session_state.messages.append({"role": "user", "content": user_input})

            try:
                with st.spinner("Thinking..."):
                    result = process_user_message(
                        agents=agents,
                        applicant_info=st.session_state.applicant_info,
                        chat_history=st.session_state.messages,
                        conversation_state=st.session_state.conversation_state,
                    )

                assistant_message = result["assistant_message"]
                updated_state = result["conversation_state"]
                end_session = result.get("end_session", False)

                st.session_state.messages.append(
                    {"role": "assistant", "content": assistant_message}
                )
                st.session_state.conversation_state = updated_state

                if end_session:
                    st.session_state.end_session = True
                    st.rerun()
                    return

            except Exception as e:
                st.session_state.api_error = f"API error: {str(e)}"

            st.rerun()

    with right_col:
        with st.container(border=True):
            st.subheader("Applicant Info")
            st.write(f"**First Name:** {st.session_state.applicant_info.get('first_name', '')}")
            st.write(f"**Last Name:** {st.session_state.applicant_info.get('last_name', '')}")
            st.write(f"**Email:** {st.session_state.applicant_info.get('email', '')}")
            st.write(f"**Phone Number:** {st.session_state.applicant_info.get('phone_number', '')}")

            st.divider()

            state_value = st.session_state.conversation_state.get("status", "new")
            last_action = st.session_state.conversation_state.get("last_action", "none")

            st.write("**Current State**")
            st.write(format_state(state_value))
            st.write("**Last Action**")
            st.write(last_action)

            if st.session_state.end_session:
                st.warning("Conversation ended")
            
            st.divider()

            if st.button("Start Over", use_container_width=True):
                reset_app()
                st.rerun()


def main():
    try:
        agents = bootstrap_app()
    except Exception as e:
        st.error(f"Startup error: {e}")
        st.stop()

    initialize_session_state()

    st.title("Recruitment Chatbot")

    if not st.session_state.registration_submitted:
        render_registration_screen()
    else:
        render_chat_screen(agents)


if __name__ == "__main__":
    main()