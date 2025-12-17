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

async def analyze_image_local(image_bytes: bytes, context: str = "", language: str = "en"):
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

    system_prompt = f"""You are 'Snap-2-Track', a culinary expert with a sharp eye for nutrition.
    Analyze the food image. Context provided by user: "{context}"
    
    GUIDELINES FOR 'reply_text':
    1. **Natural & Varied:** React to the dish naturally. **Do NOT** start with "The image shows", "This is", or "I see". 
       - Instead, dive straight into the details: "That golden crust looks perfectly baked!" or "A vibrant bowl of fresh greens."
    2. **Emotion/Vibe:** Include a touch of appreciation for the food's appeal or 'comfort' level. Be professional but human.
    3. **Macros:** You MUST explicitly weave the key macro numbers into the narrative (e.g., "...packing about 600 kcal with 30g Protein").
    4. **Length:** Keep it concise (2-3 sentences max).
    5. **NO PREACHING:** No health advice, no judgment. Just the food facts and the vibe.
    6. **LANGUAGE:** You MUST write the 'reply_text' and 'item_name' in this language: [{language}]. The JSON keys must remain in English.

    Return ONLY valid JSON:
    {schema_definition}
    """

    print(f"🚀 Sending request to OpenRouter ({MODEL_ID})... [Lang: {language}]")

    try:
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_url}}]}
            ],
            temperature=0.4,
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

async def analyze_text_correction(current_log: dict, user_text: str, language: str = "en"):
    prompt = f"""
    Current Meal Data: {json.dumps(current_log)}
    User Correction: "{user_text}"
    Target Language: {language}
    
    Task:
    1. Update 'item_name', 'nutrition' totals based on the user's input.
    2. 'reply_text': Acknowledge the change naturally and professionally in [{language}].
       - Example: "Got it, added the extra slice. That brings it to..."
       - Confirm the new total macros in the text.
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