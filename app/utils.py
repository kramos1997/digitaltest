"""Utility functions for the application."""

import re
import json
import logging
from typing import Dict, Any, List
from datetime import datetime

from .config import get_settings

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def log_structured(event: str, data: Dict[str, Any]):
    """Log structured events as JSON."""
    
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event": event,
        **data
    }
    
    # In GDPR mode, don't log sensitive information
    if settings.gdpr_mode:
        # Remove potentially sensitive fields
        sensitive_fields = ['query', 'ip', 'url', 'content', 'text']
        for field in sensitive_fields:
            if field in log_entry:
                if field == 'query':
                    log_entry[field] = f"[REDACTED_{len(str(data.get(field, '')))}chars]"
                else:
                    log_entry.pop(field, None)
    
    logger.info(json.dumps(log_entry))


def redact_sensitive_data(text: str) -> str:
    """Redact emails, phone numbers, and other sensitive data from text."""
    
    if not text:
        return text
    
    # Email addresses
    text = re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 
        '[EMAIL_REDACTED]', 
        text
    )
    
    # Phone numbers (various formats)
    phone_patterns = [
        r'\b\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',  # US/Canada
        r'\b\+?[0-9]{2,3}[-.\s]?[0-9]{3,4}[-.\s]?[0-9]{3,4}[-.\s]?[0-9]{3,4}\b',  # International
    ]
    
    for pattern in phone_patterns:
        text = re.sub(pattern, '[PHONE_REDACTED]', text)
    
    # IP addresses
    text = re.sub(
        r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
        '[IP_REDACTED]',
        text
    )
    
    # Credit card patterns (basic)
    text = re.sub(
        r'\b(?:[0-9]{4}[-\s]?){3}[0-9]{4}\b',
        '[CARD_REDACTED]',
        text
    )
    
    # Social Security Numbers (US format)
    text = re.sub(
        r'\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b',
        '[SSN_REDACTED]',
        text
    )
    
    return text


def clean_html_text(html: str) -> str:
    """Clean HTML and extract text content."""
    
    from bs4 import BeautifulSoup
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()
        
        # Get text and clean whitespace
        text = soup.get_text(separator=' ')
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
        
    except Exception:
        return ""


def extract_domain(url: str) -> str:
    """Extract clean domain from URL."""
    
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
            
        return domain
        
    except Exception:
        return ""


def normalize_date(date_str: str) -> str:
    """Normalize various date formats to YYYY-MM."""
    
    if not date_str:
        return ""
    
    try:
        from dateutil import parser
        parsed_date = parser.parse(date_str)
        return parsed_date.strftime('%Y-%m')
    except Exception:
        # Try to extract year at minimum
        year_match = re.search(r'\b(20[0-9]{2})\b', date_str)
        if year_match:
            return year_match.group(1) + "-01"  # Default to January
        return date_str  # Return as-is if can't parse


def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate simple text similarity score (0-1)."""
    
    if not text1 or not text2:
        return 0.0
    
    # Simple word-based similarity
    words1 = set(re.findall(r'\w+', text1.lower()))
    words2 = set(re.findall(r'\w+', text2.lower()))
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1 & words2
    union = words1 | words2
    
    return len(intersection) / len(union) if union else 0.0


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to maximum length with suffix."""
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def extract_sentences(text: str, max_sentences: int = None) -> List[str]:
    """Extract sentences from text."""
    
    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    # Clean sentences
    cleaned_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) > 10:  # Minimum sentence length
            cleaned_sentences.append(sentence)
    
    if max_sentences:
        cleaned_sentences = cleaned_sentences[:max_sentences]
    
    return cleaned_sentences


def is_recent_date(date_str: str, months_threshold: int = 24) -> bool:
    """Check if date is within the specified months threshold."""
    
    if not date_str:
        return False
    
    try:
        from dateutil import parser
        parsed_date = parser.parse(date_str)
        now = datetime.now()
        
        months_diff = (now.year - parsed_date.year) * 12 + (now.month - parsed_date.month)
        return months_diff <= months_threshold
        
    except Exception:
        return False


def deduplicate_by_key(items: List[Dict], key: str) -> List[Dict]:
    """Deduplicate list of dictionaries by a specific key."""
    
    seen = set()
    deduped = []
    
    for item in items:
        key_value = item.get(key)
        if key_value and key_value not in seen:
            seen.add(key_value)
            deduped.append(item)
    
    return deduped


def format_processing_time(seconds: float) -> str:
    """Format processing time for display."""
    
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.1f}s"


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage."""
    
    # Remove/replace unsafe characters
    filename = re.sub(r'[^\w\s-.]', '', filename)
    filename = re.sub(r'[-\s]+', '-', filename)
    
    return filename.strip('.-')


def validate_url(url: str) -> bool:
    """Basic URL validation."""
    
    try:
        from urllib.parse import urlparse
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def count_tokens_estimate(text: str) -> int:
    """Rough estimate of token count for text."""
    
    # Very rough estimate: ~4 characters per token for English
    return len(text) // 4


def create_safe_dict(data: Dict[str, Any], allowed_keys: List[str]) -> Dict[str, Any]:
    """Create dictionary with only allowed keys."""
    
    return {k: v for k, v in data.items() if k in allowed_keys}
