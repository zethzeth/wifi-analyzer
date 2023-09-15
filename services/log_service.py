def add_analysis_record():
    conn = 
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO logs (event_type, result) VALUES (?, ?)",
        (
            event,
            status,
        ),
    )
    conn.commit()
    conn.close()