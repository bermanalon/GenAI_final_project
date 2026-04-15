# app/modules/logging/conversation_logger.py

"""
Conversation Logger.

Responsible for logging conversations in JSON format.

Stores:
- Candidate information
- Full conversation history (turns)
- Assistant decisions (CONTINUE / SCHEDULE / END)
- Metadata for debugging and evaluation

Used for auditing and dataset generation for evaluation.
"""