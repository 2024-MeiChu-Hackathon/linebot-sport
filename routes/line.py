import json
import logging
import os
import sys
from fastapi import APIRouter, HTTPException
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from firebase import firebase
from fastapi.staticfiles import StaticFiles
from utils import check_image, create_gcal_url, is_url_valid, shorten_url_by_reurl_api
import google.generativeai as genai
import bot_instruction

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,

    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    FlexButton,
    FlexBubble,
    FlexBox,
    URIAction
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


@router_line.post("/create_profile")
async def create_profile(request: Request):
    # request ajax
    json = await request.json()
    user_id = json["user_id"]
    user_name = json["user_name"]
    user_picture = json["user_picture"]

    user_profile_path = f"profile/{user_id}"
    fdb = firebase.FirebaseApplication(firebase_url, None)
    profile_data = fdb.get(user_profile_path, None)

    if profile_data is None:
        fdb.put_async(user_profile_path, None, {
            "id": user_id,
            "name": user_name,
            "pirture": user_picture
        })
    return {"status": "success"}


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    logging.info(event)
    text = event.message.text
    user_id = event.source.user_id

    fdb = firebase.FirebaseApplication(firebase_url, None)

    user_chat_path = f"chat/{user_id}"
    user_profile_path = f"profile/{user_id}"
    # chat_state_path = f'state/{user_id}'
    conversation_data = fdb.get(user_chat_path, None)
    profile_data = fdb.get(user_profile_path, None)

    if conversation_data is None:
        messages = []
    else:
        messages = conversation_data

    model = genai.GenerativeModel(
        "gemini-1.5-pro", system_instruction=bot_instruction.create_profile(profile_data["name"]))
    # print(model._system_instruction)

    if text == "INITP":

        bubble_string = """
        {
    "type": "bubble",
    "body": {
      "type": "box",
      "layout": "vertical",
      "contents": [
        {
          "type": "box",
          "layout": "vertical",
          "margin": "sm",
          "spacing": "sm",
          "contents": [
            {
              "type": "image",
              "url": "https://i.imgur.com/1jpvBhC.png",
              "size": "4xl"
            }
          ]
        },
        {
          "type": "box",
          "layout": "vertical",
          "contents": [
            {
              "type": "text",
              "text": "你好",
              "size": "xl",
              "style": "normal",
              "weight": "bold",
              "align": "center"
            }
          ],
          "position": "relative"
        },
        {
          "type": "box",
          "layout": "vertical",
          "contents": [
            {
              "type": "text",
              "text": "歡迎使用「大家來運動」活動平台！",
              "align": "center"
            }
          ],
          "paddingTop": "5px"
        },
        {
          "type": "box",
          "layout": "vertical",
          "contents": [
            {
              "type": "separator",
              "margin": "lg"
            }
          ],
          "height": "15px",
          "position": "relative",
          "paddingBottom": "xxl"
        },
        {
          "type": "box",
          "layout": "vertical",
          "contents": [
            {
              "type": "button",
              "action": {
                "type": "uri",
                "label": "建立個人檔案",
                "uri": "https://liff.line.me/2006474745-ObYjRxE8"
              },
              "style": "secondary"
            }
          ]
        }
      ]
    }
  }
        """
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        FlexMessage(
                            alt_text="建立個人資料", contents=FlexBubble.from_json(bubble_string))
                    ]
                )
            )

    elif text == "C":
        fdb.delete(user_chat_path, None)
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="對話已清除")],
                )
            )
    elif text == "我的頁面":
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            # reply a button template
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        FlexMessage(alt_text="hello", contents=FlexBubble(
                            body=FlexBox(
                                layout='vertical',
                                contents=[

                                    FlexButton(
                                        style='link',
                                        height='sm',
                                        action=URIAction(
                                            label='我的頁面', uri="https://liff.line.me/2006474745-g2rn5ZE4")
                                    )
                                ])
                        )
                        )

                    ]
                )
            )
    # elif text == "認識我":

    elif text == "A":
        response = model.generate_content(
            f"Summary the following message in Traditional Chinese by less 5 list points. \n{messages}"
        )
        reply_msg = response.text
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_msg)],
                )
            )

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
    else:
        messages.append({"role": "user", "parts": [text]})
        response = model.generate_content(messages)
        messages.append({"role": "model", "parts": [response.text]})
        # 更新firebase中的對話紀錄
        # print(messages)
        fdb.put_async(user_chat_path, None, messages)
        reply_msg = response.text
        jsonReply = json.loads(reply_msg)
        print(jsonReply)
        if jsonReply["op"] == "sys":
            fdb.put_async(user_chat_path, None, [])
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=jsonReply['message'])],
                    )
                )
                return "OK"
        elif jsonReply["op"] == "ask":
            reply_msg = jsonReply["message"]

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_msg)],
                )
            )


@ handler.add(MessageEvent, message=ImageMessageContent)
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
