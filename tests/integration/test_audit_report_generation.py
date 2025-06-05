"""
Integration tests for audit report generation with real components.
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from leadfactory.services.audit_report_generator import AuditReportGenerator


class TestAuditReportGenerationIntegration:
    """Integration tests for complete audit report generation workflow."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup handled by OS for temp directories
    
    @pytest.fixture
    def sample_business_data(self):
        """Create comprehensive sample business data."""
        return {
            'id': 1,
            'name': 'TechStart Solutions Inc',
            'address': '100 Innovation Drive',
            'city': 'San Francisco',
            'state': 'CA',
            'zip': '94107',
            'phone': '415-555-0123',
            'email': 'hello@techstart.com',
            'website': 'https://techstart.com',
            'category': 'Software Development',
            'score': 78,
            'tech_stack': [
                'React', 'Node.js', 'PostgreSQL', 'TypeScript', 
                'Docker', 'AWS', 'Redis', 'GraphQL'
            ],
            'page_speed': 82,
            'screenshot_url': 'https://storage.example.com/screenshots/techstart.png',
            'semrush_data': {
                'errors': [
                    'Missing meta description on 3 pages',
                    'Broken internal links detected',
                    'Missing alt text on images'
                ],
                'warnings': [
                    'H1 tag optimization needed',
                    'Page titles could be more descriptive',
                    'Schema markup missing for products',
                    'Slow loading images detected',
                    'Internal linking structure needs improvement'
                ]
            },
            'audit_metadata': {
                'generated_at': '2024-01-15T10:30:00',
                'data_sources': [
                    'Website Analysis',
                    'PageSpeed Insights', 
                    'Technology Stack Analysis',
                    'SEMrush Site Audit',
                    'Visual Analysis'
                ]
            }
        }
    
    @pytest.fixture
    def mock_storage_with_data(self, sample_business_data):
        """Create mock storage that returns sample business data."""
        storage = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        
        # Mock connection context manager
        storage.get_connection.return_value.__enter__.return_value = mock_conn
        storage.get_connection.return_value.__exit__.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock database response with business data
        mock_cursor.description = [
            ('id',), ('name',), ('address',), ('city',), ('state',), ('zip',),
            ('phone',), ('email',), ('website',), ('category',), ('score',),
            ('tech_stack',), ('page_speed',), ('screenshot_url',), ('semrush_json',)
        ]
        
        mock_cursor.fetchone.return_value = (
            sample_business_data['id'],
            sample_business_data['name'],
            sample_business_data['address'],
            sample_business_data['city'],
            sample_business_data['state'],
            sample_business_data['zip'],
            sample_business_data['phone'],
            sample_business_data['email'],
            sample_business_data['website'],
            sample_business_data['category'],
            sample_business_data['score'],
            json.dumps(sample_business_data['tech_stack']),
            sample_business_data['page_speed'],
            sample_business_data['screenshot_url'],
            json.dumps(sample_business_data['semrush_data'])
        )
        
        return storage
    
    @pytest.fixture
    def mock_llm_with_analysis(self):
        """Create mock LLM client with realistic analysis response."""
        client = MagicMock()
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "executive_summary": "TechStart Solutions Inc demonstrates strong technical capabilities with a modern technology stack and good website performance. The analysis reveals a well-structured web presence with opportunities for SEO optimization and performance enhancement.",
            "key_findings": [
                "Strong technical foundation with modern stack including React, Node.js, and TypeScript",
                "Good website performance with PageSpeed score of 82/100, indicating solid optimization",
                "Comprehensive technology infrastructure using Docker and AWS for scalability",
                "SEO audit reveals 3 critical issues and 5 optimization opportunities",
                "Missing structured data markup limiting search engine understanding"
            ],
            "recommendations": [
                "Address critical SEO issues: add meta descriptions and fix broken internal links",
                "Implement structured data markup (Schema.org) for better search visibility",
                "Optimize images with proper alt text and compression for faster loading",
                "Improve internal linking structure to distribute page authority effectively",
                "Consider implementing progressive web app features for enhanced user experience"
            ],
            "overall_assessment": "TechStart Solutions Inc has built a solid technical foundation with modern development practices. The website performs well but has clear SEO optimization opportunities that, when addressed, could significantly improve search visibility and user engagement. The company's investment in current technologies positions them well for future growth."
        })
        
        from unittest.mock import AsyncMock
        client.chat_completion = AsyncMock(return_value=mock_response)
        return client
    
    @pytest.mark.asyncio
    async def test_complete_audit_report_generation(
        self, 
        temp_dir, 
        mock_storage_with_data, 
        mock_llm_with_analysis,
        sample_business_data
    ):
        """Test complete audit report generation with all components."""
        
        # Create audit report generator with mocked dependencies
        generator = AuditReportGenerator(
            storage=mock_storage_with_data,
            llm_client=mock_llm_with_analysis
        )
        
        # Generate report to file
        output_path = os.path.join(temp_dir, "complete_audit_report.pdf")
        
        result = await generator.generate_audit_report(
            business_name="TechStart Solutions Inc",
            customer_email="client@techstart.com",
            report_id="audit-2024-001",
            output_path=output_path,
            return_bytes=False
        )
        
        # Verify file was created
        assert result == output_path
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 1000  # Should be substantial PDF
        
        # Verify LLM was called
        mock_llm_with_analysis.chat_completion.assert_called_once()
        
        # Verify database query was made
        mock_storage_with_data.get_connection.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_audit_report_generation_as_bytes(
        self,
        mock_storage_with_data,
        mock_llm_with_analysis
    ):
        """Test audit report generation returning bytes."""
        
        generator = AuditReportGenerator(
            storage=mock_storage_with_data,
            llm_client=mock_llm_with_analysis
        )
        
        # Generate report as bytes
        result = await generator.generate_audit_report(
            business_name="TechStart Solutions Inc",
            customer_email="client@techstart.com",
            report_id="audit-2024-002",
            output_path=None,
            return_bytes=True
        )
        
        # Verify bytes were returned
        assert isinstance(result, bytes)
        assert len(result) > 1000  # Should be substantial PDF
        
        # Verify PDF header
        assert result.startswith(b'%PDF-')
    
    @pytest.mark.asyncio
    async def test_audit_report_with_llm_failure(
        self,
        temp_dir,
        mock_storage_with_data
    ):
        """Test audit report generation when LLM fails."""
        
        # Create LLM client that fails
        mock_llm_client = MagicMock()
        from unittest.mock import AsyncMock
        mock_llm_client.chat_completion = AsyncMock(side_effect=Exception("API Error"))
        
        generator = AuditReportGenerator(
            storage=mock_storage_with_data,
            llm_client=mock_llm_client
        )
        
        output_path = os.path.join(temp_dir, "fallback_audit_report.pdf")
        
        # Should still generate report using fallback analysis
        result = await generator.generate_audit_report(
            business_name="TechStart Solutions Inc",
            customer_email="client@techstart.com",
            report_id="audit-2024-003",
            output_path=output_path,
            return_bytes=False
        )
        
        # Verify file was created despite LLM failure
        assert result == output_path
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 1000
    
    @pytest.mark.asyncio
    async def test_audit_report_no_business_data(
        self,
        temp_dir,
        mock_llm_with_analysis
    ):
        """Test audit report generation when business data not found."""
        
        # Create storage that returns no data
        storage = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        
        storage.get_connection.return_value.__enter__.return_value = mock_conn
        storage.get_connection.return_value.__exit__.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # No business found
        
        generator = AuditReportGenerator(
            storage=storage,
            llm_client=mock_llm_with_analysis
        )
        
        output_path = os.path.join(temp_dir, "minimal_audit_report.pdf")
        
        # Should generate minimal report
        result = await generator.generate_audit_report(
            business_name="Non-existent Business",
            customer_email="client@example.com",
            report_id="audit-2024-004",
            output_path=output_path,
            return_bytes=False
        )
        
        # Verify minimal report was created
        assert result == output_path
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 500  # Should still be a real PDF
        
        # LLM should not be called for minimal report
        mock_llm_with_analysis.chat_completion.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_audit_report_with_partial_data(
        self,
        temp_dir,
        mock_llm_with_analysis
    ):
        """Test audit report generation with partial business data."""
        
        # Create storage with minimal business data
        storage = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        
        storage.get_connection.return_value.__enter__.return_value = mock_conn
        storage.get_connection.return_value.__exit__.return_value = None
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock minimal data response
        mock_cursor.description = [
            ('id',), ('name',), ('address',), ('city',), ('state',), ('zip',),
            ('phone',), ('email',), ('website',), ('category',), ('score',),
            ('tech_stack',), ('page_speed',), ('screenshot_url',), ('semrush_json',)
        ]
        
        mock_cursor.fetchone.return_value = (
            1, 'Minimal Business', None, None, None, None,
            None, 'contact@minimal.com', 'https://minimal.com', 'Unknown', 0,
            None, None, None, None
        )
        
        generator = AuditReportGenerator(
            storage=storage,
            llm_client=mock_llm_with_analysis
        )
        
        output_path = os.path.join(temp_dir, "partial_data_report.pdf")
        
        result = await generator.generate_audit_report(
            business_name="Minimal Business",
            customer_email="client@minimal.com",
            report_id="audit-2024-005",
            output_path=output_path,
            return_bytes=False
        )
        
        # Should still generate report with available data
        assert result == output_path
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 1000
    
    @pytest.mark.asyncio
    async def test_concurrent_report_generation(
        self,
        temp_dir,
        mock_storage_with_data,
        mock_llm_with_analysis
    ):
        """Test concurrent audit report generation."""
        import asyncio
        
        generator = AuditReportGenerator(
            storage=mock_storage_with_data,
            llm_client=mock_llm_with_analysis
        )
        
        # Generate multiple reports concurrently
        tasks = []
        for i in range(3):
            output_path = os.path.join(temp_dir, f"concurrent_report_{i}.pdf")
            task = generator.generate_audit_report(
                business_name="TechStart Solutions Inc",
                customer_email=f"client{i}@techstart.com",
                report_id=f"audit-2024-00{i+6}",
                output_path=output_path,
                return_bytes=False
            )
            tasks.append(task)
        
        # Wait for all reports to complete
        results = await asyncio.gather(*tasks)
        
        # Verify all reports were generated
        for i, result in enumerate(results):
            expected_path = os.path.join(temp_dir, f"concurrent_report_{i}.pdf")
            assert result == expected_path
            assert os.path.exists(expected_path)
            assert os.path.getsize(expected_path) > 1000
    
    def test_data_source_identification_comprehensive(self):
        """Test comprehensive data source identification."""
        generator = AuditReportGenerator()
        
        # Test with all data sources available
        business_data = {
            'website': 'https://example.com',
            'page_speed': 85,
            'tech_stack': ['React', 'Node.js'],
            'semrush_data': {'errors': ['Missing meta']},
            'screenshot_url': 'https://screenshots.com/image.png'
        }
        
        sources = generator._identify_data_sources(business_data)
        
        expected_sources = [
            'Website Analysis',
            'PageSpeed Insights', 
            'Technology Stack Analysis',
            'SEMrush Site Audit',
            'Visual Analysis'
        ]
        
        for expected in expected_sources:
            assert expected in sources
        
        # Test with minimal data
        minimal_data = {'website': 'https://example.com'}
        sources = generator._identify_data_sources(minimal_data)
        assert sources == ['Website Analysis']
        
        # Test with no data
        empty_data = {}
        sources = generator._identify_data_sources(empty_data)
        assert sources == []
    
    def test_fallback_analysis_comprehensive(self):
        """Test comprehensive fallback analysis generation."""
        generator = AuditReportGenerator()
        
        # Test with rich business data
        business_data = {
            'name': 'Advanced Tech Corp',
            'page_speed': 95,
            'tech_stack': ['React', 'Next.js', 'TypeScript'],
            'semrush_data': {
                'errors': ['Broken link'],
                'warnings': ['Meta description missing', 'Alt text needed']
            }
        }
        
        result = generator._generate_fallback_analysis(business_data)
        
        # Verify structure
        assert 'executive_summary' in result
        assert 'key_findings' in result
        assert 'recommendations' in result
        assert 'overall_assessment' in result
        
        # Check PageSpeed analysis
        findings = result['key_findings']
        pagespeed_finding = next((f for f in findings if 'PageSpeed' in f and '95/100' in f), None)
        assert pagespeed_finding is not None
        assert 'Excellent' in pagespeed_finding
        
        # Check modern tech detection
        modern_tech_finding = next((f for f in findings if 'Modern technology' in f), None)
        assert modern_tech_finding is not None
        
        # Check SEMrush analysis
        seo_finding = next((f for f in findings if 'SEO audit' in f), None)
        assert seo_finding is not None
        assert '1 critical issues' in seo_finding or '1 errors' in seo_finding
        
        # Verify recommendations are actionable
        recommendations = result['recommendations']
        assert len(recommendations) > 0
        assert any('SEO' in rec for rec in recommendations)


if __name__ == "__main__":
    pytest.main([__file__])