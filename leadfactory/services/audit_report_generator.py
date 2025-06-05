"""
Real Audit Report Generator Service

This module replaces the placeholder PDF generation with comprehensive,
AI-powered audit reports using actual business metrics and LLM analysis.
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from leadfactory.llm.client import LLMClient
from leadfactory.services.pdf_generator import PDFConfiguration, PDFGenerator
from leadfactory.storage.postgres_storage import PostgresStorage
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class AuditReportGenerator:
    """
    Service for generating comprehensive audit reports using real business data.
    
    This service:
    1. Fetches business data and metrics from the database
    2. Uses GPT-4 to analyze the data and generate insights
    3. Creates a professional PDF report with findings and recommendations
    """
    
    def __init__(
        self,
        storage: Optional[PostgresStorage] = None,
        llm_client: Optional[LLMClient] = None,
        pdf_config: Optional[PDFConfiguration] = None
    ):
        """
        Initialize the audit report generator.
        
        Args:
            storage: Database storage instance
            llm_client: LLM client for generating content
            pdf_config: PDF generation configuration
        """
        self.storage = storage or PostgresStorage()
        self.llm_client = llm_client or LLMClient()
        
        # Configure PDF generation with company branding
        self.pdf_config = pdf_config or PDFConfiguration(
            title="Business Website Audit Report",
            author="Anthrasite Digital",
            subject="Website Performance & SEO Analysis",
            creator="Anthrasite LeadFactory"
        )
        
        self.pdf_generator = PDFGenerator(self.pdf_config)
        
        logger.info("Audit report generator initialized")
    
    async def generate_audit_report(
        self,
        business_name: str,
        customer_email: str,
        report_id: str,
        output_path: Optional[str] = None,
        return_bytes: bool = False
    ) -> Union[str, bytes]:
        """
        Generate a comprehensive audit report for a business.
        
        Args:
            business_name: Name of the business to audit
            customer_email: Customer email address
            report_id: Unique report identifier
            output_path: Path to save PDF file
            return_bytes: Return PDF as bytes instead of file path
            
        Returns:
            Path to generated PDF or bytes content
        """
        try:
            logger.info(f"Generating audit report for {business_name} (ID: {report_id})")
            
            # 1. Fetch business data and metrics
            business_data = await self._fetch_business_data(business_name)
            
            if not business_data:
                logger.warning(f"No business data found for {business_name}, generating minimal report")
                return await self._generate_minimal_report(
                    business_name, customer_email, report_id, output_path, return_bytes
                )
            
            # 2. Generate AI-powered analysis
            audit_analysis = await self._generate_audit_analysis(business_data)
            
            # 3. Build comprehensive report content
            report_content = self._build_report_content(
                business_data, audit_analysis, customer_email, report_id
            )
            
            # 4. Generate PDF
            if output_path or return_bytes:
                result = self.pdf_generator.generate_document(
                    content=report_content,
                    output_path=output_path,
                    return_bytes=return_bytes
                )
            else:
                # Generate to temporary file
                temp_dir = tempfile.mkdtemp()
                temp_path = os.path.join(temp_dir, f"{report_id}.pdf")
                result = self.pdf_generator.generate_document(
                    content=report_content,
                    output_path=temp_path,
                    return_bytes=False
                )
            
            logger.info(f"Successfully generated audit report for {business_name}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate audit report for {business_name}: {e}")
            # Fallback to minimal report
            return await self._generate_minimal_report(
                business_name, customer_email, report_id, output_path, return_bytes
            )
    
    async def _fetch_business_data(self, business_name: str) -> Optional[Dict[str, Any]]:
        """Fetch comprehensive business data from the database."""
        try:
            with self.storage.cursor() as cursor:
                
                # Fetch business information with features
                cursor.execute("""
                    SELECT 
                        b.id, b.name, b.address, b.city, b.state, b.zip,
                        b.phone, b.email, b.website, b.category, b.score,
                        f.tech_stack, f.page_speed, f.screenshot_url, f.semrush_json
                    FROM businesses b
                    LEFT JOIN features f ON b.id = f.business_id
                    WHERE LOWER(b.name) = LOWER(%s)
                    ORDER BY b.created_at DESC
                    LIMIT 1
                """, (business_name,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                # Convert to dictionary
                columns = [desc[0] for desc in cursor.description]
                business_data = dict(zip(columns, row))
                
                # Parse JSON fields
                if business_data.get('tech_stack'):
                    try:
                        business_data['tech_stack'] = json.loads(business_data['tech_stack'])
                    except json.JSONDecodeError:
                        business_data['tech_stack'] = []
                
                if business_data.get('semrush_json'):
                    try:
                        business_data['semrush_data'] = json.loads(business_data['semrush_json'])
                    except json.JSONDecodeError:
                        business_data['semrush_data'] = {}
                
                # Fetch additional metrics if available
                business_data['audit_metadata'] = {
                    'generated_at': datetime.now().isoformat(),
                    'data_sources': self._identify_data_sources(business_data)
                }
                
                return business_data
                
        except Exception as e:
            logger.error(f"Error fetching business data for {business_name}: {e}")
            return None
    
    def _identify_data_sources(self, business_data: Dict[str, Any]) -> List[str]:
        """Identify what data sources were used for the audit."""
        sources = []
        
        if business_data.get('website'):
            sources.append('Website Analysis')
        if business_data.get('page_speed'):
            sources.append('PageSpeed Insights')
        if business_data.get('tech_stack'):
            sources.append('Technology Stack Analysis')
        if business_data.get('semrush_data'):
            sources.append('SEMrush Site Audit')
        if business_data.get('screenshot_url'):
            sources.append('Visual Analysis')
            
        return sources
    
    async def _generate_audit_analysis(self, business_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI-powered audit analysis using GPT-4."""
        try:
            # Prepare data for LLM analysis
            analysis_prompt = self._build_analysis_prompt(business_data)
            
            # Call LLM to generate analysis
            response = await self.llm_client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional web development consultant specializing in website audits. Analyze the provided business data and generate insights, findings, and recommendations."
                    },
                    {
                        "role": "user",
                        "content": analysis_prompt
                    }
                ],
                model="gpt-4",
                temperature=0.7,
                max_tokens=2000
            )
            
            # Parse the LLM response
            analysis_text = response.choices[0].message.content
            
            # Structure the analysis
            return self._parse_analysis_response(analysis_text, business_data)
            
        except Exception as e:
            logger.warning(f"LLM analysis failed, using fallback analysis: {e}")
            return self._generate_fallback_analysis(business_data)
    
    def _build_analysis_prompt(self, business_data: Dict[str, Any]) -> str:
        """Build the prompt for LLM analysis."""
        prompt_parts = [
            f"Business: {business_data.get('name', 'Unknown')}",
            f"Industry: {business_data.get('category', 'Not specified')}",
            f"Website: {business_data.get('website', 'Not provided')}"
        ]
        
        if business_data.get('page_speed'):
            prompt_parts.append(f"PageSpeed Score: {business_data['page_speed']}/100")
        
        if business_data.get('tech_stack'):
            tech_list = ', '.join(business_data['tech_stack'][:10])  # Limit to 10 items
            prompt_parts.append(f"Technology Stack: {tech_list}")
        
        if business_data.get('semrush_data'):
            # Extract key SEMrush metrics
            semrush = business_data['semrush_data']
            if isinstance(semrush, dict):
                if semrush.get('errors'):
                    prompt_parts.append(f"SEO Issues: {len(semrush['errors'])} issues found")
                if semrush.get('warnings'):
                    prompt_parts.append(f"SEO Warnings: {len(semrush['warnings'])} warnings")
        
        prompt_parts.extend([
            "",
            "Please provide a comprehensive audit analysis including:",
            "1. Executive Summary (2-3 sentences)",
            "2. Key Findings (3-4 specific findings)",
            "3. Priority Recommendations (3-4 actionable recommendations)",
            "4. Overall Assessment (strengths and areas for improvement)",
            "",
            "Format your response as JSON with the following structure:",
            '{"executive_summary": "...", "key_findings": ["...", "..."], "recommendations": ["...", "..."], "overall_assessment": "..."}'
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_analysis_response(self, analysis_text: str, business_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and structure the LLM analysis response."""
        try:
            # Try to extract JSON from the response
            start_idx = analysis_text.find('{')
            end_idx = analysis_text.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_text = analysis_text[start_idx:end_idx]
                parsed = json.loads(json_text)
                
                # Validate required fields
                required_fields = ['executive_summary', 'key_findings', 'recommendations']
                if all(field in parsed for field in required_fields):
                    return parsed
            
            # Fallback: parse as text
            return self._parse_text_analysis(analysis_text)
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse LLM analysis as JSON: {e}")
            return self._parse_text_analysis(analysis_text)
    
    def _parse_text_analysis(self, text: str) -> Dict[str, Any]:
        """Parse analysis from plain text response."""
        lines = text.split('\n')
        
        analysis = {
            'executive_summary': 'Comprehensive website audit completed.',
            'key_findings': [],
            'recommendations': [],
            'overall_assessment': 'See detailed findings and recommendations below.'
        }
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Detect sections
            if 'summary' in line.lower():
                current_section = 'executive_summary'
            elif 'finding' in line.lower():
                current_section = 'key_findings'
            elif 'recommendation' in line.lower():
                current_section = 'recommendations'
            elif 'assessment' in line.lower():
                current_section = 'overall_assessment'
            elif line.startswith('•') or line.startswith('-') or line.startswith('*'):
                # Bullet point
                item = line[1:].strip()
                if current_section in ['key_findings', 'recommendations'] and item:
                    analysis[current_section].append(item)
            elif current_section and len(line) > 20:  # Substantial text
                if current_section in ['executive_summary', 'overall_assessment']:
                    analysis[current_section] = line
                elif current_section in ['key_findings', 'recommendations']:
                    analysis[current_section].append(line)
        
        return analysis
    
    def _generate_fallback_analysis(self, business_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate basic analysis when LLM is unavailable."""
        findings = []
        recommendations = []
        
        # Analyze PageSpeed
        page_speed = business_data.get('page_speed', 0)
        if page_speed > 0:
            if page_speed >= 90:
                findings.append(f"Excellent website performance with PageSpeed score of {page_speed}/100")
            elif page_speed >= 70:
                findings.append(f"Good website performance with PageSpeed score of {page_speed}/100")
                recommendations.append("Consider optimizing images and reducing JavaScript to improve load times")
            else:
                findings.append(f"Website performance needs improvement with PageSpeed score of {page_speed}/100")
                recommendations.append("Implement performance optimizations: image compression, code minification, and caching")
        
        # Analyze technology stack
        tech_stack = business_data.get('tech_stack', [])
        if tech_stack:
            modern_techs = ['React', 'Vue', 'Angular', 'Next.js', 'Gatsby']
            if any(tech in str(tech_stack) for tech in modern_techs):
                findings.append("Modern technology stack detected")
            else:
                recommendations.append("Consider upgrading to modern web technologies for better performance and SEO")
        
        # Analyze SEMrush data
        semrush_data = business_data.get('semrush_data', {})
        if isinstance(semrush_data, dict):
            errors = semrush_data.get('errors', [])
            warnings = semrush_data.get('warnings', [])
            
            if errors:
                findings.append(f"SEO audit identified {len(errors)} critical issues requiring attention")
                recommendations.append("Address critical SEO issues to improve search engine visibility")
            
            if warnings:
                findings.append(f"SEO audit found {len(warnings)} optimization opportunities")
                recommendations.append("Implement SEO best practices to enhance search rankings")
        
        # Default recommendations if none found
        if not recommendations:
            recommendations = [
                "Optimize website loading speed for better user experience",
                "Implement responsive design for mobile users",
                "Improve SEO metadata and content structure"
            ]
        
        # Default findings if none found
        if not findings:
            findings = [
                "Website audit completed using available data sources",
                "Basic performance and technical analysis conducted"
            ]
        
        return {
            'executive_summary': f"Comprehensive audit completed for {business_data.get('name', 'the business')}. Analysis covers website performance, technology stack, and SEO factors.",
            'key_findings': findings,
            'recommendations': recommendations,
            'overall_assessment': "This audit provides actionable insights to improve website performance and online presence."
        }
    
    def _build_report_content(
        self,
        business_data: Dict[str, Any],
        audit_analysis: Dict[str, Any],
        customer_email: str,
        report_id: str
    ) -> List[Dict[str, Any]]:
        """Build the comprehensive PDF report content structure."""
        content = []
        
        # Title page
        content.extend([
            {"type": "title", "text": "Website Audit Report"},
            {"type": "spacer", "height": 20},
            {"type": "subtitle", "text": business_data.get('name', 'Business Name')},
            {"type": "spacer", "height": 30},
            {
                "type": "paragraph",
                "text": f"Report ID: {report_id}",
                "style": "CustomBodyText"
            },
            {
                "type": "paragraph",
                "text": f"Generated: {datetime.now().strftime('%B %d, %Y')}",
                "style": "CustomBodyText"
            },
            {
                "type": "paragraph",
                "text": f"Prepared for: {customer_email}",
                "style": "CustomBodyText"
            },
            {"type": "spacer", "height": 40}
        ])
        
        # Executive Summary
        content.extend([
            {"type": "section_header", "text": "Executive Summary"},
            {
                "type": "paragraph",
                "text": audit_analysis.get('executive_summary', 'Audit completed successfully.'),
                "style": "CustomBodyText"
            },
            {"type": "spacer", "height": 20}
        ])
        
        # Business Information
        content.extend([
            {"type": "section_header", "text": "Business Information"},
            {
                "type": "table",
                "data": self._build_business_info_table(business_data),
                "style": "default"
            },
            {"type": "spacer", "height": 20}
        ])
        
        # Technical Analysis
        content.extend([
            {"type": "section_header", "text": "Technical Analysis"},
            {
                "type": "table",
                "data": self._build_technical_analysis_table(business_data),
                "style": "default"
            },
            {"type": "spacer", "height": 20}
        ])
        
        # Key Findings
        content.extend([
            {"type": "section_header", "text": "Key Findings"},
        ])
        
        findings = audit_analysis.get('key_findings', [])
        for i, finding in enumerate(findings[:5], 1):  # Limit to 5 findings
            content.append({
                "type": "paragraph",
                "text": f"{i}. {finding}",
                "style": "CustomBodyText"
            })
        
        content.append({"type": "spacer", "height": 20})
        
        # Recommendations
        content.extend([
            {"type": "section_header", "text": "Priority Recommendations"},
        ])
        
        recommendations = audit_analysis.get('recommendations', [])
        for i, recommendation in enumerate(recommendations[:5], 1):  # Limit to 5 recommendations
            content.append({
                "type": "paragraph",
                "text": f"{i}. {recommendation}",
                "style": "CustomBodyText"
            })
        
        content.append({"type": "spacer", "height": 20})
        
        # Overall Assessment
        if audit_analysis.get('overall_assessment'):
            content.extend([
                {"type": "section_header", "text": "Overall Assessment"},
                {
                    "type": "paragraph",
                    "text": audit_analysis['overall_assessment'],
                    "style": "CustomBodyText"
                },
                {"type": "spacer", "height": 20}
            ])
        
        # Data Sources
        content.extend([
            {"type": "section_header", "text": "Analysis Methodology"},
            {
                "type": "paragraph",
                "text": "This audit was conducted using multiple data sources and analysis techniques:",
                "style": "CustomBodyText"
            }
        ])
        
        data_sources = business_data.get('audit_metadata', {}).get('data_sources', [])
        for source in data_sources:
            content.append({
                "type": "paragraph",
                "text": f"• {source}",
                "style": "CustomBodyText"
            })
        
        content.append({"type": "spacer", "height": 30})
        
        # Footer
        content.extend([
            {
                "type": "paragraph",
                "text": "This report was generated by Anthrasite Digital's automated audit system.",
                "style": "CustomBodyText"
            },
            {
                "type": "paragraph",
                "text": "For questions about this report, please contact support.",
                "style": "CustomBodyText"
            }
        ])
        
        return content
    
    def _build_business_info_table(self, business_data: Dict[str, Any]) -> List[List[str]]:
        """Build business information table."""
        table_data = [["Property", "Value"]]
        
        info_fields = [
            ("Business Name", business_data.get('name', 'N/A')),
            ("Industry", business_data.get('category', 'N/A')),
            ("Website", business_data.get('website', 'N/A')),
            ("Location", self._format_location(business_data)),
            ("Phone", business_data.get('phone', 'N/A')),
            ("Email", business_data.get('email', 'N/A'))
        ]
        
        for field_name, value in info_fields:
            table_data.append([field_name, str(value) if value else 'N/A'])
        
        return table_data
    
    def _build_technical_analysis_table(self, business_data: Dict[str, Any]) -> List[List[str]]:
        """Build technical analysis table."""
        table_data = [["Metric", "Value", "Assessment"]]
        
        # PageSpeed analysis
        page_speed = business_data.get('page_speed')
        if page_speed is not None:
            if page_speed >= 90:
                assessment = "Excellent"
            elif page_speed >= 70:
                assessment = "Good"
            elif page_speed >= 50:
                assessment = "Needs Improvement"
            else:
                assessment = "Poor"
            
            table_data.append(["PageSpeed Score", f"{page_speed}/100", assessment])
        
        # Technology stack
        tech_stack = business_data.get('tech_stack', [])
        if tech_stack:
            tech_count = len(tech_stack)
            tech_preview = ', '.join(tech_stack[:3])
            if tech_count > 3:
                tech_preview += f" + {tech_count - 3} more"
            table_data.append(["Technologies", tech_preview, f"{tech_count} detected"])
        
        # SEO analysis from SEMrush
        semrush_data = business_data.get('semrush_data', {})
        if isinstance(semrush_data, dict):
            errors = semrush_data.get('errors', [])
            warnings = semrush_data.get('warnings', [])
            
            if errors or warnings:
                total_issues = len(errors) + len(warnings)
                if total_issues == 0:
                    assessment = "Excellent"
                elif total_issues <= 5:
                    assessment = "Good"
                elif total_issues <= 15:
                    assessment = "Needs Attention"
                else:
                    assessment = "Requires Optimization"
                
                table_data.append([
                    "SEO Analysis",
                    f"{len(errors)} errors, {len(warnings)} warnings",
                    assessment
                ])
        
        # Overall score
        score = business_data.get('score', 0)
        if score > 0:
            if score >= 80:
                assessment = "Excellent"
            elif score >= 60:
                assessment = "Good"
            elif score >= 40:
                assessment = "Fair"
            else:
                assessment = "Needs Improvement"
            
            table_data.append(["Overall Score", f"{score}/100", assessment])
        
        return table_data
    
    def _format_location(self, business_data: Dict[str, Any]) -> str:
        """Format business location from available data."""
        parts = []
        
        if business_data.get('city'):
            parts.append(business_data['city'])
        if business_data.get('state'):
            parts.append(business_data['state'])
        if business_data.get('zip'):
            parts.append(business_data['zip'])
        
        if parts:
            return ', '.join(parts)
        elif business_data.get('address'):
            return business_data['address']
        else:
            return 'N/A'
    
    async def _generate_minimal_report(
        self,
        business_name: str,
        customer_email: str,
        report_id: str,
        output_path: Optional[str] = None,
        return_bytes: bool = False
    ) -> Union[str, bytes]:
        """Generate a minimal report when business data is not available."""
        logger.info(f"Generating minimal report for {business_name}")
        
        content = [
            {"type": "title", "text": "Website Audit Report"},
            {"type": "spacer", "height": 20},
            {"type": "subtitle", "text": business_name},
            {"type": "spacer", "height": 30},
            {
                "type": "paragraph",
                "text": f"Report ID: {report_id}",
                "style": "CustomBodyText"
            },
            {
                "type": "paragraph",
                "text": f"Generated: {datetime.now().strftime('%B %d, %Y')}",
                "style": "CustomBodyText"
            },
            {
                "type": "paragraph",
                "text": f"Prepared for: {customer_email}",
                "style": "CustomBodyText"
            },
            {"type": "spacer", "height": 40},
            {"type": "section_header", "text": "Report Status"},
            {
                "type": "paragraph",
                "text": "This audit report has been prepared for your business. Due to limited data availability at the time of generation, this report contains general recommendations for website optimization.",
                "style": "CustomBodyText"
            },
            {"type": "spacer", "height": 20},
            {"type": "section_header", "text": "General Recommendations"},
            {
                "type": "paragraph",
                "text": "• Optimize website loading speed for better user experience",
                "style": "CustomBodyText"
            },
            {
                "type": "paragraph",
                "text": "• Implement responsive design for mobile compatibility",
                "style": "CustomBodyText"
            },
            {
                "type": "paragraph",
                "text": "• Improve SEO metadata and content structure",
                "style": "CustomBodyText"
            },
            {
                "type": "paragraph",
                "text": "• Ensure website security with SSL certificates",
                "style": "CustomBodyText"
            },
            {
                "type": "paragraph",
                "text": "• Regular content updates and maintenance",
                "style": "CustomBodyText"
            },
            {"type": "spacer", "height": 30},
            {
                "type": "paragraph",
                "text": "For a more detailed analysis, please ensure your website is accessible for automated scanning.",
                "style": "CustomBodyText"
            }
        ]
        
        if output_path or return_bytes:
            return self.pdf_generator.generate_document(
                content=content,
                output_path=output_path,
                return_bytes=return_bytes
            )
        else:
            # Generate to temporary file
            temp_dir = tempfile.mkdtemp()
            temp_path = os.path.join(temp_dir, f"{report_id}.pdf")
            return self.pdf_generator.generate_document(
                content=content,
                output_path=temp_path,
                return_bytes=False
            )


# Convenience function for external usage
async def generate_audit_report(
    business_name: str,
    customer_email: str,
    report_id: str,
    output_path: Optional[str] = None,
    return_bytes: bool = False
) -> Union[str, bytes]:
    """
    Convenience function to generate an audit report.
    
    Args:
        business_name: Name of the business to audit
        customer_email: Customer email address
        report_id: Unique report identifier
        output_path: Path to save PDF file
        return_bytes: Return PDF as bytes instead of file path
        
    Returns:
        Path to generated PDF or bytes content
    """
    generator = AuditReportGenerator()
    return await generator.generate_audit_report(
        business_name, customer_email, report_id, output_path, return_bytes
    )