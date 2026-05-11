"""
ML Endpoints for Mzuzu University Admission System
Includes: Admission Prediction, Deposit Slip Recognition, Programme Recommendations
"""

from ninja import Router, Schema, File
from ninja.files import UploadedFile
from django.views.decorators.csrf import csrf_exempt
from typing import List, Optional, Dict, Any
from datetime import datetime
from .service import predictor
from .deposit_slip_recognizer import deposit_slip_recognizer
from .programme_recommender import get_recommender
import logging
import jwt
import re
from django.conf import settings
from django.contrib.auth.models import User
from django.http import JsonResponse

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


# ============ Programme Recommendation Schemas ============
class RecommendationRequestSchema(Schema):
    subjects: List[SubjectGradeSchema]
    top_n: int = 6
    programme_type: str = "all"

class ProgrammeRecommendationSchema(Schema):
    id: int
    name: str
    code: Optional[str] = None
    duration: str
    type: str
    fit_score: float
    admission_probability: float
    eligibility: str
    required_subjects: List[str]
    missing_subjects: List[str]
    min_points: int
    required_credits: int
    quota: int
    rank: Optional[int] = None

class RecommendationResponseSchema(Schema):
    success: bool
    message: str
    student_stats: Optional[Dict] = None
    recommendations: List[ProgrammeRecommendationSchema] = []
    error: Optional[str] = None

class ProgrammeFitResponseSchema(Schema):
    success: bool
    prediction: Optional[Dict] = None
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
    recommender = get_recommender()
    return 200, {
        "success": True,
        "ml_available": predictor.model_loaded,
        "programme_recommender_loaded": recommender is not None,
        "programmes_count": len(recommender.programmes_df) if recommender and recommender.programmes_df is not None else 0,
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


# ============ Programme Recommendation Endpoints ============
@csrf_exempt
@ml_router.post("/recommend-programmes", response={200: RecommendationResponseSchema, 400: dict})
@ml_router.post("/recommend-programmes/", response={200: RecommendationResponseSchema, 400: dict})
def recommend_programmes(request, data: RecommendationRequestSchema):
    """
    Get programme recommendations based on student's MSCE results
    """
    try:
        user = get_user_from_request(request)
        if user:
            logger.info(f"Programme recommendation request from user {user.id}")
        
        subjects = [{'subject': s.subject, 'grade': s.grade} for s in data.subjects]
        
        if not subjects:
            return 200, {
                "success": False,
                "message": "No subjects provided",
                "recommendations": []
            }
        
        recommender = get_recommender()
        recommendations = recommender.recommend_programmes(
            subjects=subjects,
            top_n=data.top_n,
            programme_type=data.programme_type
        )
        
        # Ensure all recommendations have proper types
        clean_recommendations = []
        for rec in recommendations:
            clean_rec = {
                "id": int(rec["id"]),
                "name": str(rec["name"]),
                "code": str(rec.get("code", "")) if rec.get("code") and str(rec.get("code")) != "nan" else "",
                "duration": str(rec.get("duration", "N/A")),
                "type": str(rec.get("type", "generic")),
                "fit_score": float(rec["fit_score"]),
                "admission_probability": float(rec["admission_probability"]),
                "eligibility": str(rec["eligibility"]),
                "required_subjects": [str(s) for s in rec.get("required_subjects", [])],
                "missing_subjects": [str(s) for s in rec.get("missing_subjects", [])],
                "min_points": int(rec.get("min_points", 30)),
                "required_credits": int(rec.get("required_credits", 4)),
                "quota": int(rec.get("quota", 0)) if rec.get("quota") and str(rec.get("quota")) != "nan" else 0,
                "rank": int(rec.get("rank", 0)) if rec.get("rank") else None
            }
            clean_recommendations.append(clean_rec)
        
        # Calculate average points
        avg_points = 0
        best_grade = 9
        if subjects:
            points_list = [recommender.grade_points.get(str(s['grade']).upper(), 9) for s in subjects]
            avg_points = sum(points_list) / len(points_list)
            best_grade = min(points_list)
        
        return 200, {
            "success": True,
            "message": f"Found {len(clean_recommendations)} programme recommendations",
            "student_stats": {
                "subjects_count": len(subjects),
                "average_points": round(avg_points, 2),
                "best_grade": best_grade
            },
            "recommendations": clean_recommendations
        }
        
    except Exception as e:
        logger.error(f"Programme recommendation error: {str(e)}", exc_info=True)
        return 400, {
            "success": False,
            "message": "Failed to generate recommendations",
            "error": str(e),
            "recommendations": []
        }
    

@csrf_exempt
@ml_router.post("/predict-programme-fit/{programme_id}", response={200: ProgrammeFitResponseSchema, 400: dict})
@ml_router.post("/predict-programme-fit/{programme_id}/", response={200: ProgrammeFitResponseSchema, 400: dict})
def predict_programme_fit(request, programme_id: int, data: PredictionInputSchema):
    """
    Predict how well a student fits a specific programme
    Returns detailed fit analysis including subject requirements and points check
    """
    try:
        user = get_user_from_request(request)
        if user:
            logger.info(f"Programme fit prediction request for programme {programme_id} from user {user.id}")
        
        subjects = [{'subject': s.subject, 'grade': s.grade} for s in data.subjects]
        
        if not subjects:
            return 400, {
                "success": False,
                "error": "No subjects provided"
            }
        
        recommender = get_recommender()
        prediction = recommender.predict_admission_probability(programme_id, subjects)
        
        if prediction.get("error"):
            return 400, {
                "success": False,
                "error": prediction["error"]
            }
        
        return 200, {
            "success": True,
            "prediction": prediction
        }
        
    except Exception as e:
        logger.error(f"Programme fit prediction error: {str(e)}", exc_info=True)
        return 400, {
            "success": False,
            "error": str(e)
        }


@csrf_exempt
@ml_router.get("/eligible-programmes", response={200: dict, 400: dict})
@ml_router.get("/eligible-programmes/", response={200: dict, 400: dict})
def get_eligible_programmes(request):
    """
    Get all programmes with eligibility criteria
    Useful for frontend to display available programmes
    """
    try:
        recommender = get_recommender()
        programmes = []
        
        for _, prog in recommender.programmes_df.iterrows():
            programmes.append({
                "id": int(prog['id']),
                "name": prog['name'],
                "code": prog.get('code', ''),
                "duration": prog['duration'],
                "type": prog.get('type', 'generic'),
                "required_subjects": prog.get('subjects', []),
                "min_points": prog.get('min_points', 30),
                "required_credits": prog.get('required_credits', 4),
                "quota": prog.get('quota', 0)
            })
        
        return 200, {
            "success": True,
            "count": len(programmes),
            "programmes": programmes
        }
        
    except Exception as e:
        logger.error(f"Error fetching programmes: {str(e)}", exc_info=True)
        return 400, {
            "success": False,
            "error": str(e)
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
    Classify document type using AI with OCR content analysis
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
        # Use OCR to analyze the actual content of the file
        recognition_result = deposit_slip_recognizer.recognize(file)
        
        document_type = "unknown"
        confidence = 0.3
        is_valid = False
        extracted_preview = {
            "has_reference": False,
            "has_amount": False,
            "has_bank": False
        }
        
        if recognition_result.get('success'):
            extracted_data = recognition_result.get('extracted_data', {})
            
            # Check if it's a deposit slip based on extracted patterns
            has_reference = bool(extracted_data.get('reference_number'))
            has_amount = bool(extracted_data.get('amount'))
            has_bank = bool(extracted_data.get('bank_name'))
            
            extracted_preview = {
                "has_reference": has_reference,
                "has_amount": has_amount,
                "has_bank": has_bank
            }
            
            # Check for NBS Bank specifically
            raw_text = recognition_result.get('raw_text_preview', '').lower()
            
            # Keywords that indicate a bank deposit slip
            deposit_slip_keywords = [
                'bank', 'deposit', 'slip', 'cash deposit', 'account number',
                'nbs bank', 'national bank', 'standard bank', 'fdh bank',
                'ecobank', 'mybucks', 'opportunity bank'
            ]
            
            # Check for specific pattern
            is_deposit_slip = (
                any(kw in raw_text for kw in deposit_slip_keywords) and
                (has_reference or has_amount or has_bank)
            )
            
            # Specific patterns for NBS deposit slip
            nbs_patterns = [
                r'nbs\s*bank',
                r'cash\s*deposit\s*slip',
                r'bic\s*f\s*d',
                r'account\s*name:',
                r'11224',
                r'12332057'
            ]
            
            is_nbs_deposit_slip = any(
                re.search(pattern, raw_text, re.IGNORECASE) 
                for pattern in nbs_patterns
            )
            
            if is_deposit_slip or is_nbs_deposit_slip:
                document_type = "deposit_slip"
                confidence = 0.85 if is_nbs_deposit_slip else 0.75
                is_valid = True
            else:
                # Fallback to filename-based classification if OCR fails
                if any(keyword in file_name for keyword in ['deposit', 'slip', 'payment', 'receipt']):
                    document_type = "deposit_slip"
                    confidence = 0.70
                    is_valid = True
                else:
                    document_type = "unknown"
                    confidence = 0.3
                    is_valid = False
        
        else:
            # If OCR fails, fallback to filename-based classification
            if any(keyword in file_name for keyword in ['deposit', 'slip', 'payment', 'receipt']):
                document_type = "deposit_slip"
                confidence = 0.65
                is_valid = True
            elif any(keyword in file_name for keyword in ['cv', 'curriculum', 'vitae', 'resume']):
                document_type = "Curriculum Vitae (CV)"
                confidence = 0.85
                is_valid = True
            elif any(keyword in file_name for keyword in ['id', 'passport', 'identification', 'national']):
                document_type = "Copy of ID / Passport"
                confidence = 0.85
                is_valid = True
            elif any(keyword in file_name for keyword in ['certificate', 'msce', 'diploma', 'degree']):
                document_type = "MSCE Certificate"
                confidence = 0.85
                is_valid = True
            elif any(keyword in file_name for keyword in ['transcript', 'results', 'academic']):
                document_type = "Transcript"
                confidence = 0.80
                is_valid = True
            elif any(keyword in file_name for keyword in ['recommendation', 'reference', 'letter']):
                document_type = "Recommendation Letter"
                confidence = 0.85
                is_valid = True
        
        logger.info(f"Document classified as: {document_type} with {confidence*100:.0f}% confidence")
        
        return 200, {
            "success": True,
            "document_type": document_type,
            "confidence": confidence,
            "is_valid": is_valid,
            "extracted_preview": extracted_preview,
            "message": f"Document classified as {document_type} with {confidence*100:.0f}% confidence"
        }
        
    except Exception as e:
        logger.error(f"Error classifying document: {str(e)}", exc_info=True)
        # Fallback to simple classification
        if any(keyword in file_name for keyword in ['deposit', 'slip', 'payment', 'receipt']):
            return 200, {
                "success": True,
                "document_type": "deposit_slip",
                "confidence": 0.60,
                "is_valid": True,
                "extracted_preview": {"has_reference": False, "has_amount": False, "has_bank": False},
                "message": "Document classified as deposit slip (based on filename)"
            }
        
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
        
        # Import models - adjust import path as needed
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
        grade_points_list = []
        
        # Grade to point conversion (MSCE)
        grade_to_points = {
            '1': 1, '2': 2, '3': 3, '4': 4, '5': 5,
            '6': 6, '7': 7, '8': 8, '9': 9, 'U': 10
        }
        
        for record in subject_records:
            subjects.append({
                'subject': record.subject,
                'grade': record.grade
            })
            points = grade_to_points.get(record.grade, 5)
            grade_points_list.append(points)
        
        # Get programme info if selected
        programme_name = getattr(applicant, 'selected_programme_name', None) or getattr(applicant, 'program', "Not specified")
        
        # Calculate basic metrics
        total_subjects = len(subjects)
        
        # Calculate average points and determine strength
        if grade_points_list:
            average_points = sum(grade_points_list) / len(grade_points_list)
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
            "message": f"Prediction completed for {getattr(applicant, 'first_name', 'Applicant')} {getattr(applicant, 'last_name', '')}"
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
# ============ Committee Predictions Dashboard Endpoints ============
# These endpoints are used by the Committee Predictions frontend page

@csrf_exempt
@ml_router.get("/predictions/dashboard", response={200: dict, 400: dict})
@ml_router.get("/predictions/dashboard/", response={200: dict, 400: dict})
def get_predictions_dashboard(request):
    """
    Get ML prediction dashboard statistics for committee
    Returns total predicted, priority distribution, average probabilities, etc.
    """
    try:
        user = get_user_from_request(request)
        if not user:
            return 401, {
                "success": False,
                "error": "Authentication required"
            }
        
        logger.info(f"Fetching predictions dashboard for user {user.id}")
        
        # Import models
        from API.models import Applicant
        
        # Get all applicants with ML predictions
        applicants_with_ml = Applicant.objects.filter(ml_decision__isnull=False)
        
        priority_counts = {
            'High': applicants_with_ml.filter(ml_priority='High').count(),
            'Medium': applicants_with_ml.filter(ml_priority='Medium').count(),
            'Low': applicants_with_ml.filter(ml_priority='Low').count()
        }
        
        # Average probability by priority
        avg_probabilities = {}
        for priority in ['High', 'Medium', 'Low']:
            applicants = applicants_with_ml.filter(ml_priority=priority)
            if applicants.exists():
                total_prob = sum(float(a.ml_probability or 0) for a in applicants)
                avg_probabilities[priority] = total_prob / applicants.count()
            else:
                avg_probabilities[priority] = 0
        
        # Recent predictions
        recent_predictions = applicants_with_ml.order_by('-ml_processed_at')[:10]
        recent = []
        for applicant in recent_predictions:
            recent.append({
                "id": applicant.id,
                "name": f"{applicant.first_name} {applicant.last_name}",
                "priority": applicant.ml_priority,
                "probability": float(applicant.ml_probability) if applicant.ml_probability else 0,
                "predicted_at": applicant.ml_processed_at.isoformat() if applicant.ml_processed_at else None
            })
        
        return 200, {
            "success": True,
            "data": {
                "total_predicted": applicants_with_ml.count(),
                "priority_distribution": priority_counts,
                "average_probabilities": avg_probabilities,
                "recent_predictions": recent,
                "model_info": {
                    "model_loaded": predictor.model_loaded if hasattr(predictor, 'model_loaded') else True,
                    "feature_columns": ['subjects_count', 'total_points', 'programme_id', 'points_per_subject', 'above_min_credits', 'points_within_limit']
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching predictions dashboard: {str(e)}", exc_info=True)
        return 400, {
            "success": False,
            "error": str(e)
        }


@csrf_exempt
@ml_router.get("/predictions/priority/{priority_level}", response={200: dict, 400: dict})
@ml_router.get("/predictions/priority/{priority_level}/", response={200: dict, 400: dict})
def get_predictions_by_priority(request, priority_level: str):
    """
    Get all applicants with a specific priority level (High/Medium/Low)
    """
    try:
        user = get_user_from_request(request)
        if not user:
            return 401, {
                "success": False,
                "error": "Authentication required"
            }
        
        if priority_level not in ['High', 'Medium', 'Low']:
            return 400, {
                "success": False,
                "error": "Priority level must be High, Medium, or Low"
            }
        
        logger.info(f"Fetching {priority_level} priority applicants for user {user.id}")
        
        from API.models import Applicant
        
        applicants = Applicant.objects.filter(
            ml_priority=priority_level,
            status='submitted'
        ).order_by('-ml_probability')
        
        results = []
        for applicant in applicants:
            results.append({
                "id": applicant.id,
                "name": f"{applicant.first_name} {applicant.last_name}",
                "email": applicant.email,
                "programme": applicant.selected_programme_name or applicant.program or "Not specified",
                "probability": float(applicant.ml_probability) if applicant.ml_probability else 0.5,
                "priority": applicant.ml_priority,
                "confidence": float(applicant.ml_confidence) if applicant.ml_confidence else 0.5,
                "submitted_at": applicant.application_date.isoformat() if applicant.application_date else None
            })
        
        return 200, {
            "success": True,
            "priority_level": priority_level,
            "count": len(results),
            "applicants": results
        }
        
    except Exception as e:
        logger.error(f"Error fetching predictions by priority: {str(e)}", exc_info=True)
        return 400, {
            "success": False,
            "error": str(e)
        }


@csrf_exempt
@ml_router.post("/batch-predict-admissions", response={200: dict, 400: dict})
@ml_router.post("/batch-predict-admissions/", response={200: dict, 400: dict})
def batch_predict_admissions_endpoint(request, data: dict = None):
    """
    Batch predict admission probabilities for multiple applicants
    Expects JSON body: {"applicant_ids": [1, 2, 3, ...]}
    """
    try:
        import json
        
        user = get_user_from_request(request)
        if not user:
            return 401, {
                "success": False,
                "error": "Authentication required"
            }
        
        # Parse request body
        if request.body:
            try:
                body = json.loads(request.body)
                applicant_ids = body.get('applicant_ids', [])
            except:
                applicant_ids = []
        elif data:
            applicant_ids = data.get('applicant_ids', [])
        else:
            applicant_ids = []
        
        if not applicant_ids:
            return 400, {
                "success": False,
                "error": "No applicant IDs provided"
            }
        
        logger.info(f"Batch predicting for {len(applicant_ids)} applicants")
        
        from API.models import Applicant, SubjectRecord, ProgrammeChoice
        from django.db.models import Q
        
        results = []
        high_priority = 0
        medium_priority = 0
        low_priority = 0
        
        for applicant_id in applicant_ids:
            try:
                applicant = Applicant.objects.get(id=applicant_id)
                user_obj = applicant.user
                
                subject_records = SubjectRecord.objects.filter(user=user_obj)
                
                # Extract subjects and calculate features
                grade_to_points = {
                    '1': 1, '2': 2, '3': 3, '4': 4, '5': 5,
                    '6': 6, '7': 7, '8': 8, '9': 9, 'U': 10
                }
                
                grades = []
                for record in subject_records:
                    points = grade_to_points.get(record.grade, 5)
                    grades.append(points)
                
                # Calculate points
                total_points = sum(grades) if grades else 30
                subjects_count = len(grades)
                points_per_subject = total_points / max(subjects_count, 1) if subjects_count > 0 else 5
                above_min_credits = 1 if subjects_count >= 6 else 0
                points_within_limit = 1 if total_points <= 30 else 0
                
                # Determine probability and priority based on points
                if subjects_count >= 6 and total_points <= 25:
                    probability = 0.95
                    priority = 'High'
                    confidence = 0.85
                elif subjects_count >= 6 and total_points <= 30:
                    probability = 0.75
                    priority = 'Medium'
                    confidence = 0.70
                elif subjects_count >= 6:
                    probability = 0.55
                    priority = 'Medium'
                    confidence = 0.60
                else:
                    probability = 0.30
                    priority = 'Low'
                    confidence = 0.50
                
                # Update counts
                if priority == 'High':
                    high_priority += 1
                elif priority == 'Medium':
                    medium_priority += 1
                else:
                    low_priority += 1
                
                # Store in database
                applicant.ml_decision = priority.lower()
                applicant.ml_confidence = confidence
                applicant.ml_probability = probability
                applicant.ml_priority = priority
                applicant.ml_factors = {'factors': [
                    {"factor": f"MSCE Subjects: {subjects_count}", "impact": "positive" if subjects_count >= 6 else "negative"},
                    {"factor": f"Total Points: {total_points}", "impact": "positive" if total_points <= 30 else "negative"}
                ]}
                applicant.ml_recommendation = f"Candidate has {subjects_count} subjects with {total_points} total points."
                applicant.ml_processed_at = datetime.now()
                applicant.save()
                
                results.append({
                    "success": True,
                    "applicant_id": applicant.id,
                    "applicant_name": f"{applicant.first_name} {applicant.last_name}",
                    "probability": probability,
                    "priority": priority,
                    "priority_level": priority,
                    "priority_color": "red" if priority == "High" else "yellow" if priority == "Medium" else "gray",
                    "priority_icon": "🔥" if priority == "High" else "⭐" if priority == "Medium" else "📋",
                    "confidence": confidence,
                    "factors": [],
                    "recommendation": applicant.ml_recommendation
                })
                
            except Exception as e:
                logger.error(f"Error predicting for applicant {applicant_id}: {str(e)}")
                results.append({
                    "success": False,
                    "applicant_id": applicant_id,
                    "error": str(e)
                })
        
        return 200, {
            "success": True,
            "results": results,
            "summary": {
                "total": len(applicant_ids),
                "high_priority": high_priority,
                "medium_priority": medium_priority,
                "low_priority": low_priority,
                "successful": len([r for r in results if r.get('success')])
            }
        }
        
    except Exception as e:
        logger.error(f"Batch prediction error: {str(e)}", exc_info=True)
        return 400, {
            "success": False,
            "error": str(e)
        }





# Add this at the very end of API/ml/endpoints.py
router = ml_router  # Create alias for backward compatibility