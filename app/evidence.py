"""Evidence matrix building and validation."""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from .models import ScrapedDoc
from .utils import log_structured


@dataclass
class EvidenceEntry:
    """Single evidence entry linking claim to source."""
    claim: str
    supporting_quote: str
    source_id: int
    source_url: str
    source_title: str
    source_date: str
    confidence: str  # "high", "medium", "low"


def build_evidence_matrix(answer: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build evidence matrix mapping claims to supporting sources.
    
    Args:
        answer: Synthesized answer text with citations
        sources: List of source documents with metadata
        
    Returns:
        List of evidence entries showing claim -> quote -> source mapping
    """
    
    # Extract claims and their citations from the answer
    claims_with_citations = _extract_claims_with_citations(answer)
    
    evidence_matrix = []
    
    for claim_text, citation_numbers in claims_with_citations:
        # For each citation in the claim, try to find supporting quote
        for citation_num in citation_numbers:
            try:
                source_id = int(citation_num)
                if 1 <= source_id <= len(sources):
                    source = sources[source_id - 1]  # 0-indexed
                    
                    # Find best supporting quote from source
                    supporting_quote = _find_supporting_quote(claim_text, source.get('pull_quotes', []))
                    
                    if supporting_quote:
                        evidence_entry = {
                            "claim": claim_text[:200] + "..." if len(claim_text) > 200 else claim_text,
                            "supporting_quote": supporting_quote,
                            "source_id": source_id,
                            "source_url": source.get('url', ''),
                            "source_title": source.get('title', 'Untitled'),
                            "source_date": source.get('published_date', 'Unknown'),
                            "confidence": _assess_evidence_confidence(claim_text, supporting_quote, source)
                        }
                        evidence_matrix.append(evidence_entry)
            except (ValueError, IndexError):
                continue
    
    log_structured("evidence_matrix_built", {
        "claims_processed": len(claims_with_citations),
        "evidence_entries": len(evidence_matrix),
        "high_confidence": sum(1 for e in evidence_matrix if e['confidence'] == 'high'),
        "medium_confidence": sum(1 for e in evidence_matrix if e['confidence'] == 'medium'),
        "low_confidence": sum(1 for e in evidence_matrix if e['confidence'] == 'low')
    })
    
    return evidence_matrix


def validate_answer(answer: str, evidence_matrix: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Validate answer against evidence matrix to find unsupported claims.
    
    Args:
        answer: The synthesized answer
        evidence_matrix: Evidence matrix from build_evidence_matrix
        
    Returns:
        List of validation issues (empty if all claims are supported)
    """
    
    issues = []
    
    # Extract all claims from answer
    sentences = _extract_sentences(answer)
    
    for sentence in sentences:
        # Skip non-factual sentences (questions, introductions, etc.)
        if _is_factual_claim(sentence):
            # Check if this claim has supporting evidence
            has_support = _claim_has_evidence_support(sentence, evidence_matrix)
            
            if not has_support:
                issues.append({
                    "claim": sentence,
                    "issue": "No supporting evidence found",
                    "severity": "medium"
                })
    
    # Check for citation mismatches
    citations = re.findall(r'\[(\d+)\]', answer)
    unique_citations = set(citations)
    
    for citation in unique_citations:
        citation_has_evidence = any(
            str(entry['source_id']) == citation 
            for entry in evidence_matrix
        )
        
        if not citation_has_evidence:
            issues.append({
                "claim": f"Citation [{citation}] referenced but no evidence found",
                "issue": "Missing citation evidence",
                "severity": "high"
            })
    
    # Check for low-confidence evidence clusters
    low_confidence_count = sum(1 for e in evidence_matrix if e['confidence'] == 'low')
    total_evidence = len(evidence_matrix)
    
    if total_evidence > 0 and (low_confidence_count / total_evidence) > 0.5:
        issues.append({
            "claim": "Overall answer reliability",
            "issue": f"High proportion of low-confidence evidence ({low_confidence_count}/{total_evidence})",
            "severity": "medium"
        })
    
    log_structured("answer_validation", {
        "sentences_checked": len(sentences),
        "issues_found": len(issues),
        "high_severity": sum(1 for i in issues if i['severity'] == 'high'),
        "medium_severity": sum(1 for i in issues if i['severity'] == 'medium')
    })
    
    return issues


def _extract_claims_with_citations(answer: str) -> List[Tuple[str, List[str]]]:
    """Extract factual claims and their associated citations."""
    
    claims = []
    
    # Split into sentences and look for citations
    sentences = _extract_sentences(answer)
    
    for sentence in sentences:
        if _is_factual_claim(sentence):
            # Find all citations in this sentence
            citations = re.findall(r'\[(\d+)\]', sentence)
            if citations:
                # Clean sentence of citations for claim text
                clean_sentence = re.sub(r'\[\d+\]', '', sentence).strip()
                claims.append((clean_sentence, citations))
    
    return claims


def _extract_sentences(text: str) -> List[str]:
    """Extract sentences from text."""
    
    # Split on sentence endings, but be careful with abbreviations
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    # Clean and filter sentences
    cleaned_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) > 10 and not sentence.startswith('Sources'):
            cleaned_sentences.append(sentence)
    
    return cleaned_sentences


def _is_factual_claim(sentence: str) -> bool:
    """Determine if a sentence contains factual claims that need evidence."""
    
    # Skip questions
    if '?' in sentence:
        return False
    
    # Skip transition/introductory phrases
    intro_phrases = [
        'in conclusion', 'to summarize', 'overall', 'in summary',
        'this suggests', 'this indicates', 'for example', 'for instance'
    ]
    
    if any(phrase in sentence.lower() for phrase in intro_phrases):
        return False
    
    # Look for factual indicators
    factual_indicators = [
        'is', 'are', 'was', 'were', 'has', 'have', 'had',
        'will', 'would', 'shows', 'indicates', 'reports',
        'according to', 'data', 'study', 'research'
    ]
    
    return any(indicator in sentence.lower() for indicator in factual_indicators)


def _find_supporting_quote(claim: str, pull_quotes: List[str]) -> Optional[str]:
    """Find the best supporting quote for a claim."""
    
    if not pull_quotes:
        return None
    
    claim_words = set(_normalize_text(claim).split())
    
    best_quote = None
    best_overlap = 0
    
    for quote in pull_quotes:
        quote_words = set(_normalize_text(quote).split())
        overlap = len(claim_words & quote_words)
        
        if overlap > best_overlap and overlap >= 2:  # Minimum 2 word overlap
            best_overlap = overlap
            best_quote = quote
    
    return best_quote


def _normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    
    # Convert to lowercase and remove punctuation
    normalized = re.sub(r'[^\w\s]', ' ', text.lower())
    
    # Remove extra whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized


def _claim_has_evidence_support(claim: str, evidence_matrix: List[Dict[str, Any]]) -> bool:
    """Check if a claim has supporting evidence in the matrix."""
    
    claim_words = set(_normalize_text(claim).split())
    
    for evidence_entry in evidence_matrix:
        evidence_claim_words = set(_normalize_text(evidence_entry['claim']).split())
        
        # Check for significant word overlap
        overlap = len(claim_words & evidence_claim_words)
        
        if overlap >= max(2, len(claim_words) * 0.3):  # 30% overlap or minimum 2 words
            return True
    
    return False


def _assess_evidence_confidence(claim: str, supporting_quote: str, source: Dict[str, Any]) -> str:
    """Assess confidence level of evidence."""
    
    # Source authority factor
    domain = source.get('domain', '').lower()
    authority_score = 0
    
    if any(d in domain for d in ['.gov', '.mil']):
        authority_score = 3
    elif any(d in domain for d in ['.edu', '.europa.eu']):
        authority_score = 2.5
    elif any(d in domain for d in ['.org', '.int']):
        authority_score = 2
    elif any(name in domain for name in ['reuters', 'bbc', 'economist']):
        authority_score = 1.5
    else:
        authority_score = 1
    
    # Recency factor
    recency_score = 1
    date_str = source.get('published_date', '')
    if '2024' in date_str or '2023' in date_str:
        recency_score = 1.5
    elif '2022' in date_str:
        recency_score = 1.2
    
    # Quote relevance factor
    quote_relevance = 1
    if supporting_quote:
        claim_words = set(_normalize_text(claim).split())
        quote_words = set(_normalize_text(supporting_quote).split())
        overlap_ratio = len(claim_words & quote_words) / max(len(claim_words), 1)
        quote_relevance = min(1.5, 0.5 + overlap_ratio)
    
    # Calculate final confidence score
    confidence_score = authority_score * recency_score * quote_relevance
    
    if confidence_score >= 4.0:
        return "high"
    elif confidence_score >= 2.5:
        return "medium"
    else:
        return "low"
