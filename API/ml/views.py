# ml/views.py
import json
import logging
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.contrib.auth.models import User
import jwt
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import os

logger = logging.getLogger(__name__)

def get_user_from_token(request):
    """Extract user from JWT token in request"""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        logger.warning("No Authorization header found")
        return None
    
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        logger.warning(f"Invalid Authorization header format: {auth_header[:50]}")
        return None
    
    token = parts[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user = User.objects.get(id=payload['user_id'])
        logger.info(f"Authenticated user: {user.username} (ID: {user.id})")
        return user
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        return None
    except User.DoesNotExist:
        logger.warning(f"User not found for ID in token")
        return None

@csrf_exempt
@require_http_methods(["POST"])
def classify_document(request):
    """Classify document type using AI"""
    logger.info("=" * 50)
    logger.info("DOCUMENT CLASSIFICATION REQUEST")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Content-Type: {request.content_type}")
    logger.info(f"FILES keys: {list(request.FILES.keys())}")
    logger.info(f"POST keys: {list(request.POST.keys())}")
    
    try:
        # Get user for logging
        user = get_user_from_token(request)
        logger.info(f"User: {user.username if user else 'Anonymous'}")
        
        # Get the uploaded file - check multiple possible keys
        file = None
        for key in ['file', 'document', 'upload', 'deposit_slip']:
            if key in request.FILES:
                file = request.FILES[key]
                logger.info(f"Found file with key '{key}': {file.name}, size: {file.size} bytes")
                break
        
        if not file:
            logger.error("No file found in request")
            return JsonResponse({
                "success": False,
                "error": "No file uploaded. Please upload a file with key 'file'",
                "document_type": "unknown",
                "confidence": 0,
                "is_valid": False
            }, status=422)
        
        # Validate file size (5MB max)
        if file.size > 5 * 1024 * 1024:
            logger.warning(f"File too large: {file.size} bytes")
            return JsonResponse({
                "success": False,
                "error": f"File too large: {file.size} bytes. Max 5MB",
                "document_type": "unknown",
                "confidence": 0,
                "is_valid": False
            }, status=422)
        
        # Validate file type
        content_type = getattr(file, 'content_type', '')
        file_name = file.name.lower()
        
        allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg']
        
        if content_type not in allowed_types and not any(
            file_name.endswith(ext) for ext in ['.pdf', '.jpg', '.jpeg', '.png']
        ):
            logger.warning(f"Invalid file type: {content_type}, {file_name}")
            return JsonResponse({
                "success": False,
                "error": f"Invalid file type: {content_type or file_name}. Only PDF, JPG, and PNG files are allowed",
                "document_type": "unknown",
                "confidence": 0,
                "is_valid": False
            }, status=422)
        
        # For now, return a mock classification response
        # In production, you would call your actual ML model here
        
        # Determine document type based on filename
        document_type = "unknown"
        confidence = 0.5
        
        if any(kw in file_name for kw in ['cv', 'curriculum', 'vitae', 'resume']):
            document_type = "Curriculum Vitae (CV)"
            confidence = 0.85
        elif any(kw in file_name for kw in ['id', 'passport', 'identification', 'national']):
            document_type = "Copy of ID / Passport"
            confidence = 0.85
        elif any(kw in file_name for kw in ['certificate', 'msce', 'diploma', 'degree']):
            document_type = "MSCE Certificate"
            confidence = 0.85
        elif any(kw in file_name for kw in ['transcript', 'results', 'academic']):
            document_type = "Transcript"
            confidence = 0.80
        elif any(kw in file_name for kw in ['recommendation', 'reference', 'letter']):
            document_type = "Recommendation Letter"
            confidence = 0.85
        elif any(kw in file_name for kw in ['deposit', 'slip', 'payment', 'receipt', 'bank']):
            document_type = "deposit_slip"
            confidence = 0.90
        
        logger.info(f"Document classified as: {document_type} with {confidence*100:.0f}% confidence")
        
        return JsonResponse({
            "success": True,
            "document_type": document_type,
            "confidence": confidence,
            "is_valid": confidence >= 0.6,
            "extracted_preview": {
                "has_reference": document_type == "deposit_slip",
                "has_amount": document_type == "deposit_slip",
                "has_bank": document_type == "deposit_slip"
            },
            "message": f"Document classified as {document_type} with {confidence*100:.0f}% confidence"
        })
        
    except Exception as e:
        logger.error(f"Error classifying document: {str(e)}", exc_info=True)
        return JsonResponse({
            "success": False,
            "error": str(e),
            "document_type": "unknown",
            "confidence": 0,
            "is_valid": False
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def validate_document(request):
    """Validate document against expected type"""
    logger.info("=" * 50)
    logger.info("DOCUMENT VALIDATION REQUEST")
    
    try:
        user = get_user_from_token(request)
        logger.info(f"User: {user.username if user else 'Anonymous'}")
        
        # Get file
        file = None
        for key in ['file', 'document']:
            if key in request.FILES:
                file = request.FILES[key]
                logger.info(f"Found file: {file.name}")
                break
        
        if not file:
            return JsonResponse({
                "success": False,
                "error": "No file provided",
                "is_valid": False,
                "confidence": 0,
                "message": "No file uploaded"
            }, status=422)
        
        expected_type = request.POST.get('expected_type', '')
        logger.info(f"Expected type: {expected_type}")
        
        # Simple validation based on filename
        file_name = file.name.lower()
        confidence = 0.7
        
        # Check if filename matches expected type
        is_valid = False
        if expected_type == "MSCE Certificate" and any(kw in file_name for kw in ['certificate', 'msce']):
            is_valid = True
            confidence = 0.85
        elif expected_type == "Copy of ID / Passport" and any(kw in file_name for kw in ['id', 'passport', 'national']):
            is_valid = True
            confidence = 0.85
        elif expected_type == "Curriculum Vitae (CV)" and any(kw in file_name for kw in ['cv', 'curriculum', 'resume']):
            is_valid = True
            confidence = 0.85
        elif expected_type == "deposit_slip" and any(kw in file_name for kw in ['deposit', 'slip', 'payment', 'receipt']):
            is_valid = True
            confidence = 0.90
        else:
            # Not a clear match
            is_valid = False
            confidence = 0.3
        
        return JsonResponse({
            "success": True,
            "is_valid": is_valid,
            "confidence": confidence,
            "message": f"Document validation {'passed' if is_valid else 'failed'}"
        })
        
    except Exception as e:
        logger.error(f"Error validating document: {str(e)}", exc_info=True)
        return JsonResponse({
            "success": False,
            "error": str(e),
            "is_valid": False,
            "confidence": 0,
            "message": "Validation failed"
        }, status=500)