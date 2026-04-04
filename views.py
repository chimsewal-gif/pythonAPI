# api/views.py
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
import json

@ensure_csrf_cookie
def get_csrf_token(request):
    """Get CSRF token for the session"""
    return JsonResponse({'csrfToken': get_token(request)})

def current_user(request):
    """Get current user information"""
    return JsonResponse({
        'is_authenticated': request.user.is_authenticated,
        'id': request.user.id if request.user.is_authenticated else None,
        'username': request.user.username if request.user.is_authenticated else None,
        'email': request.user.email if request.user.is_authenticated else None,
    })

@login_required
@require_http_methods(["POST"])
def create_department(request):
    """Create a new department"""
    try:
        # Parse JSON data
        data = json.loads(request.body)
        
        # Validate required fields
        required_fields = ['name', 'code']
        for field in required_fields:
            if field not in data or not data[field].strip():
                return JsonResponse({
                    'error': f'{field} is required'
                }, status=400)
        
        # Basic validation
        if len(data['code']) > 10:
            return JsonResponse({
                'error': 'Department code must be 10 characters or less'
            }, status=400)
        
        # Here you would typically save to database
        # For now, we'll return a success response
        department_data = {
            'id': 1,  # This would be the actual ID from database
            'name': data['name'],
            'code': data['code'],
            'description': data.get('description', ''),
            'head_of_department': data.get('head_of_department', ''),
            'email': data.get('email', ''),
            'phone': data.get('phone', ''),
            'established_year': data.get('established_year'),
            'is_active': data.get('is_active', True),
        }
        
        return JsonResponse({
            'success': True,
            'message': 'Department created successfully',
            'department': department_data
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'error': f'Server error: {str(e)}'
        }, status=500)