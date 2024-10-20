from firebase_admin import credentials
import firebase_admin
import json
import routes
import logging
import os

if os.getenv("API_ENV") != "production":
    from dotenv import load_dotenv

    load_dotenv()


from fastapi import FastAPI, HTTPException, Request
import uvicorn
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=os.getenv("LOG", "WARNING"))
logger = logging.getLogger(__file__)


app = FastAPI()
app.include_router(routes.router_web)
app.include_router(routes.router_line)
app.include_router(routes.router_liff)

app.mount("/static", StaticFiles(directory="static"), name="static")

# service_account_info = json.loads(os.getenv('GOOGLE_CREDENTIALS'))
# cred = credentials.Certificate(service_account_info)
# firebase_admin.initialize_app(cred, {'databaseURL': os.getenv("FIREBASE_URL")})


@app.get("/health")
async def health():
    return "ok"


# @app.get("/")
# async def find_image_keyword(img_url: str):
#     image_data = check_image(img_url)
#     image_data = json.loads(image_data)

#     g_url = create_gcal_url(
#         image_data["title"],
#         image_data["time"],
#         image_data["location"],
#         image_data["content"],
#     )
#     if is_url_valid(g_url):
#         return RedirectResponse(g_url)
#     else:
#         return "Error"

@app.get("/")
async def read_root():
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get('PORT', default=8000))
    # activate debug mode when developer mode is on
    debug = True if os.environ.get(
        'API_ENV', default='develop') == 'develop' else False
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
