# app/modules/orchestration/routing.py


"""
Intent Routing Logic.

Contains functions for detecting user intent from chat history,
including:
- Scheduling intent
- Information request
- Mixed intent (schedule + info)

Used by the Main Agent to decide which advisors to invoke.
"""