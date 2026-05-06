from app.database import get_connection

def get_summary():
    conn = get_connection()
    row = conn.execute("""
        SELECT
            COUNT(*)                        AS total_requests,
            ROUND(AVG(latency_ms), 2)       AS avg_latency_ms,
            ROUND(SUM(estimated_cost), 6)   AS total_cost,
            SUM(total_tokens)               AS total_tokens
        FROM request_logs
        WHERE status = 'success'
    """).fetchone()

    top_model = conn.execute("""
        SELECT model, COUNT(*) AS cnt
        FROM request_logs
        WHERE status = 'success'
        GROUP BY model
        ORDER BY cnt DESC
        LIMIT 1
    """).fetchone()

    conn.close()
    return {
        "total_requests":  row["total_requests"],
        "avg_latency_ms":  row["avg_latency_ms"],
        "total_cost_usd":  row["total_cost"],
        "total_tokens":    row["total_tokens"],
        "top_model":       top_model["model"] if top_model else None,
    }


def get_latency_stats():
    conn = get_connection()
    rows = conn.execute("""
        SELECT latency_ms
        FROM request_logs
        WHERE status = 'success'
        ORDER BY latency_ms
    """).fetchall()
    conn.close()

    if not rows:
        return {"p50": 0, "p95": 0, "min": 0, "max": 0}

    values = [r["latency_ms"] for r in rows]
    n = len(values)

    def percentile(data, p):
        idx = max(0, int(len(data) * p / 100) - 1)
        return data[idx]

    return {
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "min": round(values[0], 2),
        "max": round(values[-1], 2),
        "count": n,
    }


def get_cost_over_time():
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            DATE(timestamp)             AS day,
            ROUND(SUM(estimated_cost), 6) AS daily_cost,
            COUNT(*)                    AS requests
        FROM request_logs
        WHERE status = 'success'
        GROUP BY DATE(timestamp)
        ORDER BY day ASC
    """).fetchall()
    conn.close()

    return [
        {"day": r["day"], "cost": r["daily_cost"], "requests": r["requests"]}
        for r in rows
    ]