"""Information synthesis and analysis module."""

import asyncio
import re
from typing import List, Dict, Any
import json
from datetime import datetime
from collections import Counter
from urllib.parse import urlparse

from .models import ExtractedContent, ProcessedSource, QueryAnalysis, QueryType, ResearchMetadata
from .config import settings


class InformationSynthesizer:
    """Synthesizes information from multiple sources into comprehensive answers."""
    
    def __init__(self):
        # Common words to ignore in relevance calculation
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'about', 'is', 'are', 'was', 'were', 'be', 'been',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these',
            'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him',
            'her', 'us', 'them', 'my', 'your', 'his', 'its', 'our', 'their'
        }
    
    async def synthesize_research(
        self,
        query_analysis: QueryAnalysis,
        extracted_contents: List[ExtractedContent]
    ) -> Dict[str, Any]:
        """Synthesize research from extracted content."""
        
        # First, process and rank sources
        processed_sources = await self._process_sources(
            extracted_contents, query_analysis.original_query
        )
        
        # Filter sources by quality and relevance
        quality_sources = self._filter_quality_sources(processed_sources)
        
        # Generate comprehensive answer
        answer = await self._generate_answer(query_analysis, quality_sources)
        
        # Generate follow-up suggestions
        follow_ups = await self._generate_follow_ups(query_analysis, answer)
        
        # Calculate metadata
        metadata = self._calculate_metadata(query_analysis, extracted_contents, quality_sources)
        
        return {
            "answer": answer,
            "sources": quality_sources,
            "follow_up_suggestions": follow_ups,
            "metadata": metadata
        }
    
    async def _process_sources(
        self,
        extracted_contents: List[ExtractedContent],
        original_query: str
    ) -> List[ProcessedSource]:
        """Process and evaluate source quality."""
        processed_sources = []
        
        for content in extracted_contents:
            if not content.extraction_success or len(content.content) < settings.min_content_length:
                continue
            
            # Calculate relevance score
            relevance_score = await self._calculate_relevance(content, original_query)
            
            if relevance_score < settings.min_relevance_score:
                continue
            
            # Extract key findings
            key_findings = await self._extract_key_findings(content, original_query)
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(content)
            
            processed_source = ProcessedSource(
                title=content.title,
                url=content.url,
                relevance_score=relevance_score,
                key_findings=key_findings,
                domain=urlparse(str(content.url)).netloc,
                last_updated=content.metadata.get('published_date'),
                content_length=len(content.content),
                quality_score=quality_score
            )
            
            processed_sources.append(processed_source)
        
        # Sort by combined relevance and quality score
        processed_sources.sort(
            key=lambda x: x.relevance_score * 0.7 + x.quality_score * 0.3,
            reverse=True
        )
        
        return processed_sources
    
    async def _calculate_relevance(self, content: ExtractedContent, query: str) -> float:
        """Calculate relevance score using keyword matching and content analysis."""
        
        # Tokenize query and content
        query_words = self._tokenize_text(query.lower())
        content_words = self._tokenize_text(content.content.lower())
        title_words = self._tokenize_text(content.title.lower())
        
        # Calculate different types of relevance
        keyword_relevance = self._calculate_keyword_relevance(query_words, content_words)
        title_relevance = self._calculate_keyword_relevance(query_words, title_words)
        semantic_relevance = self._calculate_semantic_relevance(query, content.content)
        
        # Weighted combination
        relevance_score = (
            keyword_relevance * 0.4 +
            title_relevance * 0.3 +
            semantic_relevance * 0.3
        )
        
        return max(0.0, min(1.0, relevance_score))
    
    def _tokenize_text(self, text: str) -> List[str]:
        """Tokenize text into meaningful words."""
        words = re.findall(r'\b[a-z]+\b', text)
        return [word for word in words if word not in self.stop_words and len(word) > 2]
    
    def _calculate_keyword_relevance(self, query_words: List[str], content_words: List[str]) -> float:
        """Calculate relevance based on keyword overlap."""
        if not query_words:
            return 0.0
        
        content_word_set = set(content_words)
        matched_words = sum(1 for word in query_words if word in content_word_set)
        
        return matched_words / len(query_words)
    
    def _calculate_semantic_relevance(self, query: str, content: str) -> float:
        """Calculate semantic relevance using simple heuristics."""
        
        # Look for exact phrase matches (higher weight)
        query_phrases = self._extract_phrases(query)
        content_lower = content.lower()
        
        phrase_matches = sum(1 for phrase in query_phrases if phrase in content_lower)
        phrase_score = min(1.0, phrase_matches / max(len(query_phrases), 1))
        
        # Look for related terms and contexts
        context_score = 0.0
        if len(content) > 100:  # Only if content is substantial
            # Simple context indicators
            if any(word in content_lower for word in ['according to', 'research shows', 'study found']):
                context_score += 0.2
            if any(word in content_lower for word in ['data', 'statistics', 'percent', '%']):
                context_score += 0.1
            if any(word in content_lower for word in ['expert', 'specialist', 'professional']):
                context_score += 0.1
        
        return min(1.0, phrase_score * 0.7 + context_score * 0.3)
    
    def _extract_phrases(self, text: str) -> List[str]:
        """Extract meaningful phrases from text."""
        # Simple phrase extraction (2-3 word combinations)
        words = text.lower().split()
        phrases = []
        
        for i in range(len(words) - 1):
            if len(words[i]) > 2 and len(words[i + 1]) > 2:
                phrases.append(f"{words[i]} {words[i + 1]}")
        
        return phrases
    
    async def _extract_key_findings(self, content: ExtractedContent, query: str) -> str:
        """Extract key findings relevant to the query using rule-based extraction."""
        
        # Split content into sentences
        sentences = self._split_into_sentences(content.content)
        
        # Score sentences based on relevance to query
        scored_sentences = []
        query_words = set(self._tokenize_text(query.lower()))
        
        for sentence in sentences:
            if len(sentence.strip()) < 20:  # Skip very short sentences
                continue
                
            sentence_words = set(self._tokenize_text(sentence.lower()))
            
            # Calculate sentence relevance
            word_overlap = len(query_words.intersection(sentence_words))
            sentence_score = word_overlap / max(len(query_words), 1)
            
            # Boost sentences with important indicators
            if any(indicator in sentence.lower() for indicator in 
                   ['according to', 'research shows', 'study found', 'data shows', 'results indicate']):
                sentence_score += 0.3
            
            # Boost sentences with numbers/statistics
            if re.search(r'\d+%|\d+\.\d+%|\$\d+|\d+ percent', sentence):
                sentence_score += 0.2
            
            scored_sentences.append((sentence_score, sentence))
        
        # Sort by score and take top sentences
        scored_sentences.sort(reverse=True, key=lambda x: x[0])
        
        # Take top 2-3 sentences, but limit total length
        key_findings = []
        total_length = 0
        max_length = 400
        
        for score, sentence in scored_sentences[:5]:  # Check top 5
            if score > 0.1 and total_length + len(sentence) <= max_length:
                key_findings.append(sentence.strip())
                total_length += len(sentence)
            
            if len(key_findings) >= 3:  # Max 3 sentences
                break
        
        if not key_findings:
            # Fallback to first few sentences
            return '. '.join(sentences[:2])[:400] + "..."
        
        return ' '.join(key_findings)
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences using simple rules."""
        # Simple sentence splitting on periods, exclamation marks, question marks
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _calculate_quality_score(self, content: ExtractedContent) -> float:
        """Calculate source quality score based on various factors."""
        score = 0.5  # Base score
        
        # Domain authority (simplified)
        domain = urlparse(str(content.url)).netloc.lower()
        if any(auth_domain in domain for auth_domain in ['.edu', '.gov', '.org']):
            score += 0.2
        elif any(news_domain in domain for news_domain in ['reuters.com', 'bbc.com', 'nytimes.com']):
            score += 0.15
        
        # Content length (optimal range)
        content_length = len(content.content)
        if 1000 <= content_length <= 5000:
            score += 0.1
        elif content_length < 500:
            score -= 0.1
        
        # Has metadata
        if content.metadata:
            score += 0.05
            if 'published_date' in content.metadata:
                score += 0.05
        
        # Fast extraction (indicates well-structured content)
        if content.extraction_time < 2.0:
            score += 0.05
        
        return max(0.0, min(1.0, score))
    
    def _filter_quality_sources(self, processed_sources: List[ProcessedSource]) -> List[ProcessedSource]:
        """Filter sources by quality thresholds."""
        # Take top sources based on combined score
        quality_sources = [
            source for source in processed_sources
            if source.relevance_score >= settings.min_relevance_score
        ]
        
        return quality_sources[:settings.max_sources_per_query]
    
    async def _generate_answer(
        self,
        query_analysis: QueryAnalysis,
        sources: List[ProcessedSource]
    ) -> str:
        """Generate comprehensive answer from processed sources using rule-based synthesis."""
        
        if not sources:
            return f"I couldn't find sufficient reliable sources to answer your question about '{query_analysis.original_query}'. Please try rephrasing your query or making it more specific."
        
        # Organize information by themes/topics
        all_findings = []
        for source in sources[:8]:  # Use top 8 sources
            all_findings.extend(self._split_into_sentences(source.key_findings))
        
        # Group similar findings
        grouped_findings = self._group_similar_findings(all_findings, query_analysis.original_query)
        
        # Generate answer based on query type
        if query_analysis.query_type == QueryType.LIST:
            return self._generate_list_answer(query_analysis, grouped_findings, sources)
        elif query_analysis.query_type == QueryType.COMPARISON:
            return self._generate_comparison_answer(query_analysis, grouped_findings, sources)
        elif query_analysis.query_type == QueryType.HOW_TO:
            return self._generate_howto_answer(query_analysis, grouped_findings, sources)
        elif query_analysis.query_type == QueryType.ANALYSIS:
            return self._generate_analysis_answer(query_analysis, grouped_findings, sources)
        else:
            return self._generate_factual_answer(query_analysis, grouped_findings, sources)
    
    def _group_similar_findings(self, findings: List[str], query: str) -> Dict[str, List[str]]:
        """Group similar findings into themes."""
        groups = {"main_findings": [], "details": [], "statistics": []}
        
        query_words = set(self._tokenize_text(query.lower()))
        
        for finding in findings:
            finding = finding.strip()
            if len(finding) < 10:
                continue
                
            finding_words = set(self._tokenize_text(finding.lower()))
            relevance = len(query_words.intersection(finding_words)) / max(len(query_words), 1)
            
            # Categorize findings
            if re.search(r'\d+%|\d+\.\d+%|\$\d+|\d+ percent|\d+,\d+', finding):
                groups["statistics"].append(finding)
            elif relevance > 0.3:
                groups["main_findings"].append(finding)
            else:
                groups["details"].append(finding)
        
        return groups
    
    def _generate_list_answer(self, query_analysis: QueryAnalysis, grouped_findings: Dict, sources: List[ProcessedSource]) -> str:
        """Generate a list-style answer."""
        answer_parts = [f"Based on research from {len(sources)} sources, here's what I found about {query_analysis.original_query}:"]
        
        # Add main findings as list items
        if grouped_findings["main_findings"]:
            answer_parts.append("\nKey findings:")
            for i, finding in enumerate(grouped_findings["main_findings"][:6], 1):
                answer_parts.append(f"{i}. {finding}")
        
        # Add statistics if available
        if grouped_findings["statistics"]:
            answer_parts.append("\nRelevant data:")
            for stat in grouped_findings["statistics"][:3]:
                answer_parts.append(f"• {stat}")
        
        # Add additional details
        if grouped_findings["details"]:
            answer_parts.append(f"\nAdditional information:")
            answer_parts.append(grouped_findings["details"][0])
        
        return "\n".join(answer_parts)
    
    def _generate_comparison_answer(self, query_analysis: QueryAnalysis, grouped_findings: Dict, sources: List[ProcessedSource]) -> str:
        """Generate a comparison-style answer."""
        answer_parts = [f"Here's a comparison based on research about {query_analysis.original_query}:"]
        
        # Try to identify comparison points
        findings = grouped_findings["main_findings"] + grouped_findings["details"]
        
        advantages = [f for f in findings if any(word in f.lower() for word in ['advantage', 'benefit', 'better', 'superior', 'pros'])]
        disadvantages = [f for f in findings if any(word in f.lower() for word in ['disadvantage', 'drawback', 'worse', 'inferior', 'cons'])]
        
        if advantages:
            answer_parts.append("\nAdvantages/Benefits:")
            for adv in advantages[:3]:
                answer_parts.append(f"• {adv}")
        
        if disadvantages:
            answer_parts.append("\nDisadvantages/Limitations:")
            for dis in disadvantages[:3]:
                answer_parts.append(f"• {dis}")
        
        # Add other findings
        other_findings = [f for f in findings if f not in advantages and f not in disadvantages]
        if other_findings:
            answer_parts.append("\nAdditional considerations:")
            for finding in other_findings[:3]:
                answer_parts.append(f"• {finding}")
        
        return "\n".join(answer_parts)
    
    def _generate_howto_answer(self, query_analysis: QueryAnalysis, grouped_findings: Dict, sources: List[ProcessedSource]) -> str:
        """Generate a how-to style answer."""
        answer_parts = [f"Here's guidance on {query_analysis.original_query}:"]
        
        # Look for step-like content
        findings = grouped_findings["main_findings"] + grouped_findings["details"]
        steps = [f for f in findings if any(word in f.lower() for word in ['step', 'first', 'then', 'next', 'finally', 'process'])]
        
        if steps:
            answer_parts.append("\nProcess/Steps:")
            for i, step in enumerate(steps[:5], 1):
                answer_parts.append(f"{i}. {step}")
        
        # Add general guidance
        other_findings = [f for f in findings if f not in steps]
        if other_findings:
            answer_parts.append("\nKey considerations:")
            for finding in other_findings[:4]:
                answer_parts.append(f"• {finding}")
        
        return "\n".join(answer_parts)
    
    def _generate_analysis_answer(self, query_analysis: QueryAnalysis, grouped_findings: Dict, sources: List[ProcessedSource]) -> str:
        """Generate an analysis-style answer."""
        answer_parts = [f"Analysis of {query_analysis.original_query}:"]
        
        # Add main analysis points
        if grouped_findings["main_findings"]:
            answer_parts.append("\nKey insights:")
            for finding in grouped_findings["main_findings"][:4]:
                answer_parts.append(f"• {finding}")
        
        # Add supporting data
        if grouped_findings["statistics"]:
            answer_parts.append("\nSupporting data:")
            for stat in grouped_findings["statistics"][:3]:
                answer_parts.append(f"• {stat}")
        
        # Add implications
        if grouped_findings["details"]:
            answer_parts.append("\nImplications:")
            for detail in grouped_findings["details"][:2]:
                answer_parts.append(f"• {detail}")
        
        return "\n".join(answer_parts)
    
    def _generate_factual_answer(self, query_analysis: QueryAnalysis, grouped_findings: Dict, sources: List[ProcessedSource]) -> str:
        """Generate a factual answer."""
        answer_parts = [f"Based on current information about {query_analysis.original_query}:"]
        
        # Add main facts
        if grouped_findings["main_findings"]:
            answer_parts.append("")
            for finding in grouped_findings["main_findings"][:4]:
                answer_parts.append(finding)
                answer_parts.append("")
        
        # Add statistics
        if grouped_findings["statistics"]:
            answer_parts.append("Key statistics:")
            for stat in grouped_findings["statistics"][:3]:
                answer_parts.append(f"• {stat}")
        
        return "\n".join(answer_parts)
    
    async def _generate_follow_ups(
        self,
        query_analysis: QueryAnalysis,
        answer: str
    ) -> List[str]:
        """Generate follow-up questions based on query type and content."""
        
        base_query = query_analysis.original_query
        key_entities = query_analysis.key_entities
        
        follow_ups = []
        
        if query_analysis.query_type == QueryType.LIST:
            follow_ups = [
                f"What are the costs associated with {base_query}?",
                f"How do I evaluate the best options for {base_query}?",
                f"What are the pros and cons of different {base_query}?",
                f"Where can I find more detailed information about {base_query}?"
            ]
        elif query_analysis.query_type == QueryType.COMPARISON:
            follow_ups = [
                f"What factors should I consider when choosing between {base_query}?",
                f"What do experts recommend for {base_query}?",
                f"Are there any new developments in {base_query}?",
                f"What are the long-term implications of {base_query}?"
            ]
        elif query_analysis.query_type == QueryType.HOW_TO:
            follow_ups = [
                f"What tools or resources do I need for {base_query}?",
                f"What are common mistakes to avoid with {base_query}?",
                f"How long does it typically take to {base_query}?",
                f"What are the best practices for {base_query}?"
            ]
        elif query_analysis.query_type == QueryType.ANALYSIS:
            follow_ups = [
                f"What are the future trends for {base_query}?",
                f"How does {base_query} compare to previous years?",
                f"What factors are driving changes in {base_query}?",
                f"What are experts predicting about {base_query}?"
            ]
        else:  # FACTUAL
            follow_ups = [
                f"What are the latest updates on {base_query}?",
                f"How does {base_query} work in practice?",
                f"What are common misconceptions about {base_query}?",
                f"Where can I find official information about {base_query}?"
            ]
        
        # Customize with entities if available
        if key_entities and len(key_entities) > 0:
            entity = key_entities[0]
            follow_ups.append(f"What other {entity.lower()} options should I consider?")
        
        return follow_ups[:4]
    
    def _calculate_metadata(
        self,
        query_analysis: QueryAnalysis,
        extracted_contents: List[ExtractedContent],
        quality_sources: List[ProcessedSource]
    ) -> ResearchMetadata:
        """Calculate research metadata."""
        avg_relevance = sum(s.relevance_score for s in quality_sources) / len(quality_sources) if quality_sources else 0
        
        return ResearchMetadata(
            sources_searched=len(extracted_contents),
            sources_processed=len(quality_sources),
            research_time_seconds=sum(c.extraction_time for c in extracted_contents),
            confidence_score=min(1.0, avg_relevance * 1.2),  # Boost confidence slightly
            query_type=query_analysis.query_type,
            sub_questions=query_analysis.sub_questions
        )
    
# Domain extraction is already imported at top