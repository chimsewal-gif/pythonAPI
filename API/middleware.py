# API/middleware.py
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse

class CorsMiddleware(MiddlewareMixin):
    """Middleware to handle CORS and OPTIONS requests"""
    
    def process_request(self, request):
        # Handle preflight OPTIONS requests
        if request.method == 'OPTIONS':
            response = HttpResponse()
            response['Access-Control-Allow-Origin'] = 'http://127.0.0.1:3000'
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'accept, accept-encoding, authorization, content-type, dnt, origin, user-agent, x-csrftoken, x-requested-with'
            response['Access-Control-Max-Age'] = '86400'
            response.status_code = 200
            return response
        return None
    
    def process_response(self, request, response):
        # Add CORS headers to all responses
        origin = request.META.get('HTTP_ORIGIN')
        allowed_origins = ['http://localhost:3000', 'http://127.0.0.1:3000']
        
        if origin in allowed_origins:
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'accept, accept-encoding, authorization, content-type, dnt, origin, user-agent, x-csrftoken, x-requested-with'
        
        return response