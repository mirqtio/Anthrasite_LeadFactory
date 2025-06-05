"""
Unit tests for the audit report generator service.
"""

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from leadfactory.services.audit_report_generator import AuditReportGenerator


class TestAuditReportGenerator:
    """Test audit report generator functionality."""
    
    @pytest.fixture
    def mock_storage(self):
        """Create mock storage."""
        storage = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        
        # Mock connection context manager
        storage.get_connection.return_value.__enter__.return_value = mock_conn
        storage.get_connection.return_value.__exit__.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        
        return storage, mock_cursor
    
    @pytest.fixture
    def mock_llm_client(self):
        """Create mock LLM client."""
        client = MagicMock()
        
        # Mock successful LLM response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "executive_summary": "Test business shows good performance with room for improvement.",
            "key_findings": [
                "Website loads quickly with good PageSpeed score",
                "Modern technology stack detected",
                "SEO optimization needed"
            ],
            "recommendations": [
                "Implement structured data markup",
                "Optimize images for better compression",
                "Improve internal linking structure"
            ],
            "overall_assessment": "Strong foundation with clear optimization opportunities."
        })
        
        client.chat_completion = AsyncMock(return_value=mock_response)
        return client
    
    @pytest.fixture
    def mock_pdf_generator(self):
        """Create mock PDF generator."""
        generator = MagicMock()
        generator.generate_document.return_value = "/tmp/test_report.pdf"
        return generator
    
    @pytest.fixture
    def sample_business_data(self):
        """Create sample business data."""
        return {
            'id': 1,
            'name': 'Test Business Inc',
            'address': '123 Main St',
            'city': 'San Francisco',
            'state': 'CA',
            'zip': '94102',
            'phone': '555-123-4567',
            'email': 'contact@testbusiness.com',
            'website': 'https://testbusiness.com',
            'category': 'Technology',
            'score': 75,
            'tech_stack': ['React', 'Node.js', 'PostgreSQL'],
            'page_speed': 85,
            'screenshot_url': 'https://example.com/screenshot.png',
            'semrush_data': {
                'errors': ['Missing meta description'],
                'warnings': ['Image alt text missing', 'H1 tag optimization needed']
            }
        }
    
    def test_initialization(self, mock_storage, mock_llm_client):
        """Test audit report generator initialization."""
        storage, _ = mock_storage
        generator = AuditReportGenerator(
            storage=storage,
            llm_client=mock_llm_client
        )
        
        assert generator.storage == storage
        assert generator.llm_client == mock_llm_client
        assert generator.pdf_config.title == "Business Website Audit Report"
        assert generator.pdf_config.author == "Anthrasite Digital"
    
    @pytest.mark.asyncio
    async def test_fetch_business_data_success(self, mock_storage, mock_llm_client):
        """Test successful business data fetching."""
        storage, mock_cursor = mock_storage
        
        # Mock database response
        mock_cursor.description = [
            ('id',), ('name',), ('address',), ('city',), ('state',), ('zip',),
            ('phone',), ('email',), ('website',), ('category',), ('score',),
            ('tech_stack',), ('page_speed',), ('screenshot_url',), ('semrush_json',)
        ]
        mock_cursor.fetchone.return_value = (
            1, 'Test Business', '123 Main St', 'San Francisco', 'CA', '94102',
            '555-123-4567', 'test@example.com', 'https://test.com', 'Technology', 75,
            '["React", "Node.js"]', 85, 'https://screenshot.png', '{"errors": []}'
        )
        
        generator = AuditReportGenerator(storage=storage, llm_client=mock_llm_client)
        
        result = await generator._fetch_business_data('Test Business')
        
        assert result is not None
        assert result['name'] == 'Test Business'
        assert result['tech_stack'] == ['React', 'Node.js']
        assert result['semrush_data'] == {'errors': []}
        assert 'audit_metadata' in result
    
    @pytest.mark.asyncio
    async def test_fetch_business_data_not_found(self, mock_storage, mock_llm_client):
        """Test business data fetching when business not found."""
        storage, mock_cursor = mock_storage
        
        # Mock no results
        mock_cursor.fetchone.return_value = None
        
        generator = AuditReportGenerator(storage=storage, llm_client=mock_llm_client)
        
        result = await generator._fetch_business_data('Non-existent Business')
        
        assert result is None
    
    def test_identify_data_sources(self, mock_storage, mock_llm_client):
        """Test data sources identification."""
        generator = AuditReportGenerator(storage=mock_storage[0], llm_client=mock_llm_client)
        
        business_data = {
            'website': 'https://test.com',
            'page_speed': 85,
            'tech_stack': ['React'],
            'semrush_data': {'errors': []},
            'screenshot_url': 'https://screenshot.png'
        }
        
        sources = generator._identify_data_sources(business_data)
        
        assert 'Website Analysis' in sources
        assert 'PageSpeed Insights' in sources
        assert 'Technology Stack Analysis' in sources
        assert 'SEMrush Site Audit' in sources
        assert 'Visual Analysis' in sources
    
    @pytest.mark.asyncio
    async def test_generate_audit_analysis_success(self, mock_storage, mock_llm_client, sample_business_data):
        """Test successful audit analysis generation."""
        generator = AuditReportGenerator(storage=mock_storage[0], llm_client=mock_llm_client)
        
        result = await generator._generate_audit_analysis(sample_business_data)
        
        assert 'executive_summary' in result
        assert 'key_findings' in result
        assert 'recommendations' in result
        assert isinstance(result['key_findings'], list)
        assert isinstance(result['recommendations'], list)
    
    @pytest.mark.asyncio
    async def test_generate_audit_analysis_llm_failure(self, mock_storage, sample_business_data):
        """Test audit analysis generation when LLM fails."""
        # Mock LLM client that raises an exception
        mock_llm_client = MagicMock()
        mock_llm_client.chat_completion = AsyncMock(side_effect=Exception("LLM API error"))
        
        generator = AuditReportGenerator(storage=mock_storage[0], llm_client=mock_llm_client)
        
        result = await generator._generate_audit_analysis(sample_business_data)
        
        # Should fall back to rule-based analysis
        assert 'executive_summary' in result
        assert 'key_findings' in result
        assert 'recommendations' in result
        assert len(result['recommendations']) > 0
    
    def test_build_analysis_prompt(self, mock_storage, mock_llm_client, sample_business_data):
        """Test analysis prompt building."""
        generator = AuditReportGenerator(storage=mock_storage[0], llm_client=mock_llm_client)
        
        prompt = generator._build_analysis_prompt(sample_business_data)
        
        assert 'Test Business Inc' in prompt
        assert 'Technology' in prompt
        assert 'PageSpeed Score: 85/100' in prompt
        assert 'React, Node.js, PostgreSQL' in prompt
        assert 'SEO Issues: 1 issues found' in prompt
        assert 'JSON' in prompt
    
    def test_parse_analysis_response_json(self, mock_storage, mock_llm_client):
        """Test parsing JSON analysis response."""
        generator = AuditReportGenerator(storage=mock_storage[0], llm_client=mock_llm_client)
        
        json_response = """
        Here is the analysis:
        {
            "executive_summary": "Test summary",
            "key_findings": ["Finding 1", "Finding 2"],
            "recommendations": ["Rec 1", "Rec 2"],
            "overall_assessment": "Good overall"
        }
        Additional text here.
        """
        
        result = generator._parse_analysis_response(json_response, {})
        
        assert result['executive_summary'] == "Test summary"
        assert result['key_findings'] == ["Finding 1", "Finding 2"]
        assert result['recommendations'] == ["Rec 1", "Rec 2"]
    
    def test_parse_analysis_response_text(self, mock_storage, mock_llm_client):
        """Test parsing text analysis response."""
        generator = AuditReportGenerator(storage=mock_storage[0], llm_client=mock_llm_client)
        
        text_response = """
        Executive Summary
        This is the summary text.
        
        Key Findings
        • Finding one here
        • Finding two here
        
        Recommendations
        - Recommendation one
        - Recommendation two
        """
        
        result = generator._parse_analysis_response(text_response, {})
        
        assert 'executive_summary' in result
        assert 'key_findings' in result
        assert 'recommendations' in result
        assert len(result['key_findings']) >= 1
        assert len(result['recommendations']) >= 1
    
    def test_generate_fallback_analysis(self, mock_storage, mock_llm_client, sample_business_data):
        """Test fallback analysis generation."""
        generator = AuditReportGenerator(storage=mock_storage[0], llm_client=mock_llm_client)
        
        result = generator._generate_fallback_analysis(sample_business_data)
        
        assert 'executive_summary' in result
        assert 'key_findings' in result
        assert 'recommendations' in result
        
        # Check PageSpeed analysis
        findings = result['key_findings']
        pagespeed_finding = next((f for f in findings if 'PageSpeed' in f), None)
        assert pagespeed_finding is not None
        assert '85/100' in pagespeed_finding
        
        # Check SEMrush analysis
        semrush_finding = next((f for f in findings if 'SEO audit' in f), None)
        assert semrush_finding is not None
    
    def test_build_business_info_table(self, mock_storage, mock_llm_client, sample_business_data):
        """Test business information table building."""
        generator = AuditReportGenerator(storage=mock_storage[0], llm_client=mock_llm_client)
        
        table_data = generator._build_business_info_table(sample_business_data)
        
        assert len(table_data) > 1  # Header + data rows
        assert table_data[0] == ["Property", "Value"]
        
        # Check some expected rows
        business_name_row = next((row for row in table_data if row[0] == "Business Name"), None)
        assert business_name_row is not None
        assert business_name_row[1] == "Test Business Inc"
        
        website_row = next((row for row in table_data if row[0] == "Website"), None)
        assert website_row is not None
        assert website_row[1] == "https://testbusiness.com"
    
    def test_build_technical_analysis_table(self, mock_storage, mock_llm_client, sample_business_data):
        """Test technical analysis table building."""
        generator = AuditReportGenerator(storage=mock_storage[0], llm_client=mock_llm_client)
        
        table_data = generator._build_technical_analysis_table(sample_business_data)
        
        assert len(table_data) > 1  # Header + data rows
        assert table_data[0] == ["Metric", "Value", "Assessment"]
        
        # Check PageSpeed row
        pagespeed_row = next((row for row in table_data if row[0] == "PageSpeed Score"), None)
        assert pagespeed_row is not None
        assert pagespeed_row[1] == "85/100"
        assert pagespeed_row[2] == "Good"
        
        # Check SEO row
        seo_row = next((row for row in table_data if row[0] == "SEO Analysis"), None)
        assert seo_row is not None
        assert "1 errors, 2 warnings" in seo_row[1]
    
    def test_format_location(self, mock_storage, mock_llm_client):
        """Test location formatting."""
        generator = AuditReportGenerator(storage=mock_storage[0], llm_client=mock_llm_client)
        
        # Test with city, state, zip
        business_data = {'city': 'San Francisco', 'state': 'CA', 'zip': '94102'}
        result = generator._format_location(business_data)
        assert result == "San Francisco, CA, 94102"
        
        # Test with only address
        business_data = {'address': '123 Main St, Anytown, USA'}
        result = generator._format_location(business_data)
        assert result == "123 Main St, Anytown, USA"
        
        # Test with no location data
        business_data = {}
        result = generator._format_location(business_data)
        assert result == "N/A"
    
    def test_build_report_content(self, mock_storage, mock_llm_client, sample_business_data):
        """Test report content building."""
        generator = AuditReportGenerator(storage=mock_storage[0], llm_client=mock_llm_client)
        
        audit_analysis = {
            'executive_summary': 'Test summary',
            'key_findings': ['Finding 1', 'Finding 2'],
            'recommendations': ['Rec 1', 'Rec 2'],
            'overall_assessment': 'Good overall'
        }
        
        content = generator._build_report_content(
            sample_business_data,
            audit_analysis,
            'customer@example.com',
            'report-123'
        )
        
        assert len(content) > 10  # Should have many content elements
        
        # Check for title
        title_elements = [item for item in content if item.get('type') == 'title']
        assert len(title_elements) > 0
        assert title_elements[0]['text'] == 'Website Audit Report'
        
        # Check for sections
        section_headers = [item for item in content if item.get('type') == 'section_header']
        section_texts = [item['text'] for item in section_headers]
        assert 'Executive Summary' in section_texts
        assert 'Business Information' in section_texts
        assert 'Technical Analysis' in section_texts
        assert 'Key Findings' in section_texts
        assert 'Priority Recommendations' in section_texts
    
    @pytest.mark.asyncio
    async def test_generate_minimal_report(self, mock_storage, mock_llm_client):
        """Test minimal report generation."""
        generator = AuditReportGenerator(storage=mock_storage[0], llm_client=mock_llm_client)
        
        with patch.object(generator.pdf_generator, 'generate_document') as mock_generate:
            mock_generate.return_value = "/tmp/minimal_report.pdf"
            
            result = await generator._generate_minimal_report(
                "Test Business",
                "customer@example.com",
                "report-123",
                "/tmp/test.pdf",
                False
            )
            
            assert result == "/tmp/minimal_report.pdf"
            mock_generate.assert_called_once()
            
            # Check the content passed to PDF generator
            call_args = mock_generate.call_args
            content = call_args[1]['content']
            
            # Should have title and basic content
            title_elements = [item for item in content if item.get('type') == 'title']
            assert len(title_elements) > 0
            assert title_elements[0]['text'] == 'Website Audit Report'
    
    @pytest.mark.asyncio
    @patch('tempfile.mkdtemp')
    async def test_generate_audit_report_with_data(self, mock_tempdir, mock_storage, mock_llm_client, sample_business_data):
        """Test complete audit report generation with business data."""
        mock_tempdir.return_value = "/tmp/test"
        storage, mock_cursor = mock_storage
        
        # Mock database response
        mock_cursor.description = [
            ('id',), ('name',), ('address',), ('city',), ('state',), ('zip',),
            ('phone',), ('email',), ('website',), ('category',), ('score',),
            ('tech_stack',), ('page_speed',), ('screenshot_url',), ('semrush_json',)
        ]
        mock_cursor.fetchone.return_value = (
            1, 'Test Business Inc', '123 Main St', 'San Francisco', 'CA', '94102',
            '555-123-4567', 'test@example.com', 'https://test.com', 'Technology', 75,
            '["React", "Node.js"]', 85, 'https://screenshot.png', '{"errors": []}'
        )
        
        generator = AuditReportGenerator(storage=storage, llm_client=mock_llm_client)
        
        with patch.object(generator.pdf_generator, 'generate_document') as mock_generate:
            mock_generate.return_value = "/tmp/test/report-123.pdf"
            
            result = await generator.generate_audit_report(
                "Test Business Inc",
                "customer@example.com",
                "report-123",
                "/tmp/test.pdf",
                False
            )
            
            assert result == "/tmp/test/report-123.pdf"
            mock_generate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_audit_report_no_data(self, mock_storage, mock_llm_client):
        """Test audit report generation when no business data found."""
        storage, mock_cursor = mock_storage
        
        # Mock no database results
        mock_cursor.fetchone.return_value = None
        
        generator = AuditReportGenerator(storage=storage, llm_client=mock_llm_client)
        
        with patch.object(generator, '_generate_minimal_report') as mock_minimal:
            mock_minimal.return_value = "/tmp/minimal.pdf"
            
            result = await generator.generate_audit_report(
                "Non-existent Business",
                "customer@example.com",
                "report-123",
                "/tmp/test.pdf",
                False
            )
            
            assert result == "/tmp/minimal.pdf"
            mock_minimal.assert_called_once()


class TestAuditReportGeneratorIntegration:
    """Integration tests for audit report generator."""
    
    @pytest.mark.asyncio
    async def test_convenience_function(self):
        """Test the convenience function for generating reports."""
        from leadfactory.services.audit_report_generator import generate_audit_report
        
        with patch('leadfactory.services.audit_report_generator.AuditReportGenerator') as mock_class:
            mock_instance = MagicMock()
            mock_instance.generate_audit_report = AsyncMock(return_value="/tmp/report.pdf")
            mock_class.return_value = mock_instance
            
            result = await generate_audit_report(
                "Test Business",
                "customer@example.com",
                "report-123",
                "/tmp/test.pdf",
                False
            )
            
            assert result == "/tmp/report.pdf"
            mock_instance.generate_audit_report.assert_called_once_with(
                "Test Business",
                "customer@example.com", 
                "report-123",
                "/tmp/test.pdf",
                False
            )


if __name__ == "__main__":
    pytest.main([__file__])