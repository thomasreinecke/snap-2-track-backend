# app/orchestrator.py
import os
import uuid
from sqlmodel import Session, select
from .models import User, Meal, NutritionLog, Message, ImageStore
from .ai_engine import analyze_image_local, analyze_text_correction
from datetime import datetime
import json
from collections import defaultdict
from uuid import UUID
import traceback

# FIXED: Read from BACKEND_ENDPOINT as requested
BACKEND_ENDPOINT = os.getenv("BACKEND_ENDPOINT", "http://localhost:8000").rstrip("/")

async def handle_message(session: Session, user_identifier: str, text: str = None, image_bytes: bytes = None):
    print(f"\n📨 [NEW MSG] User: {user_identifier} | Text: {text} | Img: {len(image_bytes) if image_bytes else 0}b")

    # 1. User
    user = session.exec(select(User).where(User.identifier == user_identifier)).first()
    if not user:
        user = User(identifier=user_identifier)
        session.add(user)
        session.commit()
        session.refresh(user)

    # 2. Image (Stored in DB)
    img_id = None
    if image_bytes:
        new_image = ImageStore(data=image_bytes, mime_type="image/jpeg")
        session.add(new_image)
        session.commit()
        session.refresh(new_image)
        img_id = new_image.id

    # 3. Message Log
    user_msg = Message(user_id=user.id, sender="user", text=text, image_id=img_id)
    session.add(user_msg)
    
    active_meal = _get_latest_active_meal(session, user.id)
    ai_result = {}
    bot_reply_text = ""

    # 4. Processing
    if image_bytes:
        context_str = text if text else "New meal log"
        ai_result = await analyze_image_local(image_bytes, context=context_str)
        print(f"   🤖 AI: {json.dumps(ai_result, indent=2)}")
        
        if ai_result.get("is_food", False) is True:
            friendly_id = _generate_friendly_id()
            new_meal = Meal(user_id=user.id, friendly_id=friendly_id, status="draft", image_id=img_id)
            session.add(new_meal)
            session.commit()
            session.refresh(new_meal)
            _save_log(session, new_meal.id, ai_result)
            active_meal = new_meal
            bot_reply_text = ai_result.get("reply_text")
        else:
            bot_reply_text = ai_result.get("reply_text", "That doesn't look like food.")
            active_meal = None 
        
    elif text and active_meal:
        last_log = session.exec(select(NutritionLog).where(NutritionLog.meal_id == active_meal.id)).first()
        current_data = json.loads(last_log.raw_json) if last_log else {}
        ai_result = await analyze_text_correction(current_data, text)
        print(f"   🤖 Correction: {json.dumps(ai_result, indent=2)}")
        _update_log(session, last_log, ai_result)
        bot_reply_text = ai_result.get("reply_text", "Updated.")
        
    else:
        bot_reply_text = "Please send a photo to start tracking! 📸"

    bot_msg = Message(user_id=user.id, meal_id=active_meal.id if active_meal else None, sender="bot", text=bot_reply_text)
    session.add(bot_msg)
    session.commit()

    return {
        "reply": bot_reply_text,
        "transaction_id": active_meal.friendly_id if active_meal else None,
        "data": ai_result if ai_result.get("is_food", False) else None
    }

def reset_user(session: Session, user_identifier: str):
    print(f"\n🧨 [RESET] User: {user_identifier}")
    try:
        user = session.exec(select(User).where(User.identifier == user_identifier)).first()
        if not user:
            return False

        msgs = session.exec(select(Message).where(Message.user_id == user.id)).all()
        img_ids = {m.image_id for m in msgs if m.image_id}
        
        meals = session.exec(select(Meal).where(Meal.user_id == user.id)).all()
        for m in meals:
            if m.image_id: img_ids.add(m.image_id)
        
        session.delete(user)
        session.commit()
        
        if img_ids:
            for iid in img_ids:
                img = session.exec(select(ImageStore).where(ImageStore.id == iid)).first()
                if img: session.delete(img)
            session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Error resetting: {e}")
        return False

def delete_meal(session: Session, meal_id: str):
    try:
        clean_id = meal_id.strip()
        uuid_obj = UUID(clean_id)
        meal = session.exec(select(Meal).where(Meal.id == uuid_obj)).first()
        
        if not meal: return False
        
        logs = session.exec(select(NutritionLog).where(NutritionLog.meal_id == uuid_obj)).all()
        for log in logs: session.delete(log)
            
        msgs = session.exec(select(Message).where(Message.meal_id == uuid_obj)).all()
        for m in msgs: session.delete(m)

        session.delete(meal)
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False

def get_chat_history(session: Session, user_identifier: str):
    user = session.exec(select(User).where(User.identifier == user_identifier)).first()
    if not user: return []
    
    msgs = session.exec(select(Message).where(Message.user_id == user.id).order_by(Message.timestamp)).all()
    
    results = []
    print(f"\n📂 [HISTORY] Fetching {len(msgs)} messages")
    for m in msgs:
        img_url = None
        if m.image_id:
            img_url = f"{BACKEND_ENDPOINT}/api/image/{str(m.image_id)}"
        
        results.append({
            "id": str(m.id),
            "sender": m.sender,
            "text": m.text,
            "imageUrl": img_url,
            "timestamp": m.timestamp
        })
    return results

def get_user_history_summary(session: Session, user_identifier: str):
    user = session.exec(select(User).where(User.identifier == user_identifier)).first()
    if not user: return []

    meals = session.exec(select(Meal).where(Meal.user_id == user.id).order_by(Meal.created_at.desc())).all()
    
    history_map = defaultdict(lambda: {
        "date": "",
        "totals": {"calories": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0},
        "meals": []
    })

    for meal in meals:
        log = session.exec(select(NutritionLog).where(NutritionLog.meal_id == meal.id)).first()
        if not log: continue

        date_key = meal.created_at.strftime("%Y-%m-%d")
        day_entry = history_map[date_key]
        day_entry["date"] = date_key
        day_entry["totals"]["calories"] += log.calories_kcal
        day_entry["totals"]["protein"] += log.protein_g
        day_entry["totals"]["carbs"] += log.carbs_g
        day_entry["totals"]["fat"] += log.fat_g
        day_entry["totals"]["fiber"] += log.fiber_g 
        
        img_url = None
        if meal.image_id:
            img_url = f"{BACKEND_ENDPOINT}/api/image/{str(meal.image_id)}"

        day_entry["meals"].append({
            "id": str(meal.id),
            "time": meal.created_at.strftime("%H:%M"),
            "name": log.item_name,
            "calories": log.calories_kcal,
            "image_url": img_url
        })

    result = list(history_map.values())
    result.sort(key=lambda x: x["date"], reverse=True)
    return result

# Helpers
def _get_latest_active_meal(session, user_id):
    return session.exec(select(Meal).where(Meal.user_id == user_id).order_by(Meal.created_at.desc())).first()

def _generate_friendly_id():
    return datetime.now().strftime("%b-%d-%H%M").lower()

def _map_data_to_log(log, data):
    nutri = data.get("nutrition", {})
    log.item_name = data.get("item_name", "Unknown")
    log.meal_type = data.get("meal_type", "snack")
    log.is_composed_meal = data.get("is_composed_meal", False)
    log.estimated_weight_g = data.get("estimated_weight_g", 0)
    log.calories_kcal = nutri.get("calories_kcal", 0)
    log.protein_g = nutri.get("protein_g", 0)
    log.carbs_g = nutri.get("carbs_g", 0)
    log.fat_g = nutri.get("fat_g", 0)
    log.fiber_g = nutri.get("fiber_g", 0)
    log.confidence_score = data.get("confidence_score", 0.0)
    log.reasoning = data.get("reasoning", "")
    log.dietary_flags = data.get("dietary_flags", [])
    log.raw_json = json.dumps(data)

def _save_log(session, meal_id, data):
    log = NutritionLog(meal_id=meal_id)
    _map_data_to_log(log, data)
    session.add(log)
    session.commit()

def _update_log(session, log, data):
    _map_data_to_log(log, data)
    session.add(log)
    session.commit()