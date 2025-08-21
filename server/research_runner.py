#!/usr/bin/env python3
"""
Standalone Python script that runs the research engine.
This script reads JSON from stdin and outputs JSON to stdout.
"""

import sys
import json
import asyncio
from pathlib import Path

# Add the research module to the path
sys.path.insert(0, str(Path(__file__).parent))

from research.research_engine import ResearchEngine
from research.models import ResearchRequest, ResearchOptions


async def main():
    try:
        # Read input from stdin
        input_data = sys.stdin.read()
        request_data = json.loads(input_data)
        
        # Create research request
        options = ResearchOptions(**request_data.get("options", {}))
        request = ResearchRequest(
            query=request_data["query"],
            options=options
        )
        
        # Execute research
        research_engine = ResearchEngine()
        result = await research_engine.research(request)
        
        # Convert to dict for JSON serialization
        result_dict = result.model_dump()
        
        # Output result as JSON
        print(json.dumps(result_dict, default=str))
        
    except Exception as e:
        # Output error as JSON
        error_result = {
            "query": request_data.get("query", ""),
            "answer": f"Research failed: {str(e)}",
            "research_metadata": {
                "sources_searched": 0,
                "sources_processed": 0,
                "research_time_seconds": 0,
                "confidence_score": 0.0,
                "query_type": "factual",
                "sub_questions": []
            },
            "sources": [],
            "follow_up_suggestions": ["Please try again with a different query"]
        }
        print(json.dumps(error_result))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())