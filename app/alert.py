import httpx
import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from app.database import get_connection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

def get_config():
    """Always fetch fresh config from environment"""
    return {
        "THRESHOLD": float(os.getenv("SPEND_ALERT_THRESHOLD", "0.001")),
        "WEBHOOK_URL": os.getenv("WEBHOOK_URL", ""),
    }

def get_todays_spend() -> float:
    today = datetime.now(timezone.utc).date().isoformat()
    conn  = get_connection()
    try:
        row = conn.execute("""
            SELECT ROUND(SUM(estimated_cost), 6) AS spend
            FROM request_logs
            WHERE status = 'success'
              AND DATE(timestamp) = ?
        """, (today,)).fetchone()
        return row["spend"] or 0.0
    finally:
        conn.close()

async def check_and_alert():
    config = get_config()
    spend = get_todays_spend()
    
    threshold = config["THRESHOLD"]
    webhook_url = config["WEBHOOK_URL"]

    if spend < threshold:
        return

    if not webhook_url:
        logger.warning(f"Spend ${spend:.6f} exceeds threshold ${threshold:.6f} but no WEBHOOK_URL is set.")
        return

    # To avoid spamming, we could implement a check here to only alert once.
    # For now, let's just make sure the alert itself works reliably.
    
    payload = {
        "alert": "daily_spend_exceeded",
        "spend_usd": spend,
        "threshold": threshold,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": f"⚠️ Daily spend limit exceeded: ${spend:.6f} / ${threshold:.6f}"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
            logger.info(f"Alert sent successfully: ${spend:.6f} spend")
    except Exception as e:
        logger.error(f"Failed to send alert to webhook: {e}")