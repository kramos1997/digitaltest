"""Test query expansion functionality."""

import pytest
from app.search import expand_query


class TestQueryExpansion:
    """Test query expansion strategies."""
    
    @pytest.mark.asyncio
    async def test_expand_query_returns_list(self):
        """Test that expand_query returns a list of queries."""
        query = "AI regulation Europe"
        result = await expand_query(query)
        
        assert isinstance(result, list)
        assert len(result) >= 4
        assert len(result) <= 8
    
    @pytest.mark.asyncio
    async def test_expand_query_includes_original(self):
        """Test that original query is included."""
        query = "climate change policy"
        result = await expand_query(query)
        
        assert query in result
    
    @pytest.mark.asyncio
    async def test_expand_query_includes_gov_edu_bias(self):
        """Test that expansion includes at least one gov/edu biased query."""
        query = "cybersecurity standards"
        result = await expand_query(query)
        
        has_gov_bias = any("site:gov" in q for q in result)
        has_edu_bias = any("site:edu" in q for q in result)
        has_europa_bias = any("site:europa.eu" in q for q in result)
        
        assert has_gov_bias or has_edu_bias or has_europa_bias
    
    @pytest.mark.asyncio
    async def test_expand_query_includes_temporal_constraints(self):
        """Test that expansion includes temporal constraints."""
        query = "renewable energy policies"
        result = await expand_query(query)
        
        has_temporal = any("since:" in q or "months" in q for q in result)
        assert has_temporal
    
    @pytest.mark.asyncio
    async def test_expand_query_removes_duplicates(self):
        """Test that duplicate queries are removed."""
        query = "data protection"
        result = await expand_query(query)
        
        assert len(result) == len(set(result))  # No duplicates
    
    @pytest.mark.asyncio
    async def test_expand_query_limits_results(self):
        """Test that results are limited to 8 queries."""
        query = "artificial intelligence governance"
        result = await expand_query(query)
        
        assert len(result) <= 8
    
    @pytest.mark.asyncio
    async def test_expand_query_empty_input(self):
        """Test behavior with empty query."""
        query = ""
        result = await expand_query(query)
        
        # Should still return some results but may be minimal
        assert isinstance(result, list)
        assert len(result) >= 1  # At least the empty string
    
    @pytest.mark.asyncio
    async def test_expand_query_context_terms(self):
        """Test that context terms are added appropriately."""
        query = "AI governance"
        result = await expand_query(query)
        
        # Should add regulation/policy context if not already present
        has_context = any("regulation" in q or "policy" in q for q in result)
        assert has_context
    
    @pytest.mark.asyncio
    async def test_expand_query_broader_narrower_variants(self):
        """Test that broader and narrower variants are created."""
        query = "blockchain technology"
        result = await expand_query(query)
        
        has_overview = any("overview" in q for q in result)
        has_details = any("implementation" in q or "details" in q for q in result)
        
        assert has_overview or has_details
