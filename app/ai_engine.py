# app/ai_engine.py
import os
import base64
import json
import time
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
    start_time = time.time()

    try:
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_url}}]}
            ],
            temperature=0.4,
            max_tokens=1000,
            extra_body={"include_usage": True}
        )
        
        latency = time.time() - start_time
        cost = _extract_cost(response)
        raw_metadata = response.model_dump() if hasattr(response, 'model_dump') else response.__dict__
        
        data = _clean_json(response.choices[0].message.content)
        
        return {
            "data": data,
            "cost": cost,
            "latency": latency,
            "metadata": raw_metadata
        }

    except Exception as e:
        print(f"❌ OpenRouter API Error: {str(e)}")
        return {
            "data": _error_data(str(e)),
            "cost": 0.0,
            "latency": time.time() - start_time,
            "metadata": {"error": str(e)}
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
    start_time = time.time()
    try:
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            extra_body={"include_usage": True}
        )
        
        latency = time.time() - start_time
        cost = _extract_cost(response)
        raw_metadata = response.model_dump() if hasattr(response, 'model_dump') else response.__dict__
        data = _clean_json(response.choices[0].message.content)
        
        return {
            "data": data,
            "cost": cost,
            "latency": latency,
            "metadata": raw_metadata
        }
        
    except Exception as e:
        print(f"❌ Correction Error: {e}")
        return {
            "data": current_log, 
            "cost": 0.0, 
            "latency": time.time() - start_time,
            "metadata": {"error": str(e)}
        }

def _extract_cost(response):
    try:
        if hasattr(response, 'usage') and response.usage:
            usage_dict = response.usage.model_dump() if hasattr(response.usage, 'model_dump') else response.usage.__dict__
            return float(usage_dict.get('cost', 0.0))
    except Exception as e:
        print(f"⚠️ Could not extract cost: {e}")
    return 0.0

def _clean_json(text: str):
    text = text.replace("```json", "").replace("```", "").strip()
    start_idx = text.find('{')
    end_idx = text.rfind('}')
    if start_idx != -1 and end_idx != -1:
        text = text[start_idx : end_idx + 1]
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return _error_data(f"Raw output: {text[:50]}...")

def _error_data(msg):
    return {
        "is_food": False,
        "item_name": "Error",
        "reply_text": f"System error: {msg}",
        "nutrition": {"calories_kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}
    }