# app/ai_engine.py
import os
import base64
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_ID = os.getenv("MODEL_ID", "qwen/qwen-2-vl-72b-instruct")
SITE_URL = os.getenv("SITE_URL", "http://localhost:3000")
APP_NAME = os.getenv("APP_NAME", "Snap-2-Track")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    default_headers={
        "HTTP-Referer": SITE_URL,
        "X-Title": APP_NAME,
    }
)

async def analyze_image_local(image_bytes: bytes, context: str = ""):
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    image_url = f"data:image/jpeg;base64,{base64_image}"

    schema_definition = """
    {
        "is_food": boolean, 
        "item_name": "Short name",
        "meal_type": "breakfast|lunch|dinner|snack",
        "is_composed_meal": true, 
        "estimated_weight_g": <int>,
        "nutrition": {
            "calories_kcal": <int>,
            "protein_g": <int>,
            "carbs_g": <int>,
            "fat_g": <int>,
            "fiber_g": <int>
        },
        "dietary_flags": ["string"],
        "confidence_score": <float 0.0-1.0>,
        "reasoning": "Technical reasoning",
        "reply_text": "Response to user"
    }
    """

    system_prompt = f"""You are 'Snap-2-Track'. Analyze the food image. Context: "{context}"
    
    GUIDELINES FOR 'reply_text':
    1. **Describe Visuals:** Briefly describe what you see (colors, textures, plating).
    2. **State Macros:** You MUST explicitly list the identified macros in the text (e.g. "I estimate ~500 kcal, 30g Protein, ...").
    3. **NO PREACHING:** Do NOT give health advice, do NOT say "watch your sugar", do NOT say "this is a healthy choice". Just state the facts of the food.
    4. **Tone:** Neutral, observant, professional but casual.
    
    If text context adds items (e.g. "plus a beer"), include them in math and text.

    Return ONLY valid JSON:
    {schema_definition}
    """

    print(f"🚀 Sending request to OpenRouter ({MODEL_ID})...")

    try:
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_url}}]}
            ],
            temperature=0.2, 
            max_tokens=1000
        )
        return _clean_json(response.choices[0].message.content)

    except Exception as e:
        print(f"❌ OpenRouter API Error: {str(e)}")
        return {
            "is_food": False,
            "item_name": "API Error",
            "reply_text": f"My brain is offline momentarily! 🤯 Error: {str(e)}",
            "nutrition": {"calories_kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}
        }

async def analyze_text_correction(current_log: dict, user_text: str):
    prompt = f"""
    Current Meal Data: {json.dumps(current_log)}
    User Correction: "{user_text}"
    
    Task:
    1. Update 'item_name', 'nutrition' totals.
    2. 'reply_text': Confirm the change AND list the new total macros. 
    3. NO PREACHING.

    Return ONLY the updated JSON.
    """
    try:
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return _clean_json(response.choices[0].message.content)
    except Exception as e:
        return current_log

def _clean_json(text: str):
    text = text.replace("```json", "").replace("```", "").strip()
    start_idx = text.find('{')
    end_idx = text.rfind('}')
    if start_idx != -1 and end_idx != -1:
        text = text[start_idx : end_idx + 1]
    
    data = {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {
            "is_food": False,
            "item_name": "Parsing Error",
            "reply_text": "I saw the food, but I tripped over the math. Try again? 📉",
            "reasoning": f"Raw output: {text[:50]}..."
        }
    
    # Strip whitespace from reply_text if it exists
    if "reply_text" in data and isinstance(data["reply_text"], str):
        data["reply_text"] = data["reply_text"].strip()
        
    return data