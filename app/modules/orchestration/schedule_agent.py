# app/modules/orchestration/schedule_agent.py

"""
Scheduling Advisor.

Handles all interview scheduling logic, including:
- Detecting scheduling-related intent
- Interpreting natural language time expressions
- Calling scheduling tools (SQL database)
- Proposing, validating, and confirming interview slots

Returns structured scheduling actions and response text.
"""