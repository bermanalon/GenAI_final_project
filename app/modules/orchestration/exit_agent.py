# app/modules/orchestration/exit_agent.py

"""
Exit Advisor.

Determines whether the conversation should be ended based on the
candidate's intent (e.g., disinterest, request to stop).

Returns a boolean decision and a polite closing message if needed.
Designed to minimize unnecessary or unwanted follow-ups.
"""