from fastapi import APIRouter
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


router_liff = APIRouter(prefix='/liff', tags=['liff'])


templates = Jinja2Templates(directory="templates")


@router_liff.get("/health", response_class=HTMLResponse)
async def read_item(request: Request):
    return "LIFF OK"


@router_liff.get("/create_profile", response_class=HTMLResponse)
async def create_profile(request: Request):
    return templates.TemplateResponse(
        request=request, name="create_profile.html"
    )
