"""
Vision Service Module
Handles integration with Google Gemini Vision API for object identification
and Google Custom Search API for similar images.
"""

import os
import base64
import json
from typing import Dict, List, Optional

from dotenv import load_dotenv


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

# Environment variables for API keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID", "")


def _call_gemini(client, model: str, image_bytes: bytes, mime_type: str, prompt: str) -> Dict:
    """
    Make a single Gemini API call and parse the JSON response.
    Raises on failure so the caller can retry or fall back.
    """
    from google.genai import types

    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            prompt,
        ],
    )

    # Parse JSON response - handle potential markdown code fences
    response_text = response.text.strip()
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        response_text = "\n".join(lines).strip()

    result = json.loads(response_text)

    if not result.get("name") or not result.get("description"):
        raise Exception("Gemini API returned incomplete data")

    if not isinstance(result.get("tags"), list):
        result["tags"] = []

    return result


def _extract_retry_delay(error_message: str) -> float:
    """Extract the suggested retry delay from a 429 error message."""
    import re
    match = re.search(r"retry in ([\d.]+)s", error_message, re.IGNORECASE)
    if match:
        return min(float(match.group(1)), 60.0)  # Cap at 60s
    return 10.0  # Default 10s wait


# Models to try in order — each has a separate free-tier quota
GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]


def identify_object_with_gemini(image_base64: str) -> Dict:
    """
    Identify object in image using Gemini Vision API.
    Automatically retries on rate-limit errors and falls back to
    alternative models that have separate free-tier quotas.

    Args:
        image_base64: Base64 encoded image data (with data:image/... prefix)

    Returns:
        Dict with keys: name, description, tags

    Raises:
        Exception: If all models and retries are exhausted
    """
    import time

    if not GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY environment variable not set")

    try:
        from google import genai
    except ImportError:
        raise Exception("google-genai package not installed. Run: pip install google-genai")

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Extract base64 data and detect mime type
    mime_type = "image/jpeg"
    if image_base64.startswith("data:"):
        header, image_data = image_base64.split(",", 1)
        if "image/png" in header:
            mime_type = "image/png"
        elif "image/webp" in header:
            mime_type = "image/webp"
    else:
        image_data = image_base64

    image_bytes = base64.b64decode(image_data)

    prompt = """Analyze this image and identify the main object or subject. 
Respond ONLY with valid JSON (no markdown, no code fences) in this exact format:
{"name": "concise name 2-4 words", "description": "detailed 2-3 sentence description", "tags": ["tag1", "tag2", "tag3", "tag4"]}

Be specific and accurate. If multiple objects are present, focus on the most prominent one.
Include 4-8 relevant tags for categorization."""

    last_error = None

    for model in GEMINI_MODELS:
        # Try each model up to 2 times (initial + 1 retry after waiting)
        for attempt in range(2):
            try:
                print(f"[Vision] Trying model={model}, attempt={attempt + 1}")
                result = _call_gemini(client, model, image_bytes, mime_type, prompt)
                print(f"[Vision] Success with model={model}")
                return result

            except json.JSONDecodeError as e:
                last_error = Exception(f"Failed to parse Gemini API response: {e}")
                break  # JSON parse errors won't be fixed by retrying

            except Exception as e:
                error_str = str(e)
                last_error = e

                # If model not found (404), skip to next model immediately
                if "404" in error_str or "NOT_FOUND" in error_str:
                    print(f"[Vision] Model {model} not available, trying next model...")
                    break  # Move to next model

                # If rate-limited (429), wait and retry once, then try next model
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    if attempt == 0:
                        delay = _extract_retry_delay(error_str)
                        print(f"[Vision] Rate limited on {model}, waiting {delay:.0f}s before retry...")
                        time.sleep(delay)
                        continue
                    else:
                        print(f"[Vision] Rate limited on {model} after retry, trying next model...")
                        break  # Move to next model
                else:
                    # Other errors — don't retry
                    raise Exception(f"Gemini API error: {error_str}")

    raise Exception(
        f"All Gemini models are currently rate-limited. "
        f"Your free-tier quota has been exhausted. Please wait a few minutes and try again. "
        f"Last error: {last_error}"
    )


def get_similar_images_google(query: str, count: int = 6) -> List[Dict]:
    """
    Search for similar images using Google Custom Search API.
    
    Args:
        query: Search query (object name or description)
        count: Number of images to return (default 6)
    
    Returns:
        List of dicts with keys: url, thumbnail, title, source
    
    Raises:
        Exception: If API call fails or API keys are missing
    """
    if not GOOGLE_SEARCH_API_KEY or not SEARCH_ENGINE_ID:
        raise Exception("GOOGLE_SEARCH_API_KEY or SEARCH_ENGINE_ID not set")
    
    try:
        from googleapiclient.discovery import build
        
        # Initialize Custom Search API client
        service = build("customsearch", "v1", developerKey=GOOGLE_SEARCH_API_KEY)
        
        # Execute search with image search type
        result = service.cse().list(
            q=query,
            cx=SEARCH_ENGINE_ID,
            searchType="image",
            num=min(count, 10),  # API max is 10
            safe="active",  # Filter explicit content
            fileType="jpg,png",
            imgSize="MEDIUM"
        ).execute()
        
        # Parse results
        images = []
        for item in result.get("items", [])[:count]:
            images.append({
                "url": item.get("link", ""),
                "thumbnail": item.get("image", {}).get("thumbnailLink", item.get("link", "")),
                "title": item.get("title", "Similar Image"),
                "source": item.get("displayLink", "")
            })
        
        return images
        
    except ImportError:
        raise Exception("google-api-python-client package not installed. Run: pip install google-api-python-client")
    except Exception as e:
        raise Exception(f"Google Search API error: {str(e)}")


def get_similar_images_fallback(query: str, tags: List[str], count: int = 6) -> List[Dict]:
    """
    Fallback: search for images using a direct HTTP request to Google Custom
    Search REST API (bypasses the client library). If that also fails, use
    loremflickr.com which serves real Flickr photos matching keywords — no
    API key required.
    """
    import random
    import requests as req

    # --- Attempt 1: Direct REST call to Google Custom Search ---
    if GOOGLE_SEARCH_API_KEY and SEARCH_ENGINE_ID:
        try:
            resp = req.get(
                "https://customsearch.googleapis.com/customsearch/v1",
                params={
                    "q": query,
                    "cx": SEARCH_ENGINE_ID,
                    "key": GOOGLE_SEARCH_API_KEY,
                    "searchType": "image",
                    "num": min(count, 10),
                    "safe": "active",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                images = []
                for item in data.get("items", [])[:count]:
                    images.append({
                        "url": item.get("link", ""),
                        "thumbnail": item.get("image", {}).get(
                            "thumbnailLink", item.get("link", "")
                        ),
                        "title": item.get("title", "Similar Image"),
                        "source": item.get("displayLink", ""),
                    })
                if images:
                    return images
            else:
                print(f"[Vision] Direct REST search returned {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[Vision] Direct REST search failed: {e}")

    # --- Attempt 2: loremflickr.com (keyword-based random Flickr images) ---
    search_terms = [query] + tags[:5]
    images = []

    for i in range(count):
        term = search_terms[i % len(search_terms)].replace(" ", ",")
        lock_id = random.randint(1, 99999)
        images.append({
            "url": f"https://loremflickr.com/800/600/{term}?lock={lock_id}",
            "thumbnail": f"https://loremflickr.com/300/200/{term}?lock={lock_id}",
            "title": f"{query} - {search_terms[i % len(search_terms)].title()}",
            "source": "flickr.com",
        })

    return images


def get_similar_images(query: str, tags: List[str] = None, count: int = 6) -> List[Dict]:
    """
    Search for similar images. Tries Google Custom Search first, 
    falls back to Unsplash Source if Google fails.
    """
    # Try Google Custom Search API first
    try:
        results = get_similar_images_google(query, count)
        if results:
            return results
    except Exception as e:
        print(f"[Vision] Google Custom Search failed: {e}")
        print("[Vision] Falling back to Unsplash Source...")
    
    # Fallback to Unsplash
    return get_similar_images_fallback(query, tags or [], count)


def identify_object_and_find_similar(image_base64: str) -> Dict:
    """
    Complete flow: Identify object with Gemini and find similar images.
    
    Args:
        image_base64: Base64 encoded image data
    
    Returns:
        Dict with keys: object (name, description, tags), similar_images
    """
    # Step 1: Identify object with Gemini
    object_info = identify_object_with_gemini(image_base64)
    
    # Step 2: Search for similar images using object name + first tag
    search_query = object_info["name"]
    if object_info["tags"]:
        search_query += " " + object_info["tags"][0]
    
    try:
        similar_images = get_similar_images(
            search_query, 
            tags=object_info.get("tags", []),
            count=6
        )
    except Exception as e:
        # If everything fails, return empty list but don't fail the whole request
        print(f"Warning: All image search methods failed: {e}")
        similar_images = []
    
    return {
        "object": object_info,
        "similar_images": similar_images
    }

