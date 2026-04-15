# app/modules/scheduling/schedule_tools.py

"""
Scheduling Tools Layer.

Defines tool schemas and execution logic for scheduling-related operations.
Acts as an interface between the Scheduling Advisor and the database layer.

Supports function calling for:
- Getting available slots
- Validating slots
- Booking slots
"""

from app.modules.scheduling.schedule_db import (
    get_nearest_slots,
    get_available_slots_in_range,
    validate_slot,
    book_slot,
)


SCHEDULE_TOOLS = [
    {
        "name": "get_nearest_slots",
        "description": "Get the nearest available interview slots from a given start date for a job position.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format"
                },
                "position": {
                    "type": "string",
                    "description": "Job title, for example Python Dev"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of slots to return"
                }
            },
            "required": ["start_date"]
        }
    },
    {
        "name": "get_available_slots_in_range",
        "description": "Get available interview slots in a date range for a job position.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format"
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format"
                },
                "position": {
                    "type": "string",
                    "description": "Job title, for example Python Dev"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of slots to return"
                }
            },
            "required": ["start_date", "end_date"]
        }
    },
    {
        "name": "validate_slot",
        "description": "Check whether a specific interview slot is still available.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format"
                },
                "time": {
                    "type": "string",
                    "description": "Time in HH:MM:SS format"
                },
                "position": {
                    "type": "string",
                    "description": "Job title, for example Python Dev"
                }
            },
            "required": ["date", "time"]
        }
    },
    {
        "name": "book_slot",
        "description": "Book an interview slot by marking it unavailable.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format"
                },
                "time": {
                    "type": "string",
                    "description": "Time in HH:MM:SS format"
                },
                "position": {
                    "type": "string",
                    "description": "Job title, for example Python Dev"
                }
            },
            "required": ["date", "time"]
        }
    }
]


def execute_schedule_tool(tool_name, args):
    """
    Execute one scheduling tool call.

    Args:
        tool_name: name of the tool to run
        args: dictionary of arguments

    Returns:
        Dictionary with the tool result
    """

    if tool_name == "get_nearest_slots":
        start_date = args["start_date"]
        position = args.get("position", "Python Dev")
        limit = args.get("limit", 3)

        slots = get_nearest_slots(
            start_date=start_date,
            position=position,
            limit=limit
        )

        return {
            "success": True,
            "tool_name": tool_name,
            "slots": slots
        }

    elif tool_name == "get_available_slots_in_range":
        start_date = args["start_date"]
        end_date = args["end_date"]
        position = args.get("position", "Python Dev")
        limit = args.get("limit", 3)

        slots = get_available_slots_in_range(
            start_date=start_date,
            end_date=end_date,
            position=position,
            limit=limit
        )

        return {
            "success": True,
            "tool_name": tool_name,
            "slots": slots
        }

    elif tool_name == "validate_slot":
        date = args["date"]
        time = args["time"]
        position = args.get("position", "Python Dev")

        available = validate_slot(
            date=date,
            time=time,
            position=position
        )

        return {
            "success": True,
            "tool_name": tool_name,
            "available": available
        }

    elif tool_name == "book_slot":
        date = args["date"]
        time = args["time"]
        position = args.get("position", "Python Dev")

        booked = book_slot(
            date=date,
            time=time,
            position=position
        )

        return {
            "success": booked,
            "tool_name": tool_name,
            "booked": booked
        }

    else:
        return {
            "success": False,
            "tool_name": tool_name,
            "error": f"Unknown tool: {tool_name}"
        }


if __name__ == "__main__":
    print("Available schedule tools:")
    for tool in SCHEDULE_TOOLS:
        print("-", tool["name"])

    print("\nTest get_nearest_slots:")
    result = execute_schedule_tool(
        "get_nearest_slots",
        {
            "start_date": "2026-03-27",
            "position": "Python Dev",
            "limit": 3
        }
    )
    print(result)

    print("\nTest validate_slot:")
    result = execute_schedule_tool(
        "validate_slot",
        {
            "date": "2026-03-27",
            "time": "09:00:00",
            "position": "Python Dev"
        }
    )
    print(result)