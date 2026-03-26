import os
import sys
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st
from app.main import bootstrap_app, create_initial_session_state
from app.modules.chat import get_chatgpt_response

st.markdown("""
<style>
.block-container {
    padding-top: 1.8rem;
    padding-bottom: 0.5rem;
    margin-top: 0;
    margin-bottom: 0.2rem
}
</style>
""", unsafe_allow_html=True)

st.set_page_config(
    page_title="Recruitment Chatbot",
    page_icon="💼",
    layout="wide"
)


def initialize_session_state():
    defaults = create_initial_session_state()
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if "registration_ready_for_chat" not in st.session_state:
        st.session_state.registration_ready_for_chat = False            
    
def reset_app():
    defaults = create_initial_session_state()
    st.session_state.clear()
    for key, value in defaults.items():
        st.session_state[key] = value


def validate_registration(first_name: str, last_name: str, email: str, phone_number: str) -> list[str]:
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


try:
    client = bootstrap_app()
except Exception as e:
    st.error(f"Startup error: {e}")
    st.stop()

initialize_session_state()

# -----------------------------
# Fixed header
# -----------------------------
st.markdown("### Recruitment Chatbot")

# -----------------------------
# Registration screen
# -----------------------------
if not st.session_state.registration_submitted:
    left_spacer, center_col, right_spacer = st.columns([1, 1.6, 1])

    with center_col:
        with st.container(border=True):
            st.subheader("Registration Form")
            st.write("Please fill in your details and click submit.")

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
                                f"Hello {full_name}, thank you for registering. "
                                "I can provide information about the position and help schedule a meeting "
                                "with a recruiter. How can I help you today?"
                            )
                        }
                    ]

                    st.session_state.registration_ready_for_chat = True
                    st.rerun()
            if st.session_state.registration_ready_for_chat:
                st.success("Registration completed successfully.")

                if st.button("Continue to Chat with the Recruitment Bot", use_container_width=True):
                    st.session_state.registration_submitted = True
                    st.session_state.registration_ready_for_chat = False
                    st.rerun()
# -----------------------------
# Chat screen
# -----------------------------
else:
        
    left_col, right_col = st.columns([2.2, 1], gap="medium")

    with left_col:
        with st.container(border=True):
            st.subheader("Conversation")

            # Smaller dedicated chat area so chat_input stays visible
            chat_area = st.container(height=320)

            with chat_area:
                for msg in st.session_state.messages:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

            if st.session_state.api_error:
                st.error(st.session_state.api_error)

        user_input = st.chat_input("Write your message here...")

        if user_input:
            st.session_state.api_error = ""
            st.session_state.messages.append(
                {"role": "user", "content": user_input}
            )

            try:
                with st.spinner("Thinking..."):
                    assistant_reply = get_chatgpt_response(
                        client=client,
                        applicant_info=st.session_state.applicant_info,
                        chat_history=st.session_state.messages,
                    )

                st.session_state.messages.append(
                    {"role": "assistant", "content": assistant_reply}
                )

            except Exception as e:
                st.session_state.api_error = f"API error: {str(e)}"

            st.rerun()

    with right_col:
        with st.container(border=True):
            st.subheader("Applicant Info")
            st.write(f"**First Name:** {st.session_state.applicant_info['first_name']}")
            st.write(f"**Last Name:** {st.session_state.applicant_info['last_name']}")
            st.write(f"**Email:** {st.session_state.applicant_info['email']}")
            st.write(f"**Phone Number:** {st.session_state.applicant_info['phone_number']}")

            st.divider()

            if st.button("Start Over", use_container_width=True):
                reset_app()
                st.rerun()