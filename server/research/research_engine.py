"""Main research engine that orchestrates the entire research process."""

import asyncio
import time
from typing import Dict, Any

from .models import ResearchRequest, ResearchResponse
from .query_analyzer import QueryAnalyzer
from .search_engine import SearchEngine
from .content_extractor import ContentExtractor
from .synthesizer import InformationSynthesizer


class ResearchEngine:
    """Main research engine that coordinates the research process."""
    
    def __init__(self):
        self.query_analyzer = QueryAnalyzer()
        self.synthesizer = InformationSynthesizer()
    
    async def research(self, request: ResearchRequest) -> ResearchResponse:
        """Execute the complete research process."""
        start_time = time.time()
        
        try:
            # Step 1: Analyze the query
            print(f"🔍 Analyzing query: {request.query}")
            query_analysis = await self.query_analyzer.analyze_query(request.query)
            
            # Step 2: Execute searches
            print(f"🔎 Searching with {len(query_analysis.search_terms)} queries")
            search_results = []
            
            async with SearchEngine() as search_engine:
                search_results = await search_engine.search_multiple_queries(
                    query_analysis.search_terms
                )
            
            print(f"📄 Found {len(search_results)} search results")
            
            # Step 3: Extract content from sources
            print(f"🌐 Extracting content from {len(search_results)} sources")
            extracted_contents = []
            
            async with ContentExtractor() as content_extractor:
                extracted_contents = await content_extractor.extract_multiple_sources(
                    search_results[:request.options.max_sources]
                )
            
            successful_extractions = [c for c in extracted_contents if c.extraction_success]
            print(f"✅ Successfully extracted content from {len(successful_extractions)} sources")
            
            # Step 4: Synthesize information
            print(f"🧠 Synthesizing research results")
            synthesis_results = await self.synthesizer.synthesize_research(
                query_analysis, successful_extractions
            )
            
            total_time = time.time() - start_time
            synthesis_results["metadata"].research_time_seconds = total_time
            
            # Build the response
            response = ResearchResponse(
                query=request.query,
                answer=synthesis_results["answer"],
                research_metadata=synthesis_results["metadata"],
                sources=synthesis_results["sources"],
                follow_up_suggestions=synthesis_results["follow_up_suggestions"]
            )
            
            print(f"🎉 Research complete in {total_time:.1f}s")
            return response
            
        except Exception as e:
            print(f"❌ Research failed: {e}")
            # Return error response
            from .models import ResearchMetadata, QueryType
            
            error_metadata = ResearchMetadata(
                sources_searched=0,
                sources_processed=0,
                research_time_seconds=time.time() - start_time,
                confidence_score=0.0,
                query_type=QueryType.FACTUAL,
                sub_questions=[]
            )
            
            return ResearchResponse(
                query=request.query,
                answer=f"I apologize, but I encountered an error during research: {str(e)}. Please try again with a different query or check your API configuration.",
                research_metadata=error_metadata,
                sources=[],
                follow_up_suggestions=[
                    "Try rephrasing your question",
                    "Make your query more specific",
                    "Check if the topic requires specialized knowledge"
                ]
            )