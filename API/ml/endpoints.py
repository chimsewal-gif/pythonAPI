# API/ml/endpoints.py
"""
Separate ML endpoints for admission prediction
"""

from ninja import Router, Schema
from typing import List, Optional
from .service import predictor

# Create a separate router for ML endpoints
ml_router = Router()

# Schemas for ML endpoints
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


@ml_router.post("/predict", response={200: PredictionResponseSchema, 400: dict})
@ml_router.post("/predict/", response={200: PredictionResponseSchema, 400: dict})
def predict_admission(request, data: PredictionInputSchema):
    """
    ML prediction endpoint for admission chances based on MSCE results
    """
    try:
        # Convert subjects to dict format
        subjects = [{'subject': s.subject, 'grade': s.grade} for s in data.subjects]
        
        # Get prediction from ML service
        result = predictor.predict(subjects)
        
        if result.get('success'):
            return {
                "success": True,
                "average_points": result['average_points'],
                "prediction": result['prediction'],
                "probability": result['probability'],
                "message": result['message'],
                "using_ml": result.get('using_ml', False)
            }
        else:
            return {
                "success": False,
                "error": result.get('error', 'Prediction failed')
            }, 400
            
    except Exception as e:
        print(f"Prediction endpoint error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": f"Prediction failed: {str(e)}"
        }, 400


@ml_router.get("/health", response={200: dict})
@ml_router.get("/health/", response={200: dict})
def ml_health_check(request):
    """Check if ML service is available"""
    return {
        "success": True,
        "ml_available": predictor.model_loaded,
        "message": "ML service is running" if predictor.model_loaded else "ML service running in fallback mode"
    }


@ml_router.post("/batch-predict", response={200: dict, 400: dict})
@ml_router.post("/batch-predict/", response={200: dict, 400: dict})
def batch_predict_admission(request, data: List[PredictionInputSchema]):
    """
    Batch prediction for multiple subject sets
    """
    try:
        results = []
        for item in data:
            subjects = [{'subject': s.subject, 'grade': s.grade} for s in item.subjects]
            result = predictor.predict(subjects)
            results.append(result)
        
        return {
            "success": True,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        print(f"Batch prediction error: {str(e)}")
        return {
            "success": False,
            "error": f"Batch prediction failed: {str(e)}"
        }, 400