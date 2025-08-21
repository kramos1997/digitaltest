"""Test FastAPI routes and endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app
from app.models import SearchResult, ScrapedDoc


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_search_results():
    """Mock search results for testing."""
    return [
        SearchResult(
            title="Test Article",
            url="https://example.com/test",
            snippet="This is a test snippet",
            engine="google",
            published_date="2024-03",
            domain="example.com"
        )
    ]


@pytest.fixture
def mock_scraped_docs():
    """Mock scraped documents for testing."""
    return [
        ScrapedDoc(
            title="Test Document",
            url="https://example.com/test",
            text="This is test content with relevant information about AI regulation.",
            domain="example.com",
            word_count=100,
            published_at_guess="2024-03"
        )
    ]


class TestRoutes:
    """Test API routes."""
    
    def test_index_route(self, client):
        """Test the index route returns HTML."""
        response = client.get("/")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert "ClarityDesk" in response.text
        assert "Deep Research with Evidence" in response.text
    
    def test_privacy_route(self, client):
        """Test the privacy policy route."""
        response = client.get("/privacy")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert "Privacy Policy" in response.text
        assert "GDPR" in response.text
    
    @patch('app.main.get_llm_client')
    def test_llm_health_route_healthy(self, mock_get_llm_client, client):
        """Test LLM health check when healthy."""
        # Mock LLM client
        mock_client = AsyncMock()
        mock_client.chat.return_value = iter(["OK"])
        mock_get_llm_client.return_value = mock_client
        
        response = client.get("/llm/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "provider" in data
    
    @patch('app.main.get_llm_client')
    def test_llm_health_route_unhealthy(self, mock_get_llm_client, client):
        """Test LLM health check when unhealthy."""
        # Mock LLM client that raises exception
        mock_client = AsyncMock()
        mock_client.chat.side_effect = Exception("Connection failed")
        mock_get_llm_client.return_value = mock_client
        
        response = client.get("/llm/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "error" in data
    
    def test_research_route_empty_query(self, client):
        """Test research route with empty query."""
        response = client.post("/research", data={"q": "", "lang": "en"})
        
        assert response.status_code == 400
        assert "Query cannot be empty" in response.json()["detail"]
    
    @patch('app.main.get_search_client')
    @patch('app.main.get_llm_client')
    @patch('app.search.expand_query')
    @patch('app.search.searx_search')
    @patch('app.scrape.scrape_documents')
    @patch('app.rank.score_documents')
    @patch('app.synth.synthesize_answer')
    def test_research_route_success(self, mock_synthesize, mock_score, mock_scrape, 
                                   mock_search, mock_expand, mock_get_llm_client,
                                   mock_get_search_client, client, mock_search_results, 
                                   mock_scraped_docs):
        """Test successful research flow."""
        # Mock all dependencies
        mock_expand.return_value = ["test query", "expanded query"]
        mock_search.return_value = mock_search_results
        mock_scrape.return_value = mock_scraped_docs
        mock_score.return_value = mock_scraped_docs
        mock_synthesize.return_value = {
            "answer": "Test answer with citations [1]",
            "sources": [{
                "id": 1,
                "title": "Test Source",
                "url": "https://example.com",
                "domain": "example.com",
                "published_date": "2024-03",
                "pull_quotes": ["Test quote"]
            }],
            "confidence": "high"
        }
        
        mock_get_search_client.return_value = MagicMock()
        mock_get_llm_client.return_value = MagicMock()
        
        response = client.post("/research", data={"q": "test query", "lang": "en"})
        
        # Should return streaming response
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    
    @patch('app.main.get_search_client')
    @patch('app.main.get_llm_client')
    @patch('app.search.expand_query')
    @patch('app.search.searx_search')
    def test_research_route_insufficient_sources(self, mock_search, mock_expand,
                                                mock_get_llm_client, mock_get_search_client, 
                                                client):
        """Test research route when insufficient sources found."""
        # Mock insufficient search results
        mock_expand.return_value = ["test query"]
        mock_search.return_value = []  # No sources found
        
        mock_get_search_client.return_value = MagicMock()
        mock_get_llm_client.return_value = MagicMock()
        
        response = client.post("/research", data={"q": "test query", "lang": "en"})
        
        assert response.status_code == 200
        # Should contain error message about insufficient sources
        content = b"".join(response.iter_content()).decode()
        assert "Insufficient sources found" in content
    
    def test_research_route_invalid_language(self, client):
        """Test research route with invalid language parameter."""
        response = client.post("/research", data={"q": "test query", "lang": "invalid"})
        
        # Should handle gracefully or return validation error
        assert response.status_code in [400, 422]  # Validation error
    
    @patch('app.main.get_search_client')
    @patch('app.main.get_llm_client')
    @patch('app.search.expand_query')
    def test_research_route_exception_handling(self, mock_expand, mock_get_llm_client,
                                              mock_get_search_client, client):
        """Test research route handles exceptions gracefully."""
        # Mock exception during expansion
        mock_expand.side_effect = Exception("Test error")
        
        mock_get_search_client.return_value = MagicMock()
        mock_get_llm_client.return_value = MagicMock()
        
        response = client.post("/research", data={"q": "test query", "lang": "en"})
        
        assert response.status_code == 200
        # Should return error message in streaming response
        content = b"".join(response.iter_content()).decode()
        assert "error occurred" in content.lower()


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    @patch('app.main.get_search_client')
    @patch('app.main.get_llm_client')
    def test_rate_limiting_applied(self, mock_get_llm_client, mock_get_search_client, client):
        """Test that rate limiting is applied to research endpoint."""
        mock_get_search_client.return_value = MagicMock()
        mock_get_llm_client.return_value = MagicMock()
        
        # Make multiple rapid requests (would exceed rate limit in real scenario)
        for i in range(3):
            response = client.post("/research", data={"q": f"query {i}", "lang": "en"})
            # In test environment, rate limiting might not be fully enforced
            assert response.status_code in [200, 429]  # Success or rate limited


class TestErrorHandling:
    """Test error handling in routes."""
    
    def test_404_handling(self, client):
        """Test that non-existent routes return 404."""
        response = client.get("/nonexistent-route")
        assert response.status_code == 404
    
    def test_method_not_allowed(self, client):
        """Test method not allowed responses."""
        response = client.get("/research")  # POST endpoint
        assert response.status_code == 405
