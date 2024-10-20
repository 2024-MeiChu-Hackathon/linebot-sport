import json
import logging
import os
import sys
from fastapi import APIRouter, HTTPException
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from firebase import firebase
from fastapi.staticfiles import StaticFiles
import firebase_admin
from utils import check_image, create_gcal_url, is_url_valid, shorten_url_by_reurl_api
import google.generativeai as genai
import bot_instruction
import uuid


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


from firebase_admin import db, credentials
creds_dict = json.loads(os.environ.get(
    ("GOOGLE_CREDENTIALS_FIREBASE")))
firebase_admin.initialize_app(
    credentials.Certificate(creds_dict), {'databaseURL': os.getenv("FIREBASE_URL")})


sports_sprites = {
    "basketball": "/static/img/basketball.png",
    "cycling": "/static/img/biking.png",
    "table tennis": "/static/img/tabletennis.png",
    "tennis": "/static/img/tennis.png",
    "volleyball": "/static/img/volleyball.png",
    "other": "/static/img/volleyball.png"
}

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

    # user_id: profile.userId,
    # user_name: name,
    # user_picture: profile.pictureUrl,
    # user_city: city,
    # user_district: district,
    # user_birthday: birthday,
    # user_gender: gender,
    # user_school: school,
    # user_department: department

    user_id = json["user_id"]
    user_name = json["user_name"]
    user_picture = json["user_picture"]
    user_city = json["user_city"]
    user_district = json["user_district"]
    user_birthday = json["user_birthday"]
    user_gender = json["user_gender"]
    user_school = json["user_school"]
    user_department = json["user_department"]

    user_profile_path = f"profile/{user_id}"
    fdb = firebase.FirebaseApplication(firebase_url, None)
    profile_data = fdb.get(user_profile_path, None)

    if profile_data is None:
        fdb.put_async(user_profile_path, None, {
            "id": user_id,
            "name": user_name,
            "picture": user_picture,
            "city": user_city,
            "district": user_district,
            "school": user_school,
            "birthday": user_birthday,
            "gender": user_gender,
            "department": user_department,
            "isfullyinitial": False
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
    user_now_path = f"profile/{user_id}"
    # chat_state_path = f'state/{user_id}'
    conversation_data = fdb.get(user_chat_path, None)
    profile_data = fdb.get(user_profile_path, None)

    if conversation_data is None:
        messages = []
    else:
        messages = conversation_data

    model = genai.GenerativeModel("gemini-1.5-pro")
    if profile_data is None or profile_data.get("isfullyinitial") == False:
        if profile_data is not None:
            model = genai.GenerativeModel(
                "gemini-1.5-pro", system_instruction=bot_instruction.create_profile(gusername=profile_data.get("name"), gbirthday=profile_data.get("birthday"), ggender=profile_data.get("gender"), gcity=profile_data.get("city"), gschool=profile_data.get("school"), gdepartment=profile_data.get("department")))
        else:
            model = genai.GenerativeModel(
                "gemini-1.5-pro", system_instruction=bot_instruction.ask_register())
    # print(model._system_instruction)
    else:
        if profile_data.get("status") == "adding_event":
            model = genai.GenerativeModel(
                "gemini-1.5-pro", system_instruction=bot_instruction.create_activity())
        else:
            model = genai.GenerativeModel(
                "gemini-1.5-pro", system_instruction=bot_instruction.generic_instruction(gusername=profile_data.get("name"), gbirthday=profile_data.get("birthday"), ggender=profile_data.get("gender"), gcity=profile_data.get("city"), gschool=profile_data.get("school"), gdepartment=profile_data.get("department"), gprefer_sport=profile_data.get("prefer_sport")))

    if text == "INITP" or text == "我要註冊":

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
              "text": "你好！",
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
    elif text == "PC":
        # 刪除Profile
        fdb.delete(user_profile_path, None)
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="個人資料已清除")],
                )
            )
    elif text == "探索活動":
        # search_path = f"events/by_event_type/"
        # dbresult["event_type"] = fdb.get(search_path, None)
        # search_path = f"events/by_time/"
        # dbresult["start_time"] = fdb.get(search_path, None)
        # search_path = f"events/by_location/"
        # dbresult["location"] = fdb.get(search_path, None)
        dbresult = db.reference("events").get()

        # for ikey, ivalue in dbresult.items():
        #     for jkey, jvalue in ivalue.items():
        #         # dbresultMessage += f"{jkey}: {jvalue}\n"
        #         for kkey, kvalue in jvalue.items():
        #             # dbresultMessage += f"{kkey}: {kvalue}\n"
        #             dbresultMessage += f"id: "
        #             for lkey, lvalue in kvalue.items():
        #                 dbresultMessage += f"{lvalue} "
        #             dbresultMessage += "\n"

        #             dbresultMessage += f"{kkey}: "
        #             for lkey, lvalue in kvalue.items():
        #                 dbresultMessage += f"{lvalue} "
        #             dbresultMessage += "\n"
        print(dbresult)
        print(profile_data)
        if dbresult is None:
            reply_msg = "找不到符合條件的活動"
            jsonReply = {}
            jsonReply["message"] = reply_msg
        else:
            profile_data = fdb.get(user_profile_path, None)
            print(profile_data)
            aai = bot_instruction.search_activity(gusername=profile_data.get("name"), gcity=profile_data.get("city"), gschool=profile_data.get(
                "school"), gdepartment=profile_data.get("department"), gprefer_sport=profile_data.get("prefer_sport"), jsonReply=dbresult, gbirthday=None, ggender=None)
            model = genai.GenerativeModel(
                "gemini-1.5-pro", system_instruction=aai)
            print(model._system_instruction)

            fdb.put_async(user_now_path, None, {
                "status": "searching_event"
            })
            messages.append({"role": "user", "parts": ""})

            response = model.generate_content(
                "Please search for suitable event from the events given according to user info.")
            messages.append(
                {"role": "model", "parts": [response.text]})
            fdb.put_async(user_chat_path, None, messages)
            reply_msg = response.text
            print(reply_msg)
            jsonReply = json.loads(reply_msg)

            if jsonReply["data"] == []:
                reply_msg = jsonReply["message"]
                with ApiClient(configuration) as api_client:
                    line_bot_api = MessagingApi(api_client)
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=reply_msg)],
                        )
                    )
                    return "OK"
            else:

                flexmessages = '''
{
  "type": "carousel",
  "contents": [
'''
                bubble_string = '''
{{
  "type": "bubble",
  "body": {{
    "type": "box",
    "layout": "vertical",
    "contents": [
      {{
        "type": "image",
        "url": "{sports_sprite}",
        "size": "full",
        "aspectMode": "cover",
        "aspectRatio": "4:3",
        "gravity": "bottom",
        "animated": true,
        "align": "start",
        "position": "relative"
      }},
      {{
        "type": "box",
        "layout": "vertical",
        "contents": [
          {{
            "type": "box",
            "layout": "baseline",
            "contents": [
              {{
                "type": "text",
                "size": "xl",
                "color": "#ffffff",
                "weight": "bold",
                "text": "{event_name}"
              }}
            ]
          }},
          {{
            "type": "box",
            "layout": "baseline",
            "contents": [
              {{
                "type": "icon",
                "url": "https://i.imgur.com/F0OlHBf.png",
                "size": "sm"
              }},
              {{
                "type": "text",
                "text": "{attendees}",
                "margin": "sm",
                "color": "#d1d1d1",
                "size": "xs",
                "align": "start",
                "gravity": "center",
                "position": "relative",
                "decoration": "none",
                "style": "italic",
                "weight": "regular"
              }}
            ]
          }},
          {{
            "type": "box",
            "layout": "vertical",
            "contents": [
              {{
                "type": "separator"
              }}
            ],
            "height": "5px",
            "spacing": "3px",
            "paddingBottom": "8px",
            "paddingTop": "8px"
          }},
          {{
            "type": "box",
            "layout": "baseline",
            "contents": [
              {{
                "type": "icon",
                "url": "https://i.imgur.com/GewaQDr.png",
                "position": "relative"
              }},
              {{
                "type": "text",
                "text": "{city}, {location}",
                "color": "#ffffff",
                "flex": 0,
                "size": "md"
              }}
            ],
            "spacing": "sm",
            "margin": "xs"
          }},
          {{
            "type": "box",
            "layout": "baseline",
            "contents": [
              {{
                "type": "icon",
                "url": "https://i.imgur.com/oFEvSQB.png",
                "position": "relative"
              }},
              {{
                "type": "text",
                "text": "{start_time}",
                "color": "#ffffff",
                "size": "md",
                "flex": 0
              }}
            ],
            "spacing": "sm",
            "margin": "sm"
          }},
          {{
            "type": "box",
            "layout": "vertical",
            "contents": [
              {{
                "type": "filler"
              }},
              {{
                "type": "box",
                "layout": "baseline",
                "contents": [
                  {{
                    "type": "filler"
                  }},
                  {{
                    "type": "icon",
                    "url": "https://i.imgur.com/aUHbs0h.png"
                  }},
                  {{
                    "type": "text",
                    "text": "參加活動",
                    "color": "#ffffff",
                    "flex": 0,
                    "offsetTop": "-2px"
                  }},
                  {{
                    "type": "filler"
                  }}
                ],
                "spacing": "sm"
              }},
              {{
                "type": "filler"
              }}
            ],
            "borderWidth": "1px",
            "cornerRadius": "4px",
            "spacing": "sm",
            "borderColor": "#ffffff",
            "margin": "xxl",
            "height": "40px"
          }}
        ],
        "offsetBottom": "0px",
        "offsetStart": "0px",
        "offsetEnd": "0px",
        "backgroundColor": "#1e81b0",
        "position": "absolute",
        "paddingAll": "30px"
      }},
      {{
        "type": "box",
        "layout": "vertical",
        "contents": [
          {{
            "type": "text",
            "text": "{city}{district}",
            "color": "#ffffff",
            "align": "center",
            "size": "xs",
            "offsetTop": "3px"
          }}
        ],
        "position": "absolute",
        "cornerRadius": "15px",
        "offsetTop": "18px",
        "backgroundColor": "#ff334b",
        "offsetStart": "18px",
        "height": "25px",
        "width": "110px",
        "background": {{
          "type": "linearGradient",
          "angle": "225deg",
          "startColor": "#f7ba2c",
          "endColor": "#ea5459"
        }}
      }}
    ],
    "paddingAll": "0px"
  }}
}},
                    '''

                for data in jsonReply['data']:
                    flexmessages += bubble_string.format(
                        sports_sprite=sports_sprites[data['event_type']],
                        event_name=data["event_name"],
                        attendees="成為第一個人參加吧！",
                        city=data["event_city"][0],
                        district=f", {data['event_city'][1]}" if len(
                            data["event_city"]) == 2 else "",
                        location=data["event_location"]
                    )

                flexmessages += '''
    ]
  }
                      '''

                print(flexmessages)

                with ApiClient(configuration) as api_client:
                    line_bot_api = MessagingApi(api_client)
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[flexmessages],
                        )
                    )
                    return "OK"
    elif text == "我已完成個人資料填寫，並同意共享個人化資料。":
        bubble_string = """
{{
  "type": "bubble",
  "size": "kilo",
  "body": {{
    "type": "box",
    "layout": "vertical",
    "contents": [
      {{
        "type": "text",
        "text": "恭喜您已註冊完畢！",
        "offsetEnd": "none",
        "offsetBottom": "md",
        "size": "sm",
        "weight": "bold",
        "color": "#aaaaaa"
      }},
      {{
        "type": "box",
        "layout": "horizontal",
        "contents": [
          {{
            "type": "box",
            "layout": "vertical",
            "contents": [
              {{
                "type": "image",
                "url": "{}",
                "aspectMode": "cover"
              }}
            ],
            "cornerRadius": "xl",
            "flex": 1
          }},
          {{
            "type": "box",
            "layout": "vertical",
            "contents": [],
            "flex": 2
          }}
        ]
      }},
      {{
        "type": "box",
        "layout": "vertical",
        "contents": [
          {{
            "type": "text",
            "text": "{}",
            "weight": "bold",
            "size": "xxl",
            "offsetTop": "sm"
          }},
          {{
            "type": "box",
            "layout": "vertical",
            "margin": "lg",
            "spacing": "sm",
            "contents": [
              {{
                "type": "box",
                "layout": "baseline",
                "spacing": "sm",
                "contents": [
                  {{
                    "type": "text",
                    "text": "縣市",
                    "color": "#aaaaaa",
                    "size": "sm",
                    "flex": 1
                  }},
                  {{
                    "type": "text",
                    "wrap": true,
                    "color": "#666666",
                    "size": "sm",
                    "flex": 5,
                    "text": "{}"
                  }}
                ]
              }},
              {{
                "type": "box",
                "layout": "baseline",
                "spacing": "sm",
                "contents": [
                  {{
                    "type": "text",
                    "text": "生日",
                    "color": "#aaaaaa",
                    "size": "sm",
                    "flex": 1
                  }},
                  {{
                    "type": "text",
                    "text": "{}",
                    "wrap": true,
                    "color": "#666666",
                    "size": "sm",
                    "flex": 5
                  }}
                ]
              }}
            ]
          }},
          {{
            "type": "box",
            "layout": "baseline",
            "spacing": "sm",
            "contents": [
              {{
                "type": "text",
                "text": "性別",
                "color": "#aaaaaa",
                "size": "sm",
                "flex": 1
              }},
              {{
                "type": "text",
                "wrap": true,
                "color": "#666666",
                "size": "sm",
                "flex": 5,
                "text": "{}"
              }}
            ]
          }},
          {{
            "type": "box",
            "layout": "baseline",
            "spacing": "sm",
            "contents": [
              {{
                "type": "text",
                "text": "學校",
                "color": "#aaaaaa",
                "size": "sm",
                "flex": 1
              }},
              {{
                "type": "text",
                "wrap": true,
                "color": "#666666",
                "size": "sm",
                "flex": 5,
                "text": "{}"
              }}
            ]
          }},
          {{
            "type": "box",
            "layout": "baseline",
            "spacing": "sm",
            "contents": [
              {{
                "type": "text",
                "text": "系級",
                "color": "#aaaaaa",
                "size": "sm",
                "flex": 1
              }},
              {{
                "type": "text",
                "wrap": true,
                "color": "#666666",
                "size": "sm",
                "flex": 5,
                "text": "{}"
              }}
            ]
          }}
        ]
      }}
    ]
  }},
  "footer": {{
    "type": "box",
    "layout": "vertical",
    "spacing": "sm",
    "contents": [
      {{
        "type": "button",
        "style": "link",
        "height": "sm",
        "action": {{
          "type": "message",
          "label": "完善我的資料！",
          "text": "完善我的資料"
        }}
      }},
      {{
        "type": "box",
        "layout": "vertical",
        "contents": [],
        "margin": "sm"
      }}
    ],
    "flex": 0
  }}
}}
""".format(
            profile_data["picture"],
            profile_data["name"],
            profile_data["city"],
            profile_data["birthday"],
            "男" if profile_data["gender"] == 0 else "女",
            profile_data["school"] if profile_data["school"] != None and profile_data["school"] != "" else "未提供",
            profile_data["department"] if profile_data["department"] != None and profile_data["department"] != "" else "未提供",
        )
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(
                        alt_text="完成建立個人資料！", contents=FlexBubble.from_json(bubble_string))],
                )
            )
            return "OK"

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
        print(reply_msg)

        jsonReply = json.loads(reply_msg)
        if jsonReply["op"] == "sys":
            if jsonReply["method"] == "create_profile":
                profile_data = dict({
                    "city": jsonReply["data"]["city"],
                    "location": jsonReply["data"]["location"],
                    "prefer_sport": jsonReply["data"]["prefer_sport"],
                    "prefer_weekdays": jsonReply["data"]["prefer_weekdays"],
                    "prefer_time": jsonReply["data"]["prefer_time"],
                    "reveal_info": jsonReply["data"]["reveal_info"],
                    "isfullyinitial": True
                }, **profile_data)
                fdb.put_async(user_profile_path, None, profile_data)

                fdb.delete(user_chat_path, None)

            elif jsonReply["method"] == "create_event":
                guuid = str(uuid.uuid4())

                fdb.put_async(f"events/by_event_type/{jsonReply['data']['event_type']}/{guuid}", None, {
                    "userID": user_id,
                    "name": jsonReply["data"]["event_name"],
                    "city": jsonReply["data"]["event_city"],
                    "location": jsonReply["data"]["event_location"],
                    "start_time": jsonReply["data"]["event_start_time"],
                    "end_time": jsonReply["data"]["event_end_time"],
                    "description": jsonReply["data"]["event_description"],
                    "amount": jsonReply["data"]["event_amount"],
                    "private": jsonReply["data"]["event_private"]
                })
                fdb.put_async(f"events/by_time/{jsonReply['data']['event_start_time']}/{guuid}", None, {
                    "userID": user_id,
                    "name": jsonReply["data"]["event_name"],
                    "city": jsonReply["data"]["event_city"],
                    "location": jsonReply["data"]["event_location"],
                    "start_time": jsonReply["data"]["event_start_time"],
                    "end_time": jsonReply["data"]["event_end_time"],
                    "description": jsonReply["data"]["event_description"],
                    "amount": jsonReply["data"]["event_amount"],
                    "private": jsonReply["data"]["event_private"]
                })
                fdb.put_async(f"events/by_location/{jsonReply['data']['event_location']}/{guuid}", None, {
                    "userID": user_id,
                    "name": jsonReply["data"]["event_name"],
                    "city": jsonReply["data"]["event_city"],
                    "location": jsonReply["data"]["event_location"],
                    "start_time": jsonReply["data"]["event_start_time"],
                    "end_time": jsonReply["data"]["event_end_time"],
                    "description": jsonReply["data"]["event_description"],
                    "amount": jsonReply["data"]["event_amount"],
                    "private": jsonReply["data"]["event_private"]
                })
                fdb.delete(user_now_path, None, {
                    "status": "adding_event"
                })

            elif jsonReply["method"] == "switch_prompt":
                if jsonReply["mode"] == "add_event":
                    model = genai.GenerativeModel(
                        "gemini-1.5-pro", system_instruction=bot_instruction.create_activity())
                    fdb.put_async(user_now_path, None, {
                        "status": "searching_event"
                    })
                    messages.append({"role": "user", "parts": ""})
                    response = model.generate_content(messages)
                    messages.append(
                        {"role": "model", "parts": [response.text]})
                    fdb.put_async(user_chat_path, None, messages)
                    reply_msg = response.text
                    print(reply_msg)

                    jsonReply = json.loads(reply_msg)
                elif jsonReply["mode"] == "search_event":
                    print(profile_data)
                    print(3)
                    model = genai.GenerativeModel(
                        "gemini-1.5-pro", system_instruction=bot_instruction.search_activity(gusername=profile_data.get("name"), gcity=profile_data.get("city"), gschool=profile_data.get("school"), gdepartment=profile_data.get("department"), gprefer_sport=profile_data.get("prefer_sport")))
                    fdb.put_async(user_now_path, None, {
                        "status": "searching_event"
                    })
                    messages.append({"role": "user", "parts": ""})
                    response = model.generate_content(messages)
                    messages.append(
                        {"role": "model", "parts": [response.text]})
                    fdb.put_async(user_chat_path, None, messages)
                    reply_msg = response.text
                    print(reply_msg)

                    jsonReply = json.loads(reply_msg)
                    if jsonReply["op"] == "ask":
                        reply_msg = jsonReply["message"]
                elif jsonReply["mode"] == "generic":
                    model = genai.GenerativeModel(
                        "gemini-1.5-pro", system_instruction=bot_instruction.generic_instruction(gusername=profile_data.get("name"), gbirthday=profile_data.get("birthday"), ggender=profile_data))
                    fdb.delete_async(user_now_path, None, {
                        "status": "searching_event"
                    })
                    messages.append({"role": "user", "parts": ""})
                    response = model.generate_content(messages)
                    messages.append(
                        {"role": "model", "parts": [response.text]})
                    fdb.put_async(user_chat_path, None, messages)
                    reply_msg = response.text
                    print(reply_msg)

            print(model._system_instruction)

            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=jsonReply['message'])],
                    )
                )
                return "OK"
        elif jsonReply["op"] == "yn":
            reply_msg = jsonReply["message"]
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
        "contents": [
          {
            "type": "image",
            "url": "https://cdn-icons-png.flaticon.com/512/12510/12510970.png",
            "align": "center",
            "gravity": "center"
          }
        ],
        "offsetBottom": "6px",
        "offsetTop": "6px"
      },
      {
        "type": "box",
        "layout": "vertical",
        "contents": [
          {
            "type": "text",
            "text": "請使用下方按鈕來回答此問題",
            "size": "lg",
            "weight": "bold",
            "position": "relative",
            "align": "center"
          }
        ],
        "offsetTop": "18px"
      }
    ],
    "position": "relative",
    "alignItems": "center",
    "justifyContent": "center",
    "height": "190px"
  },
  "footer": {
    "type": "box",
    "layout": "horizontal",
    "spacing": "xs",
    "contents": [
      {
        "type": "button",
        "style": "link",
        "height": "sm",
        "action": {
          "type": "message",
          "text": "是",
          "label": "我接受"
        }
      },
      {
        "type": "button",
        "style": "link",
        "height": "sm",
        "action": {
          "type": "message",
          "label": "不接受",
          "text": "否"
        }
      }
    ],
    "flex": 0
  }
}
        """
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[
                            TextMessage(text=reply_msg),
                            FlexMessage(
                                alt_text="同意/不同意", contents=FlexBubble.from_json(bubble_string))
                        ]
                    )
                )
                return "OK"
        elif jsonReply["op"] == "ask":
            reply_msg = jsonReply["message"]
        elif jsonReply["op"] == "talk":
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
