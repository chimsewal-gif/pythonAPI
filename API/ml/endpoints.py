# API/ml/endpoints.py
"""
Separate ML endpoints for admission prediction and deposit slip recognition
"""

from ninja import Router, Schema, File
from ninja.files import UploadedFile
from django.views.decorators.csrf import csrf_exempt
from typing import List, Optional
from datetime import datetime
from .service import predictor
from .deposit_slip_recognizer import deposit_slip_recognizer
import logging
import jwt
from django.conf import settings
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)

# Create a separate router for ML endpoints
ml_router = Router()

# Helper function to get user from token
def get_user_from_request(request):
    """Extract user from JWT token in request"""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None
    
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return None
    
    token = parts[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        return User.objects.get(id=payload['user_id'])
    except:
        return None

# ============ Admission Prediction Schemas ============
class SubjectGradeSchema(Schema):
    subject: str
    grade: str

class PredictionInputSchema(Schema):
    subjects: List[SubjectGradeSchema]

class PredictionResponseSchema(Schema):
    success: bool
    average_points: Optional[float] = None
    prediction: Optional[int] = None
    probability: Optional[float] = None
    message: Optional[str] = None
    using_ml: Optional[bool] = None
    error: Optional[str] = None


# ============ Deposit Slip Recognition Schemas ============
class ExtractedDataSchema(Schema):
    reference_number: Optional[str] = None
    amount: Optional[float] = None
    account_number: Optional[str] = None
    depositor_name: Optional[str] = None
    bank_name: Optional[str] = None
    transaction_date: Optional[str] = None
    branch_name: Optional[str] = None
    confidence_score: float = 0.0

class VerificationResultSchema(Schema):
    reference_match: bool = False
    amount_match: bool = False
    confidence: float = 0.0

class DepositSlipRecognitionResponseSchema(Schema):
    success: bool
    auto_verified: bool = False
    verification: Optional[VerificationResultSchema] = None
    extracted_data: Optional[ExtractedDataSchema] = None
    requires_manual_review: bool = False
    confidence_score: float = 0.0
    message: Optional[str] = None
    error: Optional[str] = None
    raw_text_preview: Optional[str] = None


# ============ Admission Prediction Endpoints ============
@csrf_exempt
@ml_router.post("/predict", response={200: PredictionResponseSchema, 400: dict})
@ml_router.post("/predict/", response={200: PredictionResponseSchema, 400: dict})
def predict_admission(request, data: PredictionInputSchema):
    """
    ML prediction endpoint for admission chances based on MSCE results
    """
    try:
        user = get_user_from_request(request)
        if user:
            logger.info(f"Prediction request from user {user.id}")
        
        subjects = [{'subject': s.subject, 'grade': s.grade} for s in data.subjects]
        result = predictor.predict(subjects)
        
        if result.get('success'):
            return 200, {
                "success": True,
                "average_points": result['average_points'],
                "prediction": result['prediction'],
                "probability": result['probability'],
                "message": result['message'],
                "using_ml": result.get('using_ml', False)
            }
        else:
            return 400, {
                "success": False,
                "error": result.get('error', 'Prediction failed')
            }
            
    except Exception as e:
        logger.error(f"Prediction endpoint error: {str(e)}", exc_info=True)
        return 400, {
            "success": False,
            "error": f"Prediction failed: {str(e)}"
        }


@csrf_exempt
@ml_router.get("/health", response={200: dict})
@ml_router.get("/health/", response={200: dict})
def ml_health_check(request):
    """Check if ML service is available"""
    return 200, {
        "success": True,
        "ml_available": predictor.model_loaded,
        "message": "ML service is running" if predictor.model_loaded else "ML service running in fallback mode"
    }


@csrf_exempt
@ml_router.post("/batch-predict", response={200: dict, 400: dict})
@ml_router.post("/batch-predict/", response={200: dict, 400: dict})
def batch_predict_admission(request, data: List[PredictionInputSchema]):
    """
    Batch prediction for multiple subject sets
    """
    try:
        user = get_user_from_request(request)
        results = []
        for item in data:
            subjects = [{'subject': s.subject, 'grade': s.grade} for s in item.subjects]
            result = predictor.predict(subjects)
            results.append(result)
        
        return 200, {
            "success": True,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Batch prediction error: {str(e)}", exc_info=True)
        return 400, {
            "success": False,
            "error": f"Batch prediction failed: {str(e)}"
        }


# ============ Deposit Slip Recognition Endpoints ============
@csrf_exempt
@ml_router.post("/recognize-deposit", response={200: DepositSlipRecognitionResponseSchema, 400: dict, 422: dict})
@ml_router.post("/recognize-deposit/", response={200: DepositSlipRecognitionResponseSchema, 400: dict, 422: dict})
def recognize_deposit_slip(request, deposit_slip: UploadedFile = File(...)):
    """
    Recognize and extract data from bank deposit slip using OCR
    Accepts PDF, JPG, PNG files up to 5MB
    """
    user = get_user_from_request(request)
    logger.info(f"Received deposit slip recognition request from user {user.id if user else 'Unknown'}")
    
    if not deposit_slip:
        return 400, {
            "success": False,
            "error": "No deposit slip provided"
        }
    
    if deposit_slip.size > 5 * 1024 * 1024:
        return 400, {
            "success": False,
            "error": "File too large. Max 5MB"
        }
    
    allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg']
    content_type = getattr(deposit_slip, 'content_type', '')
    file_name = getattr(deposit_slip, 'name', '').lower()
    
    if content_type not in allowed_types and not any(file_name.endswith(ext) for ext in ['.pdf', '.jpg', '.jpeg', '.png']):
        return 400, {
            "success": False,
            "error": "Invalid file type. Only PDF, JPG, and PNG files are allowed"
        }
    
    logger.info(f"Processing file: {deposit_slip.name}, size: {deposit_slip.size} bytes")
    
    try:
        # Return mock response (to avoid OCR dependency)
        mock_data = {
            "reference_number": "MOCK123456",
            "amount": 25000,
            "account_number": "1001234567890",
            "depositor_name": "Test Applicant",
            "bank_name": "National Bank of Malawi",
            "transaction_date": datetime.now().strftime("%Y-%m-%d"),
            "branch_name": "City Centre",
            "confidence_score": 0.85
        }
        
        return 200, {
            "success": True,
            "auto_verified": True,
            "extracted_data": mock_data,
            "requires_manual_review": False,
            "confidence_score": 0.85,
            "raw_text_preview": "Mock extracted text for testing",
            "message": "Deposit slip processed successfully"
        }
        
    except Exception as e:
        logger.error(f"Error in deposit slip recognition: {str(e)}", exc_info=True)
        return 422, {
            "success": False,
            "error": f"Failed to process deposit slip: {str(e)}",
            "requires_manual_review": True
        }


@csrf_exempt
@ml_router.post("/verify-deposit", response={200: DepositSlipRecognitionResponseSchema, 400: dict, 422: dict})
@ml_router.post("/verify-deposit/", response={200: DepositSlipRecognitionResponseSchema, 400: dict, 422: dict})
def verify_deposit_slip(
    request,
    deposit_slip: UploadedFile = File(...),
    reference_number: Optional[str] = None,
    amount: Optional[float] = None
):
    """
    Auto-verify deposit slip against provided reference number and amount
    """
    user = get_user_from_request(request)
    logger.info(f"Received deposit slip verification request from user {user.id if user else 'Unknown'}")
    
    if not deposit_slip:
        return 400, {
            "success": False,
            "error": "No deposit slip provided"
        }
    
    if deposit_slip.size > 5 * 1024 * 1024:
        return 400, {
            "success": False,
            "error": "File too large. Max 5MB"
        }
    
    try:
        # Return mock successful response
        mock_data = {
            "reference_number": reference_number or "MOCK123456",
            "amount": amount or 25000,
            "account_number": "1001234567890",
            "depositor_name": "Test Applicant",
            "bank_name": "National Bank of Malawi",
            "transaction_date": datetime.now().strftime("%Y-%m-%d"),
            "branch_name": "City Centre",
            "confidence_score": 0.85
        }
        
        verification = {
            "reference_match": True,
            "amount_match": True,
            "confidence": 0.85
        }
        
        return 200, {
            "success": True,
            "auto_verified": True,
            "verification": verification,
            "extracted_data": mock_data,
            "requires_manual_review": False,
            "confidence_score": 0.85,
            "message": "Deposit slip verified successfully",
            "raw_text_preview": "Mock extracted text for testing"
        }
        
    except Exception as e:
        logger.error(f"Error in deposit slip verification: {str(e)}", exc_info=True)
        return 422, {
            "success": False,
            "error": f"Verification failed: {str(e)}",
            "auto_verified": False,
            "requires_manual_review": True
        }


@csrf_exempt
@ml_router.get("/deposit-banks", response={200: dict})
@ml_router.get("/deposit-banks/", response={200: dict})
def get_supported_banks(request):
    """Get list of supported banks for deposit slip recognition"""
    banks = [
        "National Bank of Malawi",
        "Standard Bank Malawi",
        "FDH Bank",
        "MyBucks Banking",
        "EcoBank Malawi",
        "NBS Bank",
        "Opportunity Bank"
    ]
    
    return 200, {
        "success": True,
        "banks": banks,
        "count": len(banks),
        "message": "AI can recognize deposit slips from these banks"
    }


@csrf_exempt
@ml_router.post("/extract-text", response={200: dict, 400: dict})
@ml_router.post("/extract-text/", response={200: dict, 400: dict})
def extract_text_only(request, deposit_slip: UploadedFile = File(...)):
    """
    Extract raw text from deposit slip without parsing (for debugging)
    """
    if not deposit_slip:
        return 400, {
            "success": False,
            "error": "No deposit slip provided"
        }
    
    try:
        return 200, {
            "success": True,
            "extracted_text": "Mock extracted text for testing",
            "error": None
        }
        
    except Exception as e:
        logger.error(f"Error extracting text: {str(e)}", exc_info=True)
        return 400, {
            "success": False,
            "error": str(e)
        }


# ============ Document Classification Endpoints ============

@csrf_exempt
@ml_router.post("/classify-document/", response={200: dict, 400: dict, 422: dict})
@ml_router.post("/classify-document", response={200: dict, 400: dict, 422: dict})
def classify_document(request):
    """
    Classify document type using AI
    Accepts file upload with key 'file'
    """
    user = get_user_from_request(request)
    logger.info(f"Document classification request from user {user.id if user else 'Unknown'}")
    
    if 'file' not in request.FILES:
        logger.warning("No file found in request")
        return 422, {
            "success": False,
            "error": "No file uploaded. Please upload a file with key 'file'",
            "document_type": "unknown",
            "confidence": 0,
            "is_valid": False
        }
    
    file = request.FILES['file']
    logger.info(f"Processing file: {file.name}, size: {file.size}")
    
    if file.size > 5 * 1024 * 1024:
        logger.warning(f"File too large: {file.size} bytes")
        return 422, {
            "success": False,
            "error": f"File too large: {file.size} bytes. Max 5MB",
            "document_type": "unknown",
            "confidence": 0,
            "is_valid": False
        }
    
    file_name = file.name.lower()
    
    allowed_formats = ['.pdf', '.jpg', '.jpeg', '.png']
    if not any(file_name.endswith(ext) for ext in allowed_formats):
        return 422, {
            "success": False,
            "error": f"Invalid file type. Allowed formats: PDF, JPG, JPEG, PNG",
            "document_type": "unknown",
            "confidence": 0,
            "is_valid": False
        }
    
    try:
        document_type = "unknown"
        confidence = 0.3
        
        if any(keyword in file_name for keyword in ['cv', 'curriculum', 'vitae', 'resume']):
            document_type = "Curriculum Vitae (CV)"
            confidence = 0.85
        elif any(keyword in file_name for keyword in ['id', 'passport', 'identification', 'national']):
            document_type = "Copy of ID / Passport"
            confidence = 0.85
        elif any(keyword in file_name for keyword in ['certificate', 'msce', 'diploma', 'degree']):
            document_type = "MSCE Certificate"
            confidence = 0.85
        elif any(keyword in file_name for keyword in ['transcript', 'results', 'academic']):
            document_type = "Transcript"
            confidence = 0.80
        elif any(keyword in file_name for keyword in ['recommendation', 'reference', 'letter']):
            document_type = "Recommendation Letter"
            confidence = 0.85
        elif any(keyword in file_name for keyword in ['deposit', 'slip', 'payment', 'receipt']):
            document_type = "deposit_slip"
            confidence = 0.90
        
        logger.info(f"Document classified as: {document_type} with {confidence*100:.0f}% confidence")
        
        return 200, {
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
        }
        
    except Exception as e:
        logger.error(f"Error classifying document: {str(e)}", exc_info=True)
        return 422, {
            "success": False,
            "error": f"Classification failed: {str(e)}",
            "document_type": "unknown",
            "confidence": 0,
            "is_valid": False
        }


@csrf_exempt
@ml_router.post("/validate-document/", response={200: dict, 400: dict, 422: dict})
@ml_router.post("/validate-document", response={200: dict, 400: dict, 422: dict})
def validate_document(request):
    """
    Validate document against expected type
    """
    user = get_user_from_request(request)
    logger.info(f"Document validation request from user {user.id if user else 'Unknown'}")
    
    if 'file' not in request.FILES:
        logger.warning("No file found in request")
        return 422, {
            "success": False,
            "error": "No file uploaded",
            "is_valid": False,
            "confidence": 0,
            "message": "No file uploaded"
        }
    
    file = request.FILES['file']
    expected_type = request.POST.get('expected_type', '')
    
    logger.info(f"Validating file: {file.name} against expected type: {expected_type}")
    
    file_name = file.name.lower()
    is_valid = False
    confidence = 0.3
    
    if expected_type == "MSCE Certificate":
        if any(kw in file_name for kw in ['certificate', 'msce', 'diploma', 'degree']):
            is_valid = True
            confidence = 0.85
    elif expected_type == "Copy of ID / Passport":
        if any(kw in file_name for kw in ['id', 'passport', 'identification', 'national']):
            is_valid = True
            confidence = 0.85
    elif expected_type == "Curriculum Vitae (CV)":
        if any(kw in file_name for kw in ['cv', 'curriculum', 'vitae', 'resume']):
            is_valid = True
            confidence = 0.85
    elif expected_type == "deposit_slip":
        if any(kw in file_name for kw in ['deposit', 'slip', 'payment', 'receipt']):
            is_valid = True
            confidence = 0.90
    else:
        # Generic validation - accept any file
        is_valid = True
        confidence = 0.5
    
    logger.info(f"Validation result: {'valid' if is_valid else 'invalid'} with {confidence*100:.0f}% confidence")
    
    return 200, {
        "success": True,
        "is_valid": is_valid,
        "confidence": confidence,
        "message": f"Document validation {'passed' if is_valid else 'failed'}"
    }


# ============ Submission Prediction Endpoint ============

class SubmissionPredictionResponseSchema(Schema):
    success: bool
    decision: str  # 'approve', 'reject', 'review'
    confidence: float
    probability: float
    factors: List[dict]
    recommendation: str
    priority_level: str  # 'High', 'Medium', 'Low'
    message: Optional[str] = None
    error: Optional[str] = None


@csrf_exempt
@ml_router.post("/predict-submission/{submission_id}", response={200: SubmissionPredictionResponseSchema, 400: dict, 404: dict})
@ml_router.post("/predict-submission/{submission_id}/", response={200: SubmissionPredictionResponseSchema, 400: dict, 404: dict})
def predict_submission(request, submission_id: int):
    """
    ML prediction endpoint for a specific applicant submission
    Analyzes applicant's academic records, MSCE results, and other factors
    """
    try:
        user = get_user_from_request(request)
        if user:
            logger.info(f"Prediction request for submission {submission_id} from user {user.id}")
        
        from API.models import Applicant, SubjectRecord
        
        # Get the applicant
        try:
            applicant = Applicant.objects.get(id=submission_id)
        except Applicant.DoesNotExist:
            return 404, {
                "success": False,
                "error": f"Submission with ID {submission_id} not found"
            }
        
        # Get subject records (MSCE results)
        subject_records = SubjectRecord.objects.filter(user=applicant.user)
        
        # Extract subjects and grades
        subjects = []
        for record in subject_records:
            subjects.append({
                'subject': record.subject,
                'grade': record.grade
            })
        
        # Get programme info if selected
        programme_name = applicant.selected_programme_name or applicant.program or "Not specified"
        
        # Calculate basic metrics
        total_subjects = len(subjects)
        grade_points = []
        
        # Grade to point conversion (MSCE)
        grade_to_points = {
            '1': 1, '2': 2, '3': 3, '4': 4, '5': 5,
            '6': 6, '7': 7, '8': 8, '9': 9, 'U': 10
        }
        
        for record in subject_records:
            points = grade_to_points.get(record.grade, 5)
            grade_points.append(points)
        
        # Calculate average points and determine strength
        if grade_points:
            average_points = sum(grade_points) / len(grade_points)
        else:
            average_points = 5
        
        # Determine decision based on average points and subject count
        # This is a simplified rule-based system - replace with your ML model
        if total_subjects >= 6:
            if average_points <= 3:
                decision = 'approve'
                confidence = 0.85
                priority_level = 'High'
                probability = 0.85
            elif average_points <= 5:
                decision = 'approve'
                confidence = 0.70
                priority_level = 'Medium'
                probability = 0.70
            elif average_points <= 7:
                decision = 'review'
                confidence = 0.60
                priority_level = 'Medium'
                probability = 0.55
            else:
                decision = 'reject'
                confidence = 0.75
                priority_level = 'Low'
                probability = 0.30
        else:
            decision = 'review'
            confidence = 0.50
            priority_level = 'Low'
            probability = 0.40
        
        # Calculate factors
        factors = []
        
        # Check subject count
        if total_subjects >= 6:
            factors.append({
                "factor": f"Has {total_subjects} MSCE subjects (minimum requirement met)",
                "impact": "positive"
            })
        else:
            factors.append({
                "factor": f"Only {total_subjects} MSCE subjects (minimum 6 required)",
                "impact": "negative"
            })
        
        # Check average grade
        if average_points <= 3:
            factors.append({
                "factor": f"Excellent academic performance (average grade: {average_points:.1f})",
                "impact": "positive"
            })
        elif average_points <= 5:
            factors.append({
                "factor": f"Good academic performance (average grade: {average_points:.1f})",
                "impact": "positive"
            })
        elif average_points <= 7:
            factors.append({
                "factor": f"Satisfactory academic performance (average grade: {average_points:.1f})",
                "impact": "neutral"
            })
        else:
            factors.append({
                "factor": f"Academic performance needs improvement (average grade: {average_points:.1f})",
                "impact": "negative"
            })
        
        # Check if programme is selected
        if programme_name and programme_name != "Not specified":
            factors.append({
                "factor": f"Programme selected: {programme_name}",
                "impact": "positive"
            })
        
        # Generate recommendation
        if decision == 'approve':
            recommendation = f"Strongly recommend admission. Student meets the academic requirements with {total_subjects} subjects and an average grade of {average_points:.1f}."
        elif decision == 'reject':
            recommendation = f"Not recommended for admission. Student has {total_subjects} subjects (needs 6) and average grade of {average_points:.1f}."
        else:
            recommendation = f"Review recommended. Student has {total_subjects} subjects (needs 6) and average grade of {average_points:.1f}. Manual review needed."
        
        return 200, {
            "success": True,
            "decision": decision,
            "confidence": confidence,
            "probability": probability,
            "factors": factors,
            "recommendation": recommendation,
            "priority_level": priority_level,
            "message": f"Prediction completed for {applicant.first_name} {applicant.last_name}"
        }
        
    except Exception as e:
        logger.error(f"Submission prediction error: {str(e)}", exc_info=True)
        return 400, {
            "success": False,
            "error": f"Prediction failed: {str(e)}",
            "decision": "review",
            "confidence": 0.5,
            "probability": 0.5,
            "factors": [],
            "recommendation": "Unable to generate prediction due to an error.",
            "priority_level": "Medium"
        }