"""
AI-powered content generation for email personalization.

This module generates personalized email content based on business data,
website analysis, and scoring insights.
"""

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Tuple

from leadfactory.llm.client import LLMClient
from leadfactory.utils.logging import get_logger

logger = get_logger(__name__)


class AIContentGenerator:
    """Generates personalized AI content for emails."""

    def __init__(self):
        """Initialize the AI content generator."""
        self.llm_client = LLMClient()

    async def generate_email_improvements(
        self,
        business_data: dict,
        score_breakdown: Optional[dict] = None,
        website_analysis: Optional[dict] = None,
    ) -> list[str]:
        """Generate personalized improvement suggestions for a business.

        Args:
            business_data: Business information including name, vertical, website
            score_breakdown: Detailed scoring breakdown showing issues
            website_analysis: Analysis of current website issues

        Returns:
            List of improvement suggestions tailored to the business
        """
        try:
            # Build context for AI
            business_name = business_data.get("name", "the business")
            vertical = business_data.get("vertical", "general business")
            website = business_data.get("website", "")
            score = business_data.get("score", 0)

            # Create the prompt
            prompt = f"""Generate 5 specific website improvement suggestions for {business_name},
            a {vertical} business. Their current website ({website}) has an audit score of {score}/100.

            Based on the scoring breakdown, focus on:
            """

            # Add specific issues from score breakdown
            if score_breakdown:
                issues = []
                if score_breakdown.get("technology_score", 100) < 50:
                    issues.append("outdated technology stack")
                if score_breakdown.get("performance_score", 100) < 50:
                    issues.append("slow page loading speeds")
                if score_breakdown.get("seo_score", 100) < 50:
                    issues.append("poor search engine visibility")
                if score_breakdown.get("mobile_score", 100) < 50:
                    issues.append("lack of mobile optimization")

                if issues:
                    prompt += "\n- " + "\n- ".join(issues)

            prompt += """

            Generate 5 improvement suggestions that are:
            1. Specific to their industry ({vertical})
            2. Actionable and clear
            3. Focused on business value (more customers, better conversions)
            4. Written in a friendly, professional tone

            Return ONLY a JSON array of strings, no other text.
            Example: ["Improvement 1", "Improvement 2", ...]
            """

            # Get AI response
            response = await asyncio.to_thread(
                self.llm_client.chat_completion,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.7,
            )

            # Parse the response
            if (
                response
                and response.get("choices")
                and response["choices"][0].get("message")
            ):
                try:
                    content = response["choices"][0]["message"]["content"]
                    improvements = json.loads(content)
                    if isinstance(improvements, list) and len(improvements) >= 3:
                        return improvements[:5]  # Limit to 5
                except json.JSONDecodeError:
                    logger.warning("Failed to parse AI response as JSON")

            # Fallback to default improvements if AI fails
            return self._get_default_improvements(vertical, score_breakdown)

        except Exception as e:
            logger.error(f"Error generating AI improvements: {e}")
            return self._get_default_improvements(
                business_data.get("vertical", "general"), score_breakdown
            )

    async def generate_personalized_intro(
        self, business_data: dict, website_analysis: Optional[dict] = None
    ) -> str:
        """Generate a personalized introduction paragraph.

        Args:
            business_data: Business information
            website_analysis: Analysis of current website

        Returns:
            Personalized introduction paragraph
        """
        try:
            business_name = business_data.get("name", "your business")
            vertical = business_data.get("vertical", "business")
            city = business_data.get("city", "")
            state = business_data.get("state", "")

            location = f"{city}, {state}" if city and state else "your area"

            prompt = f"""Write a personalized introduction paragraph for an email to {business_name},
            a {vertical} business in {location}.

            The paragraph should:
            - Be 2-3 sentences
            - Mention something specific about their industry or location
            - Show understanding of their business needs
            - Lead into why they need a website update
            - Be friendly and professional

            Return ONLY the paragraph text, no quotes or formatting.
            """

            response = await asyncio.to_thread(
                self.llm_client.chat_completion,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.8,
            )

            if (
                response
                and response.get("choices")
                and response["choices"][0].get("message")
            ):
                return response["choices"][0]["message"]["content"].strip()

            # Fallback
            return f"I noticed your website could benefit from some modern updates to better serve {vertical} customers in {location}."

        except Exception as e:
            logger.error(f"Error generating personalized intro: {e}")
            return "I noticed your website could benefit from some modern updates to better serve your customers."

    async def generate_call_to_action(
        self, business_data: dict, improvements: list[str]
    ) -> str:
        """Generate a personalized call-to-action.

        Args:
            business_data: Business information
            improvements: List of suggested improvements

        Returns:
            Personalized call-to-action text
        """
        try:
            business_name = business_data.get("name", "your business")
            vertical = business_data.get("vertical", "business")

            # Identify the most impactful improvement
            top_improvement = (
                improvements[0] if improvements else "website improvements"
            )

            prompt = f"""Write a compelling call-to-action for {business_name} ({vertical} business).

            The main improvement we're offering is: {top_improvement}

            The CTA should:
            - Be 1-2 sentences
            - Create urgency without being pushy
            - Mention a specific benefit
            - Include "free consultation" or "free website audit"

            Return ONLY the CTA text, no quotes or formatting.
            """

            response = await asyncio.to_thread(
                self.llm_client.chat_completion,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.7,
            )

            if (
                response
                and response.get("choices")
                and response["choices"][0].get("message")
            ):
                return response["choices"][0]["message"]["content"].strip()

            # Fallback
            return "Let's discuss how these improvements can help grow your business. Schedule your free consultation today!"

        except Exception as e:
            logger.error(f"Error generating CTA: {e}")
            return "Schedule your free website consultation today and see how we can help grow your business!"

    def _get_default_improvements(
        self, vertical: str, score_breakdown: Optional[dict] = None
    ) -> list[str]:
        """Get default improvements based on vertical and scores.

        Args:
            vertical: Business vertical/industry
            score_breakdown: Scoring details

        Returns:
            List of default improvement suggestions
        """
        # Base improvements that apply to most businesses
        base_improvements = [
            "Mobile-first responsive design that looks professional on all devices",
            "Faster page loading speeds to reduce visitor bounce rates",
            "Clear call-to-action buttons that convert visitors into customers",
            "Search engine optimization to help local customers find you online",
            "Modern, clean design that builds trust with potential customers",
        ]

        # Vertical-specific improvements
        vertical_improvements = {
            "hvac": [
                "Online appointment scheduling for AC repairs and maintenance",
                "Service area maps showing your coverage zones",
                "Emergency service contact form for urgent requests",
                "Seasonal promotion banners for heating/cooling services",
                "Customer testimonials showcasing your reliability",
            ],
            "plumber": [
                "24/7 emergency contact form for urgent plumbing issues",
                "Service pricing calculator for common repairs",
                "Before/after gallery of your plumbing work",
                "Online booking system for routine maintenance",
                "Service area coverage map for local customers",
            ],
            "electrician": [
                "Safety certification badges prominently displayed",
                "Emergency electrical service request form",
                "Project portfolio showcasing residential and commercial work",
                "Online quote request system for electrical projects",
                "Educational content about electrical safety",
            ],
            "contractor": [
                "Project portfolio with before/after photos",
                "Online project estimate calculator",
                "Client testimonial videos and reviews",
                "Service specialization showcase",
                "Project timeline and process explanation",
            ],
            "restaurant": [
                "Online menu with mouth-watering food photos",
                "Table reservation system integrated with your workflow",
                "Customer reviews and ratings display",
                "Special events and promotion announcements",
                "Social media integration for daily specials",
            ],
            "retail": [
                "Product catalog with search and filter options",
                "Shopping cart for online orders or inquiries",
                "Store hours and location with directions",
                "New arrival and sale notifications",
                "Customer loyalty program integration",
            ],
        }

        # Get vertical-specific improvements or use base
        improvements = vertical_improvements.get(vertical.lower(), base_improvements)

        # Prioritize based on score breakdown if available
        if score_breakdown:
            prioritized = []

            # Add performance improvements if score is low
            if score_breakdown.get("performance_score", 100) < 50:
                prioritized.append(
                    "Lightning-fast page loading (currently taking too long)"
                )

            # Add mobile improvements if needed
            if score_breakdown.get("mobile_score", 100) < 50:
                prioritized.append("Full mobile optimization for smartphone users")

            # Add remaining improvements
            for imp in improvements:
                if imp not in prioritized and len(prioritized) < 5:
                    prioritized.append(imp)

            return prioritized[:5]

        return improvements[:5]


class EmailContentPersonalizer:
    """Orchestrates AI content generation for email campaigns."""

    def __init__(self):
        """Initialize the personalizer."""
        self.content_generator = AIContentGenerator()

    async def personalize_email_content(
        self, business_data: dict, template: str, score_data: Optional[dict] = None
    ) -> tuple[str, str, str]:
        """Generate fully personalized email content.

        Args:
            business_data: Business information
            template: Base email template HTML
            score_data: Scoring and analysis data

        Returns:
            Tuple of (subject, html_content, text_content)
        """
        try:
            # Generate AI content components
            improvements = await self.content_generator.generate_email_improvements(
                business_data, score_breakdown=score_data
            )

            intro = await self.content_generator.generate_personalized_intro(
                business_data
            )

            cta = await self.content_generator.generate_call_to_action(
                business_data, improvements
            )

            # Generate personalized subject line
            subject = self._generate_subject(business_data, improvements)

            # Inject AI content into template
            html_content = self._inject_ai_content(
                template, business_data, intro, improvements, cta
            )

            # Generate plain text version
            text_content = self._generate_text_version(
                business_data, intro, improvements, cta
            )

            return subject, html_content, text_content

        except Exception as e:
            logger.error(f"Error personalizing email content: {e}")
            # Return basic personalization as fallback
            return self._basic_personalization(business_data, template)

    def _generate_subject(self, business_data: dict, improvements: list[str]) -> str:
        """Generate personalized subject line."""
        business_name = business_data.get("name", "Your Business")

        # Pick most compelling improvement for subject
        if improvements and len(improvements) > 0:
            key_improvement = improvements[0].split(".")[0]  # First sentence
            if len(key_improvement) < 40:
                return f"{business_name}: {key_improvement}"

        # Fallback subjects
        return f"Website Improvement Ideas for {business_name}"

    def _inject_ai_content(
        self,
        template: str,
        business_data: dict,
        intro: str,
        improvements: list[str],
        cta: str,
    ) -> str:
        """Inject AI-generated content into email template."""
        # Start with basic replacements
        html_content = template

        # Replace introduction paragraph
        if "I noticed your website" in html_content:
            html_content = html_content.replace(
                'I noticed your website at <a href="{{business_website}}">{{business_website}}</a> and wanted to reach out with some ideas for improvement.',
                intro,
            )

        # Replace improvements list
        improvements_html = "\n".join(
            [f"                <li>{imp}</li>" for imp in improvements]
        )

        # Handle Handlebars syntax
        import re

        improvements_pattern = r"{{#each improvements}}.*?{{/each}}"
        html_content = re.sub(
            improvements_pattern, improvements_html, html_content, flags=re.DOTALL
        )

        # Also replace static improvements if present
        static_improvements = """
                <li>Modern, mobile-responsive design that looks great on all devices</li>
                <li>Improved search engine optimization (SEO) to help customers find you</li>
                <li>Clear calls-to-action to convert visitors into customers</li>
                <li>Professional branding that builds trust with potential clients</li>
                <li>Fast loading speeds for better user experience</li>
        """
        if static_improvements.strip() in html_content:
            html_content = html_content.replace(static_improvements, improvements_html)

        # Replace CTA text
        if "I'd love to discuss these ideas with you" in html_content:
            html_content = html_content.replace(
                "I'd love to discuss these ideas with you. Would you be available for a quick 15-minute call this week?",
                cta,
            )

        return html_content

    def _generate_text_version(
        self, business_data: dict, intro: str, improvements: list[str], cta: str
    ) -> str:
        """Generate plain text version of email."""
        business_name = business_data.get("name", "Business")
        contact_name = business_data.get("contact_name", "Business Owner")

        text_content = f"""
Hello {contact_name},

{intro}

Here's what we can do for {business_name}:

"""

        for i, improvement in enumerate(improvements, 1):
            text_content += f"{i}. {improvement}\n"

        text_content += f"""

{cta}

Schedule your free consultation at: https://calendly.com/anthrasite/website-consultation

Best regards,
The Anthrasite Team
        """

        return text_content

    def _basic_personalization(
        self, business_data: dict, template: str
    ) -> tuple[str, str, str]:
        """Basic personalization without AI content."""
        business_name = business_data.get("name", "Your Business")
        subject = f"Website Improvement Proposal for {business_name}"

        # Just do basic template replacements
        html_content = template
        text_content = "Please view the HTML version of this email."

        return subject, html_content, text_content


# Singleton instance
email_content_personalizer = EmailContentPersonalizer()
