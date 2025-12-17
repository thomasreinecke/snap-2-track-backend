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

async def handle_message(session: Session, user_identifier: str, text: str = None, image_bytes: bytes = None, language: str = "en"):
    print(f"\n📨 [NEW MSG] User: {user_identifier} | Lang: {language} | Text: {text} | Img: {len(image_bytes) if image_bytes else 0}b")

    # 1. User
    user = session.exec(select(User).where(User.identifier == user_identifier)).first()
    if not user:
        user = User(identifier=user_identifier)
        session.add(user)
        session.commit()
        session.refresh(user)

    # 2. Image
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
        ai_result = await analyze_image_local(image_bytes, context=context_str, language=language)
        print(f"   🤖 AI: {json.dumps(ai_result, indent=2)}")
        
        if ai_result.get("is_food", False) is True:
            friendly_id = _generate_friendly_id(session, user.id, ai_result.get("meal_type", "snack"))
            
            new_meal = Meal(user_id=user.id, friendly_id=friendly_id, status="draft", image_id=img_id)
            session.add(new_meal)
            session.commit()
            session.refresh(new_meal)
            
            _save_log(session, new_meal.id, ai_result)
            active_meal = new_meal
            bot_reply_text = ai_result.get("reply_text")
            
            user_msg.meal_id = new_meal.id
            session.add(user_msg)
            session.commit()
        else:
            bot_reply_text = ai_result.get("reply_text", "That doesn't look like food.")
            active_meal = None 
        
    elif text and active_meal:
        last_log = session.exec(select(NutritionLog).where(NutritionLog.meal_id == active_meal.id)).first()
        current_data = json.loads(last_log.raw_json) if last_log else {}
        
        ai_result = await analyze_text_correction(current_data, text, language=language)
        print(f"   🤖 Correction: {json.dumps(ai_result, indent=2)}")
        
        _update_log(session, last_log, ai_result)
        bot_reply_text = ai_result.get("reply_text", "Updated.")
        
        user_msg.meal_id = active_meal.id
        session.add(user_msg)
        session.commit()
        
    else:
        # NOTE: Hardcoded fallback strings could be localized here if desired, 
        # but for now we focus on AI responses.
        bot_reply_text = "Please send a photo to start tracking! 📸"

    bot_msg = Message(user_id=user.id, meal_id=active_meal.id if active_meal else None, sender="bot", text=bot_reply_text)
    session.add(bot_msg)
    session.commit()

    return {
        "reply": bot_reply_text,
        "transaction_id": active_meal.friendly_id if active_meal else None,
        "data": ai_result if ai_result.get("is_food", False) else None
    }

def update_meal_nutrition(session: Session, meal_id: str, updates: dict):
    try:
        uuid_obj = UUID(meal_id)
        log = session.exec(select(NutritionLog).where(NutritionLog.meal_id == uuid_obj)).first()
        if not log:
            return False
        
        # Apply updates
        if 'calories_kcal' in updates: log.calories_kcal = updates['calories_kcal']
        if 'protein_g' in updates: log.protein_g = updates['protein_g']
        if 'carbs_g' in updates: log.carbs_g = updates['carbs_g']
        if 'fat_g' in updates: log.fat_g = updates['fat_g']
        if 'fiber_g' in updates: log.fiber_g = updates['fiber_g']
        
        log.edited = True
        session.add(log)
        session.commit()
        return True
    except Exception as e:
        print(f"Update failed: {e}")
        return False

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
        
        # Aggregates
        day_entry["totals"]["calories"] += log.calories_kcal
        day_entry["totals"]["protein"] += log.protein_g
        day_entry["totals"]["carbs"] += log.carbs_g
        day_entry["totals"]["fat"] += log.fat_g
        day_entry["totals"]["fiber"] += log.fiber_g 
        
        img_url = f"/api/image/{str(meal.image_id)}" if meal.image_id else None

        # Detailed meal info for Edit modal
        day_entry["meals"].append({
            "id": str(meal.id),
            "time": meal.created_at.strftime("%H:%M"),
            "friendly_id": meal.friendly_id,
            "name": log.item_name,
            "calories": log.calories_kcal,
            "image_url": img_url,
            "macros": {
                "protein": log.protein_g,
                "carbs": log.carbs_g,
                "fat": log.fat_g,
                "fiber": log.fiber_g
            },
            "edited": log.edited
        })

    result = list(history_map.values())
    result.sort(key=lambda x: x["date"], reverse=True)
    return result

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
    results = session.exec(
        select(Message, Meal.friendly_id)
        .outerjoin(Meal, Message.meal_id == Meal.id)
        .where(Message.user_id == user.id)
        .order_by(Message.timestamp)
    ).all()
    chat_data = []
    for msg, friendly_id in results:
        img_url = f"/api/image/{str(msg.image_id)}" if msg.image_id else None
        chat_data.append({
            "id": str(msg.id),
            "sender": msg.sender,
            "text": msg.text,
            "imageUrl": img_url,
            "timestamp": msg.timestamp,
            "mealLabel": friendly_id 
        })
    return chat_data

def reset_user(session: Session, user_identifier: str):
    try:
        user = session.exec(select(User).where(User.identifier == user_identifier)).first()
        if not user: 
            return False
        
        print(f"🗑️ Deleting user {user.id} ({user_identifier}) and all data...")

        messages = session.exec(select(Message).where(Message.user_id == user.id)).all()
        for msg in messages:
            session.delete(msg)
        
        meals = session.exec(select(Meal).where(Meal.user_id == user.id)).all()
        
        for meal in meals:
            logs = session.exec(select(NutritionLog).where(NutritionLog.meal_id == meal.id)).all()
            for log in logs:
                session.delete(log)
            session.delete(meal)
            
        session.delete(user)
        session.commit()
        print("✅ User Reset Complete.")
        return True
        
    except Exception as e:
        print(f"❌ Reset failed: {str(e)}")
        traceback.print_exc()
        session.rollback()
        return False

def _get_latest_active_meal(session, user_id):
    return session.exec(select(Meal).where(Meal.user_id == user_id).order_by(Meal.created_at.desc())).first()

def _generate_friendly_id(session, user_id, meal_type):
    now = datetime.now()
    base_date = now.strftime("%b-%d").lower()
    type_slug = meal_type.lower()
    base_id = f"{base_date}-{type_slug}"
    query = select(Meal).where(Meal.user_id == user_id).where(Meal.friendly_id.like(f"{base_id}%"))
    existing_meals = session.exec(query).all()
    if not existing_meals: return base_id
    return f"{base_id}-{len(existing_meals) + 1}"

def _save_log(session, meal_id, data):
    log = NutritionLog(meal_id=meal_id)
    _map_data_to_log(log, data)
    session.add(log)
    session.commit()

def _update_log(session, log, data):
    _map_data_to_log(log, data)
    session.add(log)
    session.commit()

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