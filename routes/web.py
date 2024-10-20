from fastapi import APIRouter
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from fastapi.templating import Jinja2Templates


router_web = APIRouter(prefix='/web', tags=['web'])


templates = Jinja2Templates(directory="templates")


@router_web.get("/create_profile", response_class=HTMLResponse)
async def create_profile(request: Request):
    return templates.TemplateResponse(
        request=request, name="create_profile.html"
    )
