"""Query analysis and planning module."""

import asyncio
import re
from typing import List, Dict, Set
from .models import QueryAnalysis, QueryType
from .config import settings


class QueryAnalyzer:
    """Analyzes user queries and generates research strategies."""
    
    def __init__(self):
        # Keywords for different query types
        self.query_type_patterns = {
            QueryType.LIST: [
                "find", "list", "show me", "what are", "examples of", "types of",
                "companies that", "businesses", "services", "products"
            ],
            QueryType.COMPARISON: [
                "compare", "vs", "versus", "difference between", "better than",
                "pros and cons", "advantages", "disadvantages"
            ],
            QueryType.HOW_TO: [
                "how to", "how do", "how can", "steps to", "guide to",
                "tutorial", "instructions", "process"
            ],
            QueryType.ANALYSIS: [
                "analyze", "analysis", "why", "what causes", "impact of",
                "effects of", "implications", "trends", "future of"
            ]
        }
        
        # Common expansion terms
        self.expansion_terms = {
            "business": ["company", "corporation", "enterprise", "firm", "organization"],
            "small": ["startup", "SME", "local", "independent", "boutique"],
            "sustainable": ["eco-friendly", "green", "environmentally friendly", "renewable"],
            "technology": ["tech", "digital", "software", "hardware", "IT"],
        }
    
    async def analyze_query(self, query: str) -> QueryAnalysis:
        """Analyze a user query to determine research strategy."""
        
        # Use rule-based analysis instead of LLM
        query_lower = query.lower()
        
        # Determine query type
        query_type = self._determine_query_type(query_lower)
        
        # Extract key entities
        key_entities = self._extract_entities(query)
        
        # Generate sub-questions
        sub_questions = self._generate_sub_questions(query, query_type, key_entities)
        
        # Generate search terms
        search_terms = self._generate_search_terms(query, key_entities, query_type)
        
        # Determine intent
        intent = self._determine_intent(query, query_type)
        
        return QueryAnalysis(
            original_query=query,
            query_type=query_type,
            key_entities=key_entities,
            sub_questions=sub_questions,
            search_terms=search_terms,
            intent=intent
        )
    
    def _determine_query_type(self, query_lower: str) -> QueryType:
        """Determine the type of query based on keywords."""
        for query_type, patterns in self.query_type_patterns.items():
            if any(pattern in query_lower for pattern in patterns):
                return query_type
        return QueryType.FACTUAL
    
    def _extract_entities(self, query: str) -> List[str]:
        """Extract key entities from the query using simple NLP."""
        # Remove common stop words and extract meaningful terms
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "about", "what", "are", "is", "find", "me", "that"
        }
        
        # Extract words that are likely entities
        words = re.findall(r'\b[A-Za-z]+\b', query.lower())
        entities = []
        
        for word in words:
            if (len(word) > 3 and 
                word not in stop_words and 
                not word.endswith('ing') and 
                not word.endswith('ed')):
                entities.append(word.capitalize())
        
        # Look for proper nouns (capitalized words in original query)
        proper_nouns = re.findall(r'\b[A-Z][a-z]+\b', query)
        entities.extend(proper_nouns)
        
        return list(set(entities))[:10]  # Limit to top 10 entities
    
    def _generate_sub_questions(self, query: str, query_type: QueryType, entities: List[str]) -> List[str]:
        """Generate sub-questions based on query type and entities."""
        sub_questions = []
        
        if query_type == QueryType.LIST:
            if entities:
                sub_questions = [
                    f"What are the best {entities[0].lower()} options?",
                    f"Where can I find reliable {entities[0].lower()}?",
                    f"What criteria should I use to evaluate {entities[0].lower()}?",
                    f"What are recent developments in {entities[0].lower()}?"
                ]
            else:
                sub_questions = [
                    "What are the main options available?",
                    "What are the key characteristics?",
                    "Where can I find more information?",
                    "What should I consider when choosing?"
                ]
        elif query_type == QueryType.COMPARISON:
            sub_questions = [
                "What are the main differences?",
                "What are the advantages and disadvantages?",
                "Which option is better for specific use cases?",
                "What do experts recommend?"
            ]
        elif query_type == QueryType.HOW_TO:
            sub_questions = [
                "What are the step-by-step instructions?",
                "What tools or resources are needed?",
                "What are common mistakes to avoid?",
                "What are best practices?"
            ]
        elif query_type == QueryType.ANALYSIS:
            sub_questions = [
                "What are the current trends?",
                "What factors contribute to this?",
                "What are the implications?",
                "What do experts predict for the future?"
            ]
        else:  # FACTUAL
            sub_questions = [
                f"What is {query}?",
                "What are the key facts?",
                "What is the current status?",
                "What are reliable sources?"
            ]
        
        return sub_questions[:5]  # Limit to 5 sub-questions
    
    def _generate_search_terms(self, query: str, entities: List[str], query_type: QueryType) -> List[str]:
        """Generate diverse search terms for comprehensive coverage."""
        search_terms = [query]  # Start with original query
        
        # Add variations with synonyms
        for entity in entities[:3]:  # Use top 3 entities
            if entity.lower() in self.expansion_terms:
                for synonym in self.expansion_terms[entity.lower()]:
                    search_terms.append(query.replace(entity, synonym))
        
        # Add query type specific variations
        if query_type == QueryType.LIST:
            search_terms.extend([
                f"{query} list",
                f"{query} directory",
                f"{query} examples",
                f"top {query}",
                f"best {query}"
            ])
        elif query_type == QueryType.COMPARISON:
            search_terms.extend([
                f"{query} comparison",
                f"{query} vs",
                f"{query} pros and cons",
                f"{query} review"
            ])
        elif query_type == QueryType.HOW_TO:
            search_terms.extend([
                f"{query} guide",
                f"{query} tutorial",
                f"{query} step by step",
                f"{query} instructions"
            ])
        elif query_type == QueryType.ANALYSIS:
            search_terms.extend([
                f"{query} analysis",
                f"{query} trends",
                f"{query} research",
                f"{query} study"
            ])
        
        # Add informational variations
        search_terms.extend([
            f"{query} information",
            f"{query} overview",
            f"{query} facts",
            f"what is {query}",
            f"{query} 2024",  # Recent information
            f"{query} latest"
        ])
        
        # Remove duplicates and return up to 12 terms
        return list(set(search_terms))[:12]
    
    def _determine_intent(self, query: str, query_type: QueryType) -> str:
        """Determine user intent based on query and type."""
        intent_templates = {
            QueryType.LIST: "User wants to find a comprehensive list or directory",
            QueryType.COMPARISON: "User wants to compare options and understand differences",
            QueryType.HOW_TO: "User wants step-by-step instructions or guidance",
            QueryType.ANALYSIS: "User wants analytical insights and expert perspectives",
            QueryType.FACTUAL: "User wants factual information and current data"
        }
        
        base_intent = intent_templates.get(query_type, "User wants information")
        return f"{base_intent} about: {query}"