"""FastAPI main application module."""

import asyncio
import json
import time
from typing import Dict, List, Optional

from fastapi import FastAPI, Request, Form, Depends, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .config import get_settings
from .deps import get_search_client, get_llm_client, get_rate_limiter
from .models import ResearchRequest, ResearchResponse, SearchResult
from .search import expand_query, searx_search
from .scrape import scrape_documents
from .rank import score_documents, rerank_with_llm
from .synth import synthesize_answer
from .evidence import build_evidence_matrix, validate_answer
from .utils import redact_sensitive_data, log_structured

app = FastAPI(title="ClarityDesk", description="GDPR-first deep research platform")

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda request, exc: _rate_limit_exceeded_handler(request, exc))
app.add_middleware(SlowAPIMiddleware)

# Static files and templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

settings = get_settings()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render main research interface."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "gdpr_mode": settings.gdpr_mode,
            "app_name": "ClarityDesk"
        }
    )


@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    """Render privacy policy page."""
    return templates.TemplateResponse(
        "privacy.html",
        {
            "request": request,
            "gdpr_mode": settings.gdpr_mode,
            "app_name": "ClarityDesk"
        }
    )


@app.get("/llm/health")
async def llm_health(llm_client=Depends(get_llm_client)):
    """Check LLM provider connectivity."""
    try:
        # Test with a simple prompt
        test_messages = [
            {"role": "user", "content": "Hello, respond with 'OK' if you're working."}
        ]
        
        response_chunks = []
        async for chunk in llm_client.chat(test_messages, max_tokens=10):
            response_chunks.append(chunk)
            
        response_text = "".join(response_chunks)
        
        return {
            "status": "healthy",
            "provider": settings.llm_provider,
            "model": getattr(settings, f"{settings.llm_provider.upper()}_MODEL", "unknown"),
            "test_response": response_text[:50]  # First 50 chars
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "provider": settings.llm_provider,
            "error": str(e)
        }


@app.post("/research")
@limiter.limit("10/minute")
async def research(
    request: Request,
    q: str = Form(...),
    lang: str = Form("en"),
    search_client=Depends(get_search_client),
    llm_client=Depends(get_llm_client)
):
    """Process research query and stream results."""
    
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # Log request (respect GDPR mode)
    if not settings.gdpr_mode:
        log_structured("research_request", {
            "query": q,
            "lang": lang,
            "ip": get_remote_address(request)
        })
    else:
        log_structured("research_request", {
            "query_length": len(q),
            "lang": lang
        })

    async def generate_research_response():
        """Generate streaming research response."""
        try:
            # Step 1: Query expansion
            yield _create_status_update("Expanding query", "query_expansion")
            expanded_queries = await expand_query(q)
            
            yield _create_status_update(
                f"Generated {len(expanded_queries)} search queries", 
                "query_expansion_complete"
            )
            
            # Step 2: Search
            yield _create_status_update("Searching sources", "search")
            search_results = await searx_search(expanded_queries, search_client, k=24)
            
            yield _create_status_update(
                f"Found {len(search_results)} potential sources", 
                "search_complete"
            )
            
            if len(search_results) < 3:
                yield _create_error_response(
                    "Insufficient sources found",
                    "Please try a different query or check your internet connection."
                )
                return
                
            # Step 3: Scraping
            yield _create_status_update("Fetching content", "scraping")
            scraped_docs = await scrape_documents(search_results[:12])  # Limit concurrent scraping
            
            if len(scraped_docs) < 3:
                yield _create_error_response(
                    "Could not fetch enough reliable sources",
                    "Many sources were inaccessible or blocked. Try a different query."
                )
                return
                
            yield _create_status_update(
                f"Successfully scraped {len(scraped_docs)} documents", 
                "scraping_complete"
            )
            
            # Step 4: Ranking
            yield _create_status_update("Ranking sources", "ranking")
            ranked_docs = await score_documents(q, scraped_docs)
            
            # Optional reranking with LLM
            if settings.enable_rerank and len(ranked_docs) >= 10:
                try:
                    ranked_docs = await rerank_with_llm(q, ranked_docs[:20], llm_client)
                except Exception as e:
                    log_structured("rerank_failed", {"error": str(e)})
                    # Continue with heuristic ranking
            
            top_docs = ranked_docs[:8]  # Use top 8 sources
            
            # Step 5: Synthesis
            yield _create_status_update("Synthesizing answer", "synthesis")
            
            # Stream the answer synthesis
            answer_data = await synthesize_answer(q, top_docs, llm_client)
            
            # Apply GDPR redaction if needed
            if settings.gdpr_mode:
                answer_data['answer'] = redact_sensitive_data(answer_data['answer'])
                for source in answer_data['sources']:
                    source['snippet'] = redact_sensitive_data(source.get('snippet', ''))
            
            # Step 6: Evidence matrix
            evidence_matrix = build_evidence_matrix(answer_data['answer'], answer_data['sources'])
            
            # Step 7: Final response
            research_response = {
                "answer": answer_data['answer'],
                "sources": answer_data['sources'],
                "evidence_matrix": evidence_matrix,
                "expanded_queries": expanded_queries,
                "processing_stats": {
                    "sources_found": len(search_results),
                    "sources_used": len(top_docs),
                    "queries_expanded": len(expanded_queries)
                }
            }
            
            # Return HTML components
            yield _create_answer_html(research_response, request)
            yield _create_sources_html(research_response, request)  
            yield _create_research_log_html(research_response, request)
            
        except Exception as e:
            log_structured("research_error", {"error": str(e)})
            yield _create_error_response(
                "Research processing failed",
                f"An error occurred during research: {str(e)}"
            )

    return StreamingResponse(
        generate_research_response(),
        media_type="text/html",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


def _create_status_update(message: str, status: str) -> str:
    """Create HTMX status update."""
    return f'''
    <div hx-swap-oob="innerHTML:#research-status">
        <div class="flex items-center gap-2 text-sm text-blue-700">
            <div class="spinner"></div>
            <span>{message}</span>
        </div>
    </div>
    '''


def _create_error_response(title: str, message: str) -> str:
    """Create error response HTML."""
    return f'''
    <div hx-swap-oob="innerHTML:#answer">
        <div class="bg-red-50 border border-red-200 rounded-lg p-6">
            <div class="flex items-center gap-2 text-red-800 mb-2">
                <i class="fas fa-exclamation-triangle"></i>
                <h4 class="font-semibold">{title}</h4>
            </div>
            <p class="text-red-700">{message}</p>
        </div>
    </div>
    '''


def _create_answer_html(response: Dict, request: Request) -> str:
    """Create answer component HTML."""
    return templates.get_template("components/answer.html").render(
        request=request,
        answer=response['answer'],
        sources=response['sources']
    )


def _create_sources_html(response: Dict, request: Request) -> str:
    """Create sources component HTML."""
    return templates.get_template("components/sources.html").render(
        request=request,
        sources=response['sources']
    )


def _create_research_log_html(response: Dict, request: Request) -> str:
    """Create research log component HTML."""
    return templates.get_template("components/research_log.html").render(
        request=request,
        expanded_queries=response['expanded_queries'],
        evidence_matrix=response['evidence_matrix'],
        processing_stats=response['processing_stats'],
        sources=response['sources']
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
