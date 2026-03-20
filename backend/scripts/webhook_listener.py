import uvicorn
from fastapi import FastAPI, Request, HTTPException
import json
import os
import sys

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.config import settings

app = FastAPI()


@app.get("/webhooks/whatsapp")
async def verify(request: Request):
    """Handle Meta's verification challenge."""
    params = request.query_params
    challenge = params.get("hub.challenge")
    verify_token = params.get("hub.verify_token")

    # You can set WHATSAPP_APP_SECRET in .env to use as verify_token
    expected_token = settings.whatsapp_app_secret or "luka_test_token"

    print("\n--- Verification Attempt ---")
    print(f"Token received: {verify_token}")
    print(f"Token expected: {expected_token}")

    if verify_token == expected_token:
        print("Verification SUCCESS!")
        return int(challenge)

    print("Verification FAILED!")
    raise HTTPException(status_code=403, detail="Invalid verify token")


@app.post("/webhooks/whatsapp")
async def webhook(request: Request):
    """Print incoming webhook JSON."""
    body = await request.body()
    try:
        data = json.loads(body)
        print("\n--- INCOMING WEBHOOK ---")
        print(json.dumps(data, indent=2))

        # We don't verify signature here for simplicity in local testing,
        # but you can add it if you have WHATSAPP_APP_SECRET set.

        return {"status": "ok"}
    except Exception as e:
        print(f"Error parsing webhook: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    print("\nStarting Local Webhook Server on port 8000...")
    print("Use 'ngrok http 8000' to expose this server to the internet.")
    uvicorn.run(app, host="0.0.0.0", port=8000)
