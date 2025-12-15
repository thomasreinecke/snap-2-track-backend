# app/main.py
import os
from fastapi import FastAPI, UploadFile, Form, Depends, File, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from .database import init_db, get_session
from .models import ImageStore
from .orchestrator import handle_message, get_user_history_summary, delete_meal, get_chat_history, reset_user
from uuid import UUID

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

@app.post("/api/chat")
async def chat_endpoint(
    text: str = Form(None),
    image: UploadFile = File(None),
    user_id: str = Form(...), 
    session: Session = Depends(get_session)
):
    image_bytes = None
    if image:
        image_bytes = await image.read()
    
    response = await handle_message(session, user_id, text, image_bytes)
    return response

@app.get("/api/history/{user_id}")
def history_endpoint(user_id: str, session: Session = Depends(get_session)):
    return get_user_history_summary(session, user_id)

@app.get("/api/chat/{user_id}")
def chat_history_endpoint(user_id: str, session: Session = Depends(get_session)):
    return get_chat_history(session, user_id)

@app.get("/api/image/{image_id}")
def get_image_endpoint(image_id: str, session: Session = Depends(get_session)):
    try:
        # Debug log
        # print(f"🖼️ Fetching image {image_id}") 
        uuid_obj = UUID(image_id)
        image_record = session.exec(select(ImageStore).where(ImageStore.id == uuid_obj)).first()
        
        if not image_record:
            raise HTTPException(status_code=404, detail="Image not found")
        
        return Response(content=image_record.data, media_type=image_record.mime_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

@app.delete("/api/meal/{meal_id}")
def delete_meal_endpoint(meal_id: str, session: Session = Depends(get_session)):
    success = delete_meal(session, meal_id)
    if not success:
        raise HTTPException(status_code=404, detail="Meal not found")
    return {"status": "deleted"}

@app.delete("/api/user/{user_id}")
def reset_user_endpoint(user_id: str, session: Session = Depends(get_session)):
    success = reset_user(session, user_id)
    # Return success even if user not found, to ensure idempotency for reset
    return {"status": "reset_complete"}