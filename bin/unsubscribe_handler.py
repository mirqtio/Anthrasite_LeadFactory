#!/usr/bin/env python3
"""
Anthrasite Lead-Factory: Unsubscribe Handler
Handles unsubscribe requests for CAN-SPAM compliance.
"""

import os
import sys
from typing import Dict, List, Optional, Tuple, Any, Union

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import email queue functions
from bin.email_queue import add_unsubscribe, is_email_unsubscribed

# Import logging configuration
from utils.logging_config import get_logger

# Set up logging
logger = get_logger(__name__)
# Load environment variables
load_dotenv()

# Constants
PORT = int(os.getenv("UNSUBSCRIBE_PORT", "8080"))
# Default to localhost for security, can be overridden with UNSUBSCRIBE_HOST env var
HOST = os.getenv("UNSUBSCRIBE_HOST", "127.0.0.1")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Create FastAPI app
app = FastAPI(title="Anthrasite Lead-Factory Unsubscribe Handler")

# Create templates directory if it doesn't exist
templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
os.makedirs(templates_dir, exist_ok=True)

# Create templates
templates = Jinja2Templates(directory=templates_dir)

# Create unsubscribe template if it doesn't exist
unsubscribe_template_path = os.path.join(templates_dir, "unsubscribe.html")
if not os.path.exists(unsubscribe_template_path):
    with open(unsubscribe_template_path, "w") as f:
        f.write(
            """
<!DOCTYPE html>
<html>
<head>
    <title>Unsubscribe from Anthrasite Web Services</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
            background-color: #f9f9f9;
        }
        .container {
            max-width: 600px;
            margin: 50px auto;
            padding: 30px;
            background-color: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #eee;
        }
        .header h1 {
            color: #2c3e50;
            font-size: 24px;
            margin-bottom: 10px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        .form-group input, .form-group textarea, .form-group select {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
        }
        .form-group textarea {
            height: 100px;
        }
        .button {
            display: inline-block;
            background-color: #3498db;
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 4px;
            font-weight: bold;
            font-size: 16px;
            border: none;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .button:hover {
            background-color: #2980b9;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            font-size: 12px;
            color: #95a5a6;
            text-align: center;
        }
        .success-message {
            background-color: #d4edda;
            color: #155724;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
        }
        .error-message {
            background-color: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Unsubscribe from Anthrasite Web Services</h1>
            <p>We're sorry to see you go. Please confirm your email address below to unsubscribe.</p>
        </div>

        {% if success %}
        <div class="success-message">
            <p>You have been successfully unsubscribed. You will no longer receive emails from Anthrasite Web Services.</p>
        </div>
        {% endif %}

        {% if error %}
        <div class="error-message">
            <p>{{ error }}</p>
        </div>
        {% endif %}

        {% if not success %}
        <form method="post" action="/unsubscribe">
            <div class="form-group">
                <label for="email">Email Address:</label>
                <input type="email" id="email" name="email" value="{{ email }}" required>
            </div>
            <div class="form-group">
                <label for="reason">Reason for unsubscribing (optional):</label>
                <select id="reason" name="reason">
                    <option value="">-- Select a reason --</option>
                    <option value="not_interested">Not interested in the content</option>
                    <option value="too_many">Receiving too many emails</option>
                    <option value="never_signed_up">I never signed up for these emails</option>
                    <option value="other">Other</option>
                </select>
            </div>
            <div class="form-group">
                <label for="comments">Additional comments (optional):</label>
                <textarea id="comments" name="comments"></textarea>
            </div>
            <button type="submit" class="button">Unsubscribe</button>
        </form>
        {% endif %}

        <div class="footer">
            <p>Anthrasite Web Services<br>
            PO Box 12345<br>
            San Francisco, CA 94107</p>
            <p>&copy; 2025 Anthrasite Web Services. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
        """
        )

# Create success template if it doesn't exist
success_template_path = os.path.join(templates_dir, "unsubscribe_success.html")
if not os.path.exists(success_template_path):
    with open(success_template_path, "w") as f:
        f.write(
            """
<!DOCTYPE html>
<html>
<head>
    <title>Unsubscribe Successful</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
            background-color: #f9f9f9;
        }
        .container {
            max-width: 600px;
            margin: 50px auto;
            padding: 30px;
            background-color: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #eee;
        }
        .header h1 {
            color: #2c3e50;
            font-size: 24px;
            margin-bottom: 10px;
        }
        .success-message {
            background-color: #d4edda;
            color: #155724;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
            text-align: center;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            font-size: 12px;
            color: #95a5a6;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Unsubscribe Successful</h1>
        </div>

        <div class="success-message">
            <p>You have been successfully unsubscribed from Anthrasite Web Services emails.</p>
            <p>Your email address {{ email }} has been removed from our mailing list.</p>
        </div>

        <p>We're sorry to see you go. If you change your mind, you can always contact us to resubscribe.</p>

        <div class="footer">
            <p>Anthrasite Web Services<br>
            PO Box 12345<br>
            San Francisco, CA 94107</p>
            <p>&copy; 2025 Anthrasite Web Services. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
        """
        )


@app.get("/", response_class=HTMLResponse)
async def root():
    """Redirect to unsubscribe page."""
    return RedirectResponse(url="/unsubscribe")


@app.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe_page(request: Request, email: Optional[str] = None):
    """Render unsubscribe page."""
    return templates.TemplateResponse(
        "unsubscribe.html",
        {"request": request, "email": email or "", "success": False, "error": None},
    )


@app.post("/unsubscribe", response_class=HTMLResponse)
async def process_unsubscribe(
    request: Request,
    email: str = Form(...),
    reason: str | None = Form(None),
    comments: str | None = Form(None),
):
    """Process unsubscribe request."""
    # Validate email
    if not email or "@" not in email:
        return templates.TemplateResponse(
            "unsubscribe.html",
            {
                "request": request,
                "email": email,
                "success": False,
                "error": "Invalid email address",
            },
        )

    # Check if already unsubscribed
    if is_email_unsubscribed(email):
        return templates.TemplateResponse(
            "unsubscribe_success.html", {"request": request, "email": email}
        )

    # Combine reason and comments
    reason_text = reason or "No reason provided"
    if comments:
        reason_text += f" - Comments: {comments}"

    # Get client IP and user agent
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Add to unsubscribe list
    success = add_unsubscribe(email, reason_text, client_ip, user_agent)

    if success:
        logger.info(f"User unsubscribed: {email}, Reason: {reason_text}")
        return templates.TemplateResponse(
            "unsubscribe_success.html", {"request": request, "email": email}
        )
    else:
        return templates.TemplateResponse(
            "unsubscribe.html",
            {
                "request": request,
                "email": email,
                "success": False,
                "error": "An error occurred while processing your request. Please try again later.",
            },
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


def main():
    """Main function."""
    logger.info(f"Starting unsubscribe handler on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
