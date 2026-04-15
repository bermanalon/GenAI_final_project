# app/modules/scheduling/schedule_db.py

"""
Scheduling Database Access Layer.

Provides low-level functions for interacting with the SQL Server database,
including:
- Retrieving available interview slots
- Validating a specific slot
- Booking a slot

All database queries are implemented here.
"""

import pyodbc


SERVER = "ALONBOOK"
DATABASE = "Tech"
DRIVER = "ODBC Driver 17 for SQL Server"
DEFAULT_POSITION = "Python Dev"


def get_connection():
    conn_str = (
        f"DRIVER={{{DRIVER}}};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        "Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)


def row_to_slot_dict(row):
    return {
        "ScheduleID": row.ScheduleID,
        "date": str(row.date),
        "time": str(row.time),
        "position": row.position,
    }


def get_nearest_slots(start_date, position=DEFAULT_POSITION, limit=3):
    """
    Return the nearest available interview slots on or after start_date.

    Args:
        start_date: string in format YYYY-MM-DD
        position: job title, default is 'Python Dev'
        limit: maximum number of slots to return

    Returns:
        List of dictionaries representing available slots.
    """
    query = """
        SELECT TOP (?)
            ScheduleID,
            [date],
            [time],
            position
        FROM dbo.Schedule
        WHERE [date] >= ?
          AND LOWER(position) = LOWER(?)
          AND available = 1
        ORDER BY [date], [time]
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(query, (limit, start_date, position))
    rows = cursor.fetchall()

    results = []
    for row in rows:
        results.append(row_to_slot_dict(row))

    cursor.close()
    conn.close()

    return results


def get_available_slots_in_range(start_date, end_date, position=DEFAULT_POSITION, limit=3):
    """
    Return available interview slots within a date range.

    Args:
        start_date: string in format YYYY-MM-DD
        end_date: string in format YYYY-MM-DD
        position: job title
        limit: maximum number of slots to return

    Returns:
        List of dictionaries representing available slots.
    """
    query = """
        SELECT TOP (?)
            ScheduleID,
            [date],
            [time],
            position
        FROM dbo.Schedule
        WHERE [date] >= ?
          AND [date] <= ?
          AND LOWER(position) = LOWER(?)
          AND available = 1
        ORDER BY [date], [time]
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(query, (limit, start_date, end_date, position))
    rows = cursor.fetchall()

    results = []
    for row in rows:
        results.append(row_to_slot_dict(row))

    cursor.close()
    conn.close()

    return results


def validate_slot(date, time, position=DEFAULT_POSITION):
    """
    Check whether a specific slot is available.

    Args:
        date: string in format YYYY-MM-DD
        time: string in format HH:MM:SS
        position: job title

    Returns:
        True if the slot is available, otherwise False.
    """
    query = """
        SELECT TOP (1) available
        FROM dbo.Schedule
        WHERE [date] = ?
          AND [time] = ?
          AND LOWER(position) = LOWER(?)
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(query, (date, time, position))
    row = cursor.fetchone()

    cursor.close()
    conn.close()

    if row is None:
        return False

    return row.available == 1


def book_slot(date, time, position=DEFAULT_POSITION):
    """
    Book a slot by setting available = 0.

    Args:
        date: string in format YYYY-MM-DD
        time: string in format HH:MM:SS
        position: job title

    Returns:
        True if one slot was updated, otherwise False.
    """
    query = """
        UPDATE dbo.Schedule
        SET available = 0
        WHERE [date] = ?
          AND [time] = ?
          AND LOWER(position) = LOWER(?)
          AND available = 1
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(query, (date, time, position))
    affected = cursor.rowcount
    conn.commit()

    cursor.close()
    conn.close()

    return affected == 1


if __name__ == "__main__":
    print("Nearest slots:")
    slots = get_nearest_slots("2026-03-27")

    for slot in slots:
        print(slot)

    print("\nSlots in range:")
    range_slots = get_available_slots_in_range("2026-03-27", "2026-04-05")

    for slot in range_slots:
        print(slot)

    print("\nValidate slot example:")
    print(validate_slot("2026-03-27", "09:00:00"))