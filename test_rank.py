"""Test document ranking functionality."""

import pytest
from datetime import datetime, timedelta
from app.rank import score_documents, _calculate_domain_score, _calculate_recency_score
from app.models import ScrapedDoc


class TestDocumentRanking:
    """Test document scoring and ranking."""
    
    def create_test_doc(self, title="Test Document", domain="example.com", 
                       word_count=1000, published_date=None):
        """Create a test document."""
        return ScrapedDoc(
            title=title,
            url=f"https://{domain}/test",
            text="This is test content with some relevant keywords about AI regulation and policy.",
            domain=domain,
            word_count=word_count,
            published_at_guess=published_date or "2024-03"
        )
    
    @pytest.mark.asyncio
    async def test_score_documents_returns_sorted_list(self):
        """Test that score_documents returns documents sorted by relevance."""
        docs = [
            self.create_test_doc("AI Policy", "example.com"),
            self.create_test_doc("AI Regulation Guide", "gov.eu", published_date="2024-01"),
            self.create_test_doc("Random Article", "blog.com")
        ]
        
        query = "AI regulation policy"
        result = await score_documents(query, docs)
        
        assert len(result) == 3
        assert all(hasattr(doc, 'relevance_score') for doc in result)
        
        # Should be sorted by score (highest first)
        scores = [doc.relevance_score for doc in result]
        assert scores == sorted(scores, reverse=True)
    
    @pytest.mark.asyncio
    async def test_score_documents_empty_list(self):
        """Test behavior with empty document list."""
        result = await score_documents("test query", [])
        assert result == []
    
    def test_calculate_domain_score_gov_domains(self):
        """Test that government domains get highest scores."""
        assert _calculate_domain_score("example.gov") == 1.0
        assert _calculate_domain_score("europa.eu") >= 0.95
        assert _calculate_domain_score("example.edu") >= 0.95
    
    def test_calculate_domain_score_org_domains(self):
        """Test that .org domains get medium-high scores."""
        score = _calculate_domain_score("nonprofit.org")
        assert 0.8 <= score < 0.9
    
    def test_calculate_domain_score_news_domains(self):
        """Test that major news domains get good scores."""
        assert _calculate_domain_score("reuters.com") >= 0.75
        assert _calculate_domain_score("bbc.com") >= 0.75
    
    def test_calculate_domain_score_default_domains(self):
        """Test that unknown domains get default scores."""
        score = _calculate_domain_score("random-blog.com")
        assert score == 0.6
    
    def test_calculate_recency_score_recent_dates(self):
        """Test that recent dates get higher scores."""
        recent_score = _calculate_recency_score("2024-03")
        old_score = _calculate_recency_score("2020-01")
        
        assert recent_score > old_score
        assert recent_score == 1.0  # Very recent
    
    def test_calculate_recency_score_invalid_dates(self):
        """Test behavior with invalid or missing dates."""
        assert _calculate_recency_score("") == 0.5
        assert _calculate_recency_score("invalid-date") == 0.5
        assert _calculate_recency_score(None) == 0.5
    
    @pytest.mark.asyncio
    async def test_ranking_prefers_authoritative_sources(self):
        """Test that authoritative sources rank higher."""
        docs = [
            self.create_test_doc("AI Policy Research", "random-blog.com"),
            self.create_test_doc("AI Policy Research", "government.gov")
        ]
        
        query = "AI policy"
        result = await score_documents(query, docs)
        
        # Government source should rank higher
        assert result[0].domain == "government.gov"
    
    @pytest.mark.asyncio
    async def test_ranking_considers_relevance(self):
        """Test that content relevance affects ranking."""
        docs = [
            self.create_test_doc("Cooking Recipes", "example.com"),
            ScrapedDoc(
                title="AI Regulation Policy",
                url="https://example.com/ai",
                text="Comprehensive guide to artificial intelligence regulation and policy implementation.",
                domain="example.com",
                word_count=500,
                published_at_guess="2024-01"
            )
        ]
        
        query = "AI regulation policy"
        result = await score_documents(query, docs)
        
        # More relevant document should rank higher
        assert "AI Regulation Policy" in result[0].title
    
    @pytest.mark.asyncio
    async def test_ranking_considers_recency(self):
        """Test that more recent documents rank higher when other factors equal."""
        docs = [
            self.create_test_doc("AI Policy", "example.com", published_date="2020-01"),
            self.create_test_doc("AI Policy", "example.com", published_date="2024-03")
        ]
        
        query = "AI policy"
        result = await score_documents(query, docs)
        
        # More recent document should rank higher
        assert result[0].published_at_guess == "2024-03"
    
    @pytest.mark.asyncio
    async def test_diversity_penalty_applied(self):
        """Test that documents from same domain get diversity penalty."""
        docs = [
            self.create_test_doc("Article 1", "same-domain.com"),
            self.create_test_doc("Article 2", "same-domain.com"),
            self.create_test_doc("Article 3", "same-domain.com"),
            self.create_test_doc("Article 4", "different-domain.com")
        ]
        
        query = "test query"
        result = await score_documents(query, docs)
        
        # Later articles from same domain should have lower scores
        same_domain_scores = [doc.relevance_score for doc in result if doc.domain == "same-domain.com"]
        assert len(same_domain_scores) >= 2  # Multiple docs from same domain
        
        # Scores should decrease for additional docs from same domain
        if len(same_domain_scores) >= 3:
            assert same_domain_scores[0] > same_domain_scores[2]  # Diversity penalty applied
