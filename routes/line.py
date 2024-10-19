import json
import logging
import os
import sys
from fastapi import APIRouter, HTTPException
from fastapi import FastAPI, Request
from firebase import firebase
from fastapi.staticfiles import StaticFiles
from utils import check_image, create_gcal_url, is_url_valid, shorten_url_by_reurl_api
import google.generativeai as genai

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ReplyMessageRequest,
    TextMessage,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    FlexButton
)
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent

logger = logging.getLogger(__file__)


channel_secret = os.getenv("LINE_CHANNEL_SECRET", None)
channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", None)
if channel_secret is None:
    print("Specify LINE_CHANNEL_SECRET as environment variable.")
    sys.exit(1)
if channel_access_token is None:
    print("Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.")
    sys.exit(1)

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)


router_line = APIRouter(prefix='/line', tags=['line'])
router_line.mount("/static", StaticFiles(directory="static"), name="static")

firebase_url = os.getenv("FIREBASE_URL")

gemini_key = os.getenv("GEMINI_API_KEY")
# Initialize the Gemini Pro API
genai.configure(api_key=gemini_key)


@router_line.post("/webhooks")
async def handle_callback(request: Request):
    signature = request.headers["X-Line-Signature"]

    # get request body as text
    body = await request.body()
    body = body.decode()

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")


@router_line.get("/liff")
async def handle_liff(request: Request):
    data = await request.json()
    user_id = data["userId"]
    text = data["text"]

    fdb = firebase.FirebaseApplication(firebase_url, None)
    return "Hello " + user_id


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    logging.info(event)
    text = event.message.text
    user_id = event.source.user_id

    fdb = firebase.FirebaseApplication(firebase_url, None)

    user_chat_path = f"chat/{user_id}"
    # chat_state_path = f'state/{user_id}'
    conversation_data = fdb.get(user_chat_path, None)
    model = genai.GenerativeModel("gemini-1.5-pro")

    if conversation_data is None:
        messages = []
    else:
        messages = conversation_data

    if text == "C":
        fdb.delete(user_chat_path, None)
        reply_msg = "已清空對話紀錄"
    elif is_url_valid(text):
        image_data = check_image(text)
        image_data = json.loads(image_data)
        g_url = create_gcal_url(
            image_data["title"],
            image_data["time"],
            image_data["location"],
            image_data["content"],
        )
        reply_msg = shorten_url_by_reurl_api(g_url)
    elif text == "A":
        response = model.generate_content(
            f"Summary the following message in Traditional Chinese by less 5 list points. \n{messages}"
        )
        reply_msg = response.text
    elif text == "我的頁面":
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(

        )
    else:
        messages.append({"role": "user", "parts": [text]})
        response = model.generate_content(messages)
        messages.append({"role": "model", "parts": [text]})
        # 更新firebase中的對話紀錄
        fdb.put_async(user_chat_path, None, messages)
        reply_msg = response.text

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_msg)],
            )
        )

    return "OK"


@handler.add(MessageEvent, message=ImageMessageContent)
def handle_github_message(event):
    image_content = b""
    with ApiClient(configuration) as api_client:
        line_bot_blob_api = MessagingApiBlob(api_client)
        image_content = line_bot_blob_api.get_message_content(event.message.id)
    image_data = check_image(b_image=image_content)
    image_data = json.loads(image_data)
    logger.info("---- Image handler JSON ----")
    logger.info(image_data)
    g_url = create_gcal_url(
        image_data["title"],
        image_data["time"],
        image_data["location"],
        image_data["content"],
    )
    reply_msg = shorten_url_by_reurl_api(g_url)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                replyToken=event.reply_token, messages=[
                    TextMessage(text=reply_msg)]
            )
        )
    return "OK"
