# API/ml/service.py
"""
Machine Learning service for admission prediction
Separate from main API to keep concerns separated
"""

import os
import joblib
import numpy as np
from typing import Tuple, Optional, List, Dict

# Grade to points mapping
GRADE_MAP = {
    '1': 1, '2': 2, '3': 3,
    '4': 5, '5': 5,
    '6': 7, '7': 7,
    '8': 8, '9': 8,
    'U': 9
}

class AdmissionPredictor:
    """Handles admission prediction using ML model"""
    
    def __init__(self):
        self.model = None
        self.model_loaded = False
        self._load_model()
    
    def _load_model(self):
        """Load the ML model from disk if it exists"""
        try:
            # Look for the model in the ml directory
            model_path = os.path.join(os.path.dirname(__file__), 'admission_model.pkl')
            if os.path.exists(model_path):
                self.model = joblib.load(model_path)
                self.model_loaded = True
                print(f"✅ ML model loaded from {model_path}")
            else:
                print(f"⚠️ ML model not found at {model_path}, using rule-based prediction")
        except Exception as e:
            print(f"❌ Error loading ML model: {e}")
            self.model_loaded = False
    
    def calculate_average_points(self, subjects: List[Dict]) -> float:
        """Calculate average points from subjects"""
        if not subjects:
            return 0.0
        
        total_points = 0
        for subject in subjects:
            grade = str(subject.get('grade', 'U'))
            points = GRADE_MAP.get(grade, 9)
            total_points += points
        
        return total_points / len(subjects)
    
    def predict_with_ml(self, avg_points: float) -> Tuple[int, float]:
        """Predict using ML model if available"""
        if self.model_loaded and self.model:
            try:
                # Reshape for single prediction
                features = np.array([[avg_points]])
                prediction = self.model.predict(features)[0]
                
                # Get probability if model supports it
                probability = 0.5
                if hasattr(self.model, 'predict_proba'):
                    proba = self.model.predict_proba(features)[0]
                    probability = float(proba[1]) if len(proba) > 1 else float(proba[0])
                
                return int(prediction), probability
            except Exception as e:
                print(f"❌ ML prediction error: {e}")
        
        # Fallback to rule-based
        return self.predict_rule_based(avg_points)
    
    def predict_rule_based(self, avg_points: float) -> Tuple[int, float]:
        """Rule-based prediction fallback"""
        if avg_points <= 3:
            return 1, 0.9
        elif avg_points <= 5:
            return 1, 0.7
        elif avg_points <= 7:
            return 0, 0.5
        else:
            return 0, 0.2
    
    def get_prediction_message(self, prediction: int, probability: float) -> str:
        """Get user-friendly message based on prediction"""
        if prediction == 1:
            if probability >= 0.8:
                return "Highly Likely Admitted"
            elif probability >= 0.6:
                return "Likely Admitted"
            else:
                return "Good Chance of Admission"
        else:
            if probability <= 0.3:
                return "Low Chance of Admission"
            elif probability <= 0.5:
                return "Possible - Needs Review"
            else:
                return "Application Under Review"
    
    def predict(self, subjects: List[Dict]) -> Dict:
        """
        Main prediction method
        Returns: dict with prediction results
        """
        if not subjects:
            return {
                'success': False,
                'error': 'No subjects provided'
            }
        
        # Calculate average points
        avg_points = self.calculate_average_points(subjects)
        
        # Get prediction
        prediction, probability = self.predict_with_ml(avg_points)
        
        # Get message
        message = self.get_prediction_message(prediction, probability)
        
        return {
            'success': True,
            'average_points': round(avg_points, 2),
            'prediction': prediction,
            'probability': probability,
            'message': message,
            'using_ml': self.model_loaded
        }


# Create a singleton instance
predictor = AdmissionPredictor()