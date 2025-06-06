"""
Mock HTTP server for browser testing.

This module provides a simple HTTP server that serves the static HTML files
and mocks API endpoints for browser-based BDD tests.
"""

import json
import os
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Dict, Any
from urllib.parse import urlparse, parse_qs


class MockAPIHandler(SimpleHTTPRequestHandler):
    """HTTP request handler that serves static files and mocks API endpoints."""

    # Mock data store
    mock_data = {
        'errors': [
            {
                'id': 'err-001',
                'timestamp': '2024-01-15T10:30:00Z',
                'stage': 'scrape',
                'operation': 'fetch_website',
                'severity': 'critical',
                'category': 'network',
                'business_id': 'biz-123',
                'content_preview': 'Connection timeout after 30s'
            },
            {
                'id': 'err-002',
                'timestamp': '2024-01-15T11:15:00Z',
                'stage': 'enrich',
                'operation': 'analyze_tech_stack',
                'severity': 'medium',
                'category': 'validation',
                'business_id': 'biz-456',
                'content_preview': 'Invalid HTML structure detected'
            }
        ],
        'businesses': [
            {
                'id': 1,
                'name': 'Test Restaurant',
                'email': 'test@restaurant.com',
                'website': 'https://testrestaurant.com',
                'category': 'restaurant',
                'score': 85,
                'status': 'pending',
                'city': 'San Francisco',
                'state': 'CA',
                'created_at': '2024-01-15T09:00:00Z',
                'address': '123 Main St',
                'archived': False
            },
            {
                'id': 2,
                'name': 'Sample Shop',
                'email': 'info@sampleshop.com',
                'website': 'https://sampleshop.com',
                'category': 'retail',
                'score': 72,
                'status': 'pending',
                'city': 'Los Angeles',
                'state': 'CA',
                'created_at': '2024-01-15T08:30:00Z',
                'address': '456 Oak Ave',
                'archived': False
            },
            {
                'id': 3,
                'name': 'Old Business',
                'email': 'old@business.com',
                'website': None,
                'category': 'service',
                'score': 45,
                'status': 'archived',
                'city': 'Portland',
                'state': 'OR',
                'created_at': '2024-01-10T12:00:00Z',
                'address': '789 Pine St',
                'archived': True,
                'archive_reason': 'irrelevant'
            }
        ],
        'qualification_criteria': [
            {
                'id': 1,
                'name': 'High Value Lead',
                'min_score': 80,
                'description': 'Leads with high potential value'
            },
            {
                'id': 2,
                'name': 'Standard Qualification',
                'min_score': 60,
                'description': 'Standard qualification criteria'
            }
        ],
        'sales_team': [
            {
                'user_id': 'user-1',
                'name': 'John Doe',
                'email': 'john@company.com',
                'role': 'Senior Sales Rep',
                'current_capacity': 3,
                'max_capacity': 10,
                'is_active': True
            },
            {
                'user_id': 'user-2',
                'name': 'Jane Smith',
                'email': 'jane@company.com',
                'role': 'Sales Rep',
                'current_capacity': 8,
                'max_capacity': 8,
                'is_active': True
            }
        ],
        'queue_entries': [
            {
                'id': 1,
                'business': {'name': 'Test Restaurant', 'email': 'test@restaurant.com'},
                'qualification_score': 85,
                'priority': 80,
                'status': 'qualified',
                'assignee': None,
                'created_at': '2024-01-15T09:00:00Z'
            },
            {
                'id': 2,
                'business': {'name': 'Sample Shop', 'email': 'info@sampleshop.com'},
                'qualification_score': 72,
                'priority': 65,
                'status': 'assigned',
                'assignee': {'name': 'John Doe'},
                'created_at': '2024-01-15T08:30:00Z'
            }
        ]
    }

    def __init__(self, *args, **kwargs):
        # Set the directory to serve static files from
        self.static_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'leadfactory', 'static')
        super().__init__(*args, directory=self.static_dir, **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query_params = parse_qs(parsed_path.query)

        # API endpoints
        if path.startswith('/api/'):
            self.handle_api_get(path, query_params)
        else:
            # Serve static files
            super().do_GET()

    def do_POST(self):
        """Handle POST requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path.startswith('/api/'):
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else b''

            try:
                request_data = json.loads(post_data.decode('utf-8')) if post_data else {}
            except json.JSONDecodeError:
                request_data = {}

            self.handle_api_post(path, request_data)
        else:
            self.send_error(404)

    def handle_api_get(self, path: str, query_params: Dict[str, list]):
        """Handle API GET requests."""
        if path == '/api/errors/dashboard-data':
            response = {
                'summary': {
                    'total_errors': len(self.mock_data['errors']),
                    'critical_errors': len([e for e in self.mock_data['errors'] if e['severity'] == 'critical']),
                    'successful_fixes_24h': 12
                },
                'active_alerts': []
            }
            self.send_json_response(response)

        elif path == '/api/logs':
            # Apply filters if provided
            logs = self.mock_data['errors'].copy()

            # Filter by severity
            severity = query_params.get('severity', [None])[0]
            if severity:
                logs = [log for log in logs if log['severity'] == severity]

            # Filter by category
            category = query_params.get('category', [None])[0]
            if category:
                logs = [log for log in logs if log['category'] == category]

            # Filter by stage
            stage = query_params.get('stage', [None])[0]
            if stage:
                logs = [log for log in logs if log['stage'] == stage]

            response = {
                'logs': logs,
                'pagination': {'total': len(logs)}
            }
            self.send_json_response(response)

        elif path == '/api/businesses':
            businesses = self.mock_data['businesses'].copy()

            # Apply search filter
            search = query_params.get('search', [None])[0]
            if search:
                businesses = [b for b in businesses
                            if search.lower() in b['name'].lower()
                            or search.lower() in (b['email'] or '').lower()]

            # Apply archived filter
            include_archived = query_params.get('include_archived', [None])[0]
            if include_archived == 'false':
                businesses = [b for b in businesses if not b.get('archived', False)]
            elif include_archived == 'true':
                businesses = [b for b in businesses if b.get('archived', False)]

            response = {
                'businesses': businesses,
                'total_count': len(businesses)
            }
            self.send_json_response(response)

        elif path == '/api/handoff/criteria':
            response = {
                'criteria': self.mock_data['qualification_criteria']
            }
            self.send_json_response(response)

        elif path == '/api/handoff/sales-team':
            response = {
                'members': self.mock_data['sales_team']
            }
            self.send_json_response(response)

        elif path == '/api/handoff/queue':
            response = {
                'entries': self.mock_data['queue_entries'],
                'total_count': len(self.mock_data['queue_entries'])
            }
            self.send_json_response(response)

        elif path == '/api/handoff/analytics/summary':
            response = {
                'summary': {
                    'total_queue_entries': len(self.mock_data['queue_entries']),
                    'unassigned_count': len([e for e in self.mock_data['queue_entries'] if not e['assignee']]),
                    'assigned_count': len([e for e in self.mock_data['queue_entries'] if e['assignee']]),
                    'contacted_count': 5
                },
                'status_breakdown': [
                    {'status': 'qualified', 'count': 8},
                    {'status': 'assigned', 'count': 12},
                    {'status': 'contacted', 'count': 5}
                ]
            }
            self.send_json_response(response)

        elif path == '/api/logs/stats':
            response = {
                'total_logs': 1250,
                'logs_by_type': {
                    'llm': 750,
                    'raw_html': 500
                },
                'logs_by_business': {
                    '1': 150,
                    '2': 120,
                    '3': 100
                },
                'date_range': {
                    'earliest': '2024-01-01T00:00:00Z',
                    'latest': '2024-01-15T12:00:00Z'
                }
            }
            self.send_json_response(response)

        else:
            self.send_error(404)

    def handle_api_post(self, path: str, request_data: Dict[str, Any]):
        """Handle API POST requests."""
        if path == '/api/errors/bulk-dismiss':
            response = {
                'results': {
                    'dismissed': request_data.get('error_ids', [])
                },
                'message': 'Successfully dismissed errors'
            }
            self.send_json_response(response)

        elif path == '/api/errors/bulk-fix':
            response = {
                'results': {
                    'summary': {
                        'successful_fixes': len(request_data.get('error_ids', [])),
                        'failed_fixes': 0,
                        'manual_intervention_required': 0
                    }
                }
            }
            self.send_json_response(response)

        elif path == '/api/errors/bulk-categorize':
            response = {
                'results': {
                    'updated': request_data.get('error_ids', [])
                },
                'message': 'Successfully updated errors'
            }
            self.send_json_response(response)

        elif path == '/api/handoff/qualify-bulk':
            response = {
                'operation_id': 'op-123',
                'message': 'Qualification started'
            }
            self.send_json_response(response)

        elif path == '/api/handoff/assign-bulk':
            response = {
                'operation_id': 'op-456',
                'message': 'Assignment started'
            }
            self.send_json_response(response)

        elif path.startswith('/api/handoff/operations/'):
            operation_id = path.split('/')[-1]
            if operation_id == 'op-123':  # Qualification operation
                response = {
                    'status': 'completed',
                    'total_count': len(request_data.get('business_ids', [])),
                    'success_count': len(request_data.get('business_ids', [])),
                    'failure_count': 0,
                    'operation_details': {
                        'qualified_count': 2,
                        'rejected_count': 1,
                        'insufficient_data_count': 0
                    }
                }
            elif operation_id == 'op-456':  # Assignment operation
                response = {
                    'status': 'completed',
                    'total_count': len(request_data.get('queue_entry_ids', [])),
                    'success_count': len(request_data.get('queue_entry_ids', [])),
                    'failure_count': 0
                }
            else:
                response = {'status': 'not_found'}

            self.send_json_response(response)

        elif path == '/api/businesses/bulk-reject':
            business_ids = request_data.get('business_ids', [])
            response = {
                'archived_count': len(business_ids),
                'message': f'Successfully archived {len(business_ids)} businesses'
            }
            self.send_json_response(response)

        elif path == '/api/businesses/restore':
            business_ids = request_data.get('business_ids', [])
            response = {
                'restored_count': len(business_ids),
                'message': f'Successfully restored {len(business_ids)} businesses'
            }
            self.send_json_response(response)

        else:
            self.send_error(404)

    def send_json_response(self, data: Dict[str, Any], status: int = 200):
        """Send a JSON response."""
        response_body = json.dumps(data).encode('utf-8')

        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response_body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        self.wfile.write(response_body)

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        """Override to reduce log noise in tests."""
        # Only log errors, not all requests
        if '404' in str(args) or '500' in str(args):
            super().log_message(format, *args)


class MockServer:
    """Mock HTTP server for browser tests."""

    def __init__(self, host: str = 'localhost', port: int = 8080):
        self.host = host
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        """Start the mock server."""
        self.server = HTTPServer((self.host, self.port), MockAPIHandler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()

        # Wait a bit for the server to start
        time.sleep(0.1)

        print(f"Mock server started at http://{self.host}:{self.port}")

    def stop(self):
        """Stop the mock server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1)

        print("Mock server stopped")

    @property
    def url(self):
        """Get the base URL of the mock server."""
        return f"http://{self.host}:{self.port}"


# Global mock server instance for tests
_mock_server = None


def get_mock_server():
    """Get the global mock server instance."""
    global _mock_server
    if _mock_server is None:
        _mock_server = MockServer()
    return _mock_server


def start_mock_server():
    """Start the global mock server."""
    server = get_mock_server()
    server.start()
    return server


def stop_mock_server():
    """Stop the global mock server."""
    global _mock_server
    if _mock_server:
        _mock_server.stop()
        _mock_server = None
