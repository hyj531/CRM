import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

DINGTALK_WEBHOOK = settings.DINGTALK.get('WEBHOOK')


def send_dingtalk_todo(user, title, content, url=None):
    if not DINGTALK_WEBHOOK:
        logger.info('DingTalk webhook not configured; skip sending: %s', title)
        return False

    payload = {
        "msgtype": "text",
        "text": {
            "content": f"{title}\n{content}\n{url or ''}".strip()
        },
    }

    try:
        response = requests.post(DINGTALK_WEBHOOK, json=payload, timeout=5)
        response.raise_for_status()
        return True
    except Exception as exc:
        logger.warning('Failed to send DingTalk message: %s', exc)
        return False
