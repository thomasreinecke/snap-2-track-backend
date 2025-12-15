# process_local_images.py
import asyncio
import os
import json
import time
# Ensure we can import from the app module
import sys
sys.path.append(os.getcwd())

from app.ai_engine import analyze_image_local

PICTURES_DIR = "pictures"

async def main():
    # Check if directory exists
    if not os.path.exists(PICTURES_DIR):
        print(f"❌ Error: Directory '{PICTURES_DIR}' not found.")
        print("Please create it and add .jpg/.png files.")
        return

    # Get list of images
    files = [f for f in os.listdir(PICTURES_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
    files.sort()

    if not files:
        print(f"⚠️  No images found in '{PICTURES_DIR}'.")
        return

    print(f"🔎 Found {len(files)} images. Starting local AI analysis...\n")
    print("="*60)

    for i, filename in enumerate(files, 1):
        filepath = os.path.join(PICTURES_DIR, filename)
        print(f"[{i}/{len(files)}] Processing: {filename}...")
        
        start_time = time.time()
        
        try:
            with open(filepath, "rb") as f:
                image_bytes = f.read()
            
            # Call the AI Engine
            result = await analyze_image_local(image_bytes, context="Batch processing test")
            
            elapsed = time.time() - start_time
            
            # Print Result
            print(f"✅ Finished in {elapsed:.2f}s")
            print(json.dumps(result, indent=2))
            
        except Exception as e:
            print(f"❌ Failed: {str(e)}")
            
        print("-" * 60)

if __name__ == "__main__":
    asyncio.run(main())