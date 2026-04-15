# app/modules/scheduling/langchain_tools.py

"""
LangChain tool wrappers for scheduling operations.

Wraps scheduling database functions as LangChain tools so the
Scheduling Advisor can use function calling.
"""

from langchain.tools import tool

from app.modules.scheduling.schedule_db import (
    get_nearest_slots,
    get_available_slots_in_range,
    validate_slot,
    book_slot,
)


@tool
def get_nearest_slots_tool(start_date: str, position: str = "Python Dev", limit: int = 3):
    """
    Return the nearest available interview slots on or after the given start date.
    """
    return get_nearest_slots(
        start_date=start_date,
        position=position,
        limit=limit,
    )


@tool
def get_available_slots_in_range_tool(
    start_date: str,
    end_date: str,
    position: str = "Python Dev",
    limit: int = 3
):
    """
    Return available interview slots within a date range.
    """
    return get_available_slots_in_range(
        start_date=start_date,
        end_date=end_date,
        position=position,
        limit=limit,
    )


@tool
def validate_slot_tool(date: str, time: str, position: str = "Python Dev"):
    """
    Check whether a specific interview slot is available.
    """
    return validate_slot(
        date=date,
        time=time,
        position=position,
    )


@tool
def book_slot_tool(date: str, time: str, position: str = "Python Dev"):
    """
    Book an interview slot by marking it unavailable.
    """
    return book_slot(
        date=date,
        time=time,
        position=position,
    )


LANGCHAIN_SCHEDULE_TOOLS = [
    get_nearest_slots_tool,
    get_available_slots_in_range_tool,
    validate_slot_tool,
    book_slot_tool,
]