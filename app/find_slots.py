import pyodbc


def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=ALONBOOK;"
        "DATABASE=Tech;"
        "Trusted_Connection=yes;"
    )



def get_nearest_available_slots(start_date, job_title, limit=3):

    query = """
        SELECT TOP (?) 
            ScheduleID,
            [date],
            [time],
            position,
            CAST([date] AS DATETIME) + CAST([time] AS DATETIME) AS slot_datetime
        FROM dbo.Schedule
        WHERE [date] >= ?
          AND LOWER(position) = LOWER(?)
          AND available = 1
        ORDER BY slot_datetime
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(query, (limit, start_date, job_title))
    rows = cursor.fetchall()

    results = []
    for row in rows:
        results.append({
            "ScheduleID": row.ScheduleID,
            "date": str(row.date),
            "time": str(row.time),
            "position": row.position
        })

    cursor.close()
    conn.close()

    return results

slots = get_nearest_available_slots("2026-03-27", "Python Dev")

for s in slots:
    print(s)