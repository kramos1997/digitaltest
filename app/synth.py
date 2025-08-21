"""Answer synthesis and factchecking module."""

import re
import json
from typing import Dict, List, Any, Optional
import asyncio

from .models import ScrapedDoc
from .prompts import SYSTEM_RESEARCH, SYSTEM_FACTCHECK
from .config import get_settings
from .utils import log_structured


settings = get_settings()


async def synthesize_answer(query: str, documents: List[ScrapedDoc], llm_client) -> Dict[str, Any]:
    """
    Synthesize a comprehensive answer from ranked documents.
    
    Args:
        query: Original research query
        documents: Top-ranked scraped documents
        llm_client: LLM client for synthesis
        
    Returns:
        Dictionary containing answer, sources, and metadata
    """
    if not documents:
        return {
            "answer": "No reliable sources found for this query. Please try rephrasing or checking your internet connection.",
            "sources": [],
            "confidence": "none"
        }
    
    # Step 1: Prepare source context
    sources_context = _prepare_sources_context(documents[:8])  # Use top 8 sources
    
    # Step 2: Create synthesis prompt
    synthesis_prompt = _create_synthesis_prompt(query, sources_context)
    
    # Step 3: Generate initial answer
    messages = [
        {"role": "system", "content": SYSTEM_RESEARCH},
        {"role": "user", "content": synthesis_prompt}
    ]
    
    try:
        # Get LLM response
        response_chunks = []
        async for chunk in llm_client.chat(messages, temperature=0.2, max_tokens=800):
            response_chunks.append(chunk)
        
        initial_answer = "".join(response_chunks)
        
        # Step 4: Parse answer and extract citations
        parsed_answer = _parse_answer_response(initial_answer, documents)
        
        # Step 5: Factcheck the answer
        factcheck_result = await _factcheck_answer(parsed_answer['answer'], documents, llm_client)
        
        # Step 6: Regenerate if needed
        if factcheck_result['needs_revision']:
            log_structured("answer_revision_needed", {
                "issues": len(factcheck_result['issues']),
                "revision_strategy": "soften_claims"
            })
            
            # Try regeneration with stricter instructions
            revised_answer = await _regenerate_answer(query, documents, factcheck_result['issues'], llm_client)
            if revised_answer:
                parsed_answer = _parse_answer_response(revised_answer, documents)
        
        # Step 7: Final formatting
        final_response = {
            "answer": parsed_answer['answer'],
            "sources": _format_sources_list(documents[:8]),
            "confidence": _assess_confidence(parsed_answer['answer'], documents),
            "citations_count": len(parsed_answer['citations']),
            "factcheck_status": "passed" if not factcheck_result['needs_revision'] else "revised"
        }
        
        log_structured("synthesis_complete", {
            "answer_length": len(final_response['answer']),
            "sources_count": len(final_response['sources']),
            "confidence": final_response['confidence'],
            "factcheck_status": final_response['factcheck_status']
        })
        
        return final_response
        
    except Exception as e:
        log_structured("synthesis_error", {"error": str(e)})
        return {
            "answer": f"An error occurred during answer synthesis: {str(e)}. Please try again or contact support.",
            "sources": _format_sources_list(documents[:5]),  # Show some sources even on error
            "confidence": "error"
        }


async def _factcheck_answer(answer: str, documents: List[ScrapedDoc], llm_client) -> Dict[str, Any]:
    """Factcheck the generated answer against source documents."""
    
    try:
        # Create factcheck context
        factcheck_context = _create_factcheck_context(answer, documents)
        
        messages = [
            {"role": "system", "content": SYSTEM_FACTCHECK},
            {"role": "user", "content": factcheck_context}
        ]
        
        # Get factcheck response
        response_chunks = []
        async for chunk in llm_client.chat(messages, temperature=0.1, max_tokens=500):
            response_chunks.append(chunk)
        
        factcheck_response = "".join(response_chunks)
        
        # Parse factcheck results
        if "FACTCHECK_PASS" in factcheck_response:
            return {"needs_revision": False, "issues": []}
        elif "FACTCHECK_ISSUES" in factcheck_response:
            issues = _parse_factcheck_issues(factcheck_response)
            return {"needs_revision": len(issues) > 2, "issues": issues}  # Revise if >2 issues
        else:
            return {"needs_revision": False, "issues": []}  # Default to pass if unclear
            
    except Exception as e:
        log_structured("factcheck_error", {"error": str(e)})
        return {"needs_revision": False, "issues": []}


async def _regenerate_answer(query: str, documents: List[ScrapedDoc], issues: List[str], llm_client) -> Optional[str]:
    """Regenerate answer with stricter factual requirements."""
    
    try:
        # Create regeneration prompt with issue awareness
        regeneration_prompt = _create_regeneration_prompt(query, documents, issues)
        
        messages = [
            {"role": "system", "content": SYSTEM_RESEARCH + "\n\nIMPORTANT: Be extra careful about factual accuracy. If uncertain about any claim, either omit it or clearly qualify with 'according to [source]' or 'preliminary data suggests'."},
            {"role": "user", "content": regeneration_prompt}
        ]
        
        # Get revised response
        response_chunks = []
        async for chunk in llm_client.chat(messages, temperature=0.1, max_tokens=800):
            response_chunks.append(chunk)
        
        return "".join(response_chunks)
        
    except Exception as e:
        log_structured("regeneration_error", {"error": str(e)})
        return None


def _prepare_sources_context(documents: List[ScrapedDoc]) -> str:
    """Prepare formatted source context for LLM."""
    
    sources_text = []
    for i, doc in enumerate(documents, 1):
        # Limit document text to prevent token overflow
        text_preview = doc.text[:1500] + "..." if len(doc.text) > 1500 else doc.text
        
        source_block = f"""
[{i}] {doc.title}
URL: {doc.url}
Domain: {doc.domain}
Date: {doc.published_at_guess or 'Unknown'}
Content: {text_preview}
"""
        sources_text.append(source_block)
    
    return "\n".join(sources_text)


def _create_synthesis_prompt(query: str, sources_context: str) -> str:
    """Create the synthesis prompt for the LLM."""
    
    return f"""Query: "{query}"

Please synthesize a comprehensive answer based on the following sources. Follow the system instructions carefully.

Sources:
{sources_context}

Remember to:
1. Use numbered citations [1][2] for all factual claims
2. Create a Sources section with pull-quotes
3. Be concise but comprehensive (3-6 paragraphs)
4. State confidence level and suggest follow-up searches if needed
"""


def _create_factcheck_context(answer: str, documents: List[ScrapedDoc]) -> str:
    """Create context for factchecking."""
    
    # Include both the answer and source summaries
    sources_summary = []
    for i, doc in enumerate(documents, 1):
        summary = f"[{i}] {doc.title} ({doc.domain}): {doc.text[:500]}..."
        sources_summary.append(summary)
    
    return f"""Answer to fact-check:
{answer}

Available Sources:
{chr(10).join(sources_summary)}

Check all factual claims, citations, and quotes for accuracy."""


def _create_regeneration_prompt(query: str, documents: List[ScrapedDoc], issues: List[str]) -> str:
    """Create prompt for answer regeneration."""
    
    issues_text = "\n".join([f"- {issue}" for issue in issues])
    sources_context = _prepare_sources_context(documents)
    
    return f"""Query: "{query}"

The previous answer had these factual issues:
{issues_text}

Please generate a new answer that addresses these concerns. Be more conservative with claims and ensure all citations are accurate.

Sources:
{sources_context}
"""


def _parse_answer_response(response: str, documents: List[ScrapedDoc]) -> Dict[str, Any]:
    """Parse LLM response to extract answer and citations."""
    
    # Extract citations [1][2] etc.
    citations = re.findall(r'\[(\d+)\]', response)
    unique_citations = list(set(citations))
    
    return {
        "answer": response,
        "citations": unique_citations,
        "citation_count": len(unique_citations)
    }


def _parse_factcheck_issues(response: str) -> List[str]:
    """Parse factcheck issues from LLM response."""
    
    try:
        # Look for numbered issues after "FACTCHECK_ISSUES:"
        issues_section = response.split("FACTCHECK_ISSUES:")[-1]
        
        # Extract numbered items
        issues = re.findall(r'\d+\.\s*([^\n]+)', issues_section)
        
        return issues[:5]  # Limit to top 5 issues
        
    except Exception:
        return []


def _format_sources_list(documents: List[ScrapedDoc]) -> List[Dict[str, Any]]:
    """Format documents into sources list for response."""
    
    sources = []
    for i, doc in enumerate(documents, 1):
        # Extract good pull-quotes
        pull_quotes = _extract_pull_quotes(doc.text)
        
        source = {
            "id": i,
            "title": doc.title or "Untitled",
            "url": doc.url,
            "domain": doc.domain or "unknown",
            "published_date": doc.published_at_guess or "Unknown date",
            "pull_quotes": pull_quotes[:4]  # Max 4 quotes per source
        }
        sources.append(source)
    
    return sources


def _extract_pull_quotes(text: str, max_quotes: int = 4) -> List[str]:
    """Extract compelling pull-quotes from document text."""
    
    if not text:
        return []
    
    # Split into sentences
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    
    # Score sentences for quote-worthiness
    scored_sentences = []
    for sentence in sentences[:50]:  # Check first 50 sentences
        score = _score_quote_sentence(sentence)
        if score > 0.3:  # Minimum threshold
            scored_sentences.append((score, sentence))
    
    # Sort by score and take top quotes
    scored_sentences.sort(reverse=True, key=lambda x: x[0])
    
    quotes = []
    for _, sentence in scored_sentences[:max_quotes]:
        # Truncate if too long
        if len(sentence) > 280:
            sentence = sentence[:277] + "..."
        quotes.append(sentence)
    
    return quotes


def _score_quote_sentence(sentence: str) -> float:
    """Score a sentence for its value as a pull-quote."""
    
    score = 0.0
    
    # Length scoring (prefer medium-length sentences)
    length = len(sentence)
    if 50 <= length <= 200:
        score += 0.3
    elif 200 < length <= 280:
        score += 0.2
    else:
        score -= 0.1
    
    # Content scoring
    # Prefer sentences with specific information
    if re.search(r'\b\d{4}\b', sentence):  # Contains year
        score += 0.2
    if re.search(r'\b\d+%\b', sentence):  # Contains percentage
        score += 0.2
    if re.search(r'\$\d+', sentence):  # Contains money
        score += 0.15
    
    # Prefer factual language
    factual_indicators = ['according to', 'reported', 'study shows', 'data indicates', 'research found']
    if any(indicator in sentence.lower() for indicator in factual_indicators):
        score += 0.15
    
    # Avoid certain types of sentences
    if sentence.startswith(('This ', 'These ', 'It ', 'They ')):
        score -= 0.1
    if '?' in sentence:  # Questions are less good as quotes
        score -= 0.1
    
    return max(0.0, score)


def _assess_confidence(answer: str, documents: List[ScrapedDoc]) -> str:
    """Assess confidence level of the synthesized answer."""
    
    # Count authoritative sources
    gov_edu_count = sum(1 for doc in documents if any(domain in (doc.domain or "") for domain in ['.gov', '.edu', '.europa.eu']))
    
    # Count recent sources (last 2 years)
    recent_count = 0
    current_year = 2024
    for doc in documents:
        if doc.published_at_guess and str(current_year-1) in doc.published_at_guess or str(current_year) in doc.published_at_guess:
            recent_count += 1
    
    # Count citations in answer
    citations = len(re.findall(r'\[\d+\]', answer))
    
    # Confidence assessment
    if gov_edu_count >= 3 and citations >= 5 and recent_count >= 2:
        return "high"
    elif gov_edu_count >= 1 and citations >= 3:
        return "medium"
    else:
        return "low"
