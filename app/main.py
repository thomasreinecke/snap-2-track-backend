# app/main.py
import os
from fastapi import FastAPI, UploadFile, Form, Depends, File, HTTPException, Response, Body, Security
from fastapi.security import APIKeyHeader
# CORS middleware removed for internal proxy architecture
from sqlmodel import Session, select
from .database import init_db, get_session
from .models import ImageStore
from .orchestrator import handle_message, get_user_history_summary, delete_meal, get_chat_history, reset_user, update_meal_nutrition
from uuid import UUID

app = FastAPI()

# --- Security Configuration ---
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

def get_api_key(api_key: str = Security(api_key_header)):
    """
    Validates API Key from SvelteKit proxy.
    """
    server_key = os.getenv("API_KEY")
    if server_key and api_key != server_key:
        raise HTTPException(
            status_code=403,
            detail="Invalid API Key"
        )
    return api_key
# ------------------------------

@app.on_event("startup")
def on_startup():
    init_db()

@app.post("/api/chat", dependencies=[Depends(get_api_key)])
async def chat_endpoint(
    text: str = Form(None),
    image: UploadFile = File(None),
    user_id: str = Form(...),
    language: str = Form("en"),
    session: Session = Depends(get_session)
):
    image_bytes = None
    if image:
        image_bytes = await image.read()
    
    response = await handle_message(session, user_id, text, image_bytes, language)
    return response

@app.get("/api/history/{user_id}", dependencies=[Depends(get_api_key)])
def history_endpoint(user_id: str, session: Session = Depends(get_session)):
    return get_user_history_summary(session, user_id)

@app.get("/api/chat/{user_id}", dependencies=[Depends(get_api_key)])
def chat_history_endpoint(user_id: str, session: Session = Depends(get_session)):
    return get_chat_history(session, user_id)

@app.get("/api/image/{image_id}", dependencies=[Depends(get_api_key)])
def get_image_endpoint(image_id: str, session: Session = Depends(get_session)):
    try:
        uuid_obj = UUID(image_id)
        image_record = session.exec(select(ImageStore).where(ImageStore.id == uuid_obj)).first()
        if not image_record:
            raise HTTPException(status_code=404, detail="Image not found")
        return Response(content=image_record.data, media_type=image_record.mime_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

@app.delete("/api/meal/{meal_id}", dependencies=[Depends(get_api_key)])
def delete_meal_endpoint(meal_id: str, session: Session = Depends(get_session)):
    success = delete_meal(session, meal_id)
    if not success:
        raise HTTPException(status_code=404, detail="Meal not found")
    return {"status": "deleted"}

@app.put("/api/meal/{meal_id}", dependencies=[Depends(get_api_key)])
def update_meal_endpoint(meal_id: str, updates: dict = Body(...), session: Session = Depends(get_session)):
    success = update_meal_nutrition(session, meal_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail="Meal not found")
    return {"status": "updated"}

@app.delete("/api/user/{user_id}", dependencies=[Depends(get_api_key)])
def reset_user_endpoint(user_id: str, session: Session = Depends(get_session)):
    success = reset_user(session, user_id)
    return {"status": "reset_complete"}