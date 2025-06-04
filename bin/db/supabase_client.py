"""
Supabase client configuration for LeadFactory.

This module provides a configured Supabase client for use across the application.
"""

import os
from supabase import create_client, Client
from leadfactory.config import get_env

# Get Supabase configuration from environment
SUPABASE_URL = get_env("SUPABASE_URL")
SUPABASE_KEY = get_env("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")

# Create the Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
