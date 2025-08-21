"""Robust JSON parsing utilities for handling malformed API responses."""

import re
import json
from typing import Any, Dict


def clean_json_response(response_text: Any) -> Dict[str, Any]:
    """
    Clean and parse potentially malformed JSON responses from search APIs.
    Handles emojis, HTML tags, and mixed content.
    """
    try:
        # Convert to string if not already
        if not isinstance(response_text, str):
            response_text = str(response_text)
        
        # Remove emojis and non-ASCII characters that break JSON
        cleaned = re.sub(r'[^\x00-\x7F]+', '', response_text)
        
        # Remove HTML tags if present
        cleaned = re.sub(r'<[^>]+>', '', cleaned)
        
        # Remove common problematic characters
        cleaned = cleaned.replace('@', '').replace('#', '')
        
        # Try to extract JSON object from mixed content
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group()
        
        # Parse the cleaned JSON
        return json.loads(cleaned)
        
    except json.JSONDecodeError as e:
        # If JSON parsing still fails, return structured fallback
        return {
            "results": [],
            "error": f"JSON parsing failed: {str(e)}",
            "raw_content": response_text[:200],  # First 200 chars for debugging
            "success": False
        }
    except Exception as e:
        # Handle any other errors
        return {
            "results": [],
            "error": f"Response processing failed: {str(e)}",
            "success": False
        }


def debug_api_response(response: Any, api_name: str = "API") -> None:
    """
    Debug API response to understand what format is being returned.
    """
    print(f"=== {api_name} Response Debug ===")
    print(f"Response type: {type(response)}")
    print(f"Response length: {len(str(response))}")
    print(f"First 200 characters: {str(response)[:200]}")
    print(f"Last 200 characters: {str(response)[-200:]}")
    print("========================")