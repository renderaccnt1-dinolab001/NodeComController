from fastapi import APIRouter
from discord_webhook import DiscordWebhook
from app.core.config import settings

router = APIRouter()

@router.get("/ping")
def pingDiscord():
    webhook_url = settings.DISCORD_OAuth2_MANNUAL_LOGIN_WEBHOOK_URL
    if not webhook_url:
        return {"status": 500, "detail": "Webhook URL not set"}
        
    webhook = DiscordWebhook(
        url=webhook_url, 
        content="hello world from NodeCom controller!",
        rate_limit_retry=True
    )
    return {"status": webhook.execute().status_code}
