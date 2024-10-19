from fastapi import APIRouter
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


router_web = APIRouter(prefix='/web', tags=['web'])

router_web.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


@router_web.get("/", response_class=HTMLResponse)
async def read_item(request: Request, name: "str" = "World"):
    return templates.TemplateResponse(
        request=request, name="index.html", context={"name": name}
    )
