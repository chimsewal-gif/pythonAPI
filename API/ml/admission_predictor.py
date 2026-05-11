"""
Machine Learning Model for Admission Prediction and Prioritisation
Predicts applicant success probability and assigns priority levels
"""

import pandas as pd
import numpy as np
import joblib
import pickle
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
from datetime import datetime
import logging
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

class AdmissionPredictor:
    """
    ML model for predicting applicant success and assigning priority levels
    """
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.feature_columns = [
            'subjects_count',           # Number of MSCE subjects
            'total_points',             # Total MSCE points
            'programme_id',             # Programme identifier
            'points_per_subject',       # Average points per subject
            'above_min_credits',        # Whether applicant has above minimum credits
            'points_within_limit'       # Whether points are within acceptable range
        ]
        self.priority_thresholds = {
            'High': 0.7,
            'Medium': 0.4,
            'Low': 0.0
        }
        
        # Paths for the trained model from train_model.py
        self.base_dir = Path(__file__).parent
        self.models_dir = self.base_dir / 'models'
        self.model_path = self.models_dir / 'admission_model.pkl'
        self.scaler_path = self.models_dir / 'admission_scaler.pkl'
        self.features_path = self.models_dir / 'admission_features.pkl'
        self.model_info_path = self.models_dir / 'admission_model_info.json'
        
        # Create models directory if it doesn't exist
        self.models_dir.mkdir(exist_ok=True)
        
        # Try to load the trained model
        self.load_model()
    
    def calculate_msce_points(self, grade: str) -> int:
        """
        Convert MSCE grade to points (lower is better)
        Standard MSCE grading: 1 = Distinction, 2 = Credit, 3 = Pass, etc.
        """
        grade_map = {
            '1': 1, 'A*': 1, 'A': 1, 'A+': 1,
            '2': 2, 'B': 2, 'B+': 2,
            '3': 3, 'C': 3, 'C+': 3,
            '4': 4, 'D': 4, 'D+': 4,
            '5': 5, 'E': 5, 'E+': 5,
            '6': 6, 'F': 6, 'U': 6,
            'P': 7, 'S': 7, 'X': 9, 'Y': 9
        }
        grade_str = str(grade).upper().strip()
        return grade_map.get(grade_str, 5)
    
    def is_credit_or_better(self, grade: str) -> bool:
        """Check if grade is a credit (grade 1 or 2) or better"""
        points = self.calculate_msce_points(grade)
        return points <= 2
    
    def calculate_total_points(self, grades: List[str]) -> int:
        """Calculate total points from a list of grades"""
        return sum(self.calculate_msce_points(g) for g in grades)
    
    def extract_features(self, applicant_data: Dict) -> tuple:
        """
        Extract features from applicant data for prediction
        Returns: (feature_vector, features_dict)
        """
        # Get MSCE results
        subject_records = applicant_data.get('subject_records', [])
        
        # Filter for MSCE subjects
        msce_subjects = []
        for s in subject_records:
            qual = s.get('qualification', '').lower()
            if 'msce' in qual or 'malawi' in qual or 'certificate' in qual:
                msce_subjects.append(s)
        
        # If no MSCE subjects found, try to use all subjects
        if not msce_subjects:
            msce_subjects = subject_records
        
        # Extract grades
        grades = []
        subjects_count = len(msce_subjects)
        has_credit_english = False
        has_credit_math = False
        has_credit_science = False
        
        for subject in msce_subjects:
            grade = subject.get('grade', '')
            if grade:
                grades.append(grade)
            
            subject_name = subject.get('subject', '').lower()
            if 'english' in subject_name:
                has_credit_english = self.is_credit_or_better(grade)
            elif 'math' in subject_name or 'mathematics' in subject_name:
                has_credit_math = self.is_credit_or_better(grade)
            elif any(sci in subject_name for sci in ['biology', 'chemistry', 'physics', 'science']):
                has_credit_science = self.is_credit_or_better(grade)
        
        # Calculate metrics
        total_points = self.calculate_total_points(grades) if grades else 30
        num_subjects = len(grades)
        points_per_subject = total_points / max(num_subjects, 1)
        
        # Determine if above minimum credits (typically min 6 subjects with credits)
        above_min_credits = 1 if num_subjects >= 6 and points_per_subject <= 2.5 else 0
        
        # Points within limit (typically total points <= 25 for competitive programmes)
        points_within_limit = 1 if total_points <= 25 else 0
        
        # Programme ID (encode programme name to ID)
        programme_name = applicant_data.get('programme_name', applicant_data.get('selected_programme', ''))
        programme_id = self._encode_programme(programme_name)
        
        # Feature vector
        features = {
            'subjects_count': num_subjects,
            'total_points': total_points,
            'programme_id': programme_id,
            'points_per_subject': points_per_subject,
            'above_min_credits': above_min_credits,
            'points_within_limit': points_within_limit
        }
        
        # Additional features for factor generation
        extended_features = {
            **features,
            'has_credit_english': has_credit_english,
            'has_credit_math': has_credit_math,
            'has_credit_science': has_credit_science,
            'application_completeness': self.calculate_completeness_score(applicant_data),
            'msce_year': applicant_data.get('msce_year', datetime.now().year),
            'programme_applicants_count': applicant_data.get('programme_applicants_count', 1),
            'programme_capacity': applicant_data.get('programme_capacity', 50),
            'documents_uploaded': applicant_data.get('documents_uploaded', False),
            'fee_paid': applicant_data.get('fee_paid', False)
        }
        
        # Create feature vector in correct order
        feature_vector = np.array([[features[col] for col in self.feature_columns]])
        
        return feature_vector, extended_features
    
    def _encode_programme(self, programme_name: str) -> int:
        """Encode programme name to ID (simplified)"""
        # This is a simplified mapping - in production, use actual programme IDs
        programme_map = {
            'bachelor of education': 1,
            'bachelor of science': 2,
            'bachelor of arts': 3,
            'bachelor of commerce': 4,
            'bachelor of law': 5,
            'master of education': 6,
            'master of science': 7,
            'phd': 8,
            'diploma': 9,
            'certificate': 10
        }
        
        prog_lower = programme_name.lower()
        for key, value in programme_map.items():
            if key in prog_lower:
                return value
        return 1  # Default to first programme
    
    def calculate_completeness_score(self, applicant_data: Dict) -> float:
        """Calculate application completeness score (0-1)"""
        score = 0
        total = 6
        
        # Personal details
        if applicant_data.get('personal_details_complete', False):
            score += 1
        
        # Next of kin
        if applicant_data.get('next_of_kin_count', 0) > 0:
            score += 1
        
        # Academic records
        if applicant_data.get('subject_records_count', 0) >= 6:
            score += 1
        
        # Programme choices
        if applicant_data.get('programme_choices_count', 0) >= 6:
            score += 1
        
        # Documents uploaded
        if applicant_data.get('documents_uploaded', False):
            score += 1
        
        # Fee payment
        if applicant_data.get('fee_paid', False):
            score += 1
        
        return score / total
    
    def predict(self, applicant_data: Dict) -> Dict:
        """
        Predict admission probability and assign priority level
        
        Returns:
            Dict with probability, priority, confidence, and factors
        """
        try:
            # Extract features
            feature_vector, features = self.extract_features(applicant_data)
            
            # Scale features if scaler is available
            if self.scaler is not None:
                feature_vector_scaled = self.scaler.transform(feature_vector)
            else:
                feature_vector_scaled = feature_vector
            
            # Get prediction probability
            if self.model is not None:
                try:
                    probability = float(self.model.predict_proba(feature_vector_scaled)[0][1])
                    confidence = float(max(self.model.predict_proba(feature_vector_scaled)[0]))
                except Exception as e:
                    logger.warning(f"Model prediction failed: {e}, using rule-based")
                    probability = self._rule_based_prediction(features)
                    confidence = 0.6
            else:
                # Fallback: rule-based prediction
                probability = self._rule_based_prediction(features)
                confidence = 0.7
            
            # Determine priority level
            if probability >= self.priority_thresholds['High']:
                priority = 'High'
                priority_color = 'red'
                priority_icon = '🔥'
            elif probability >= self.priority_thresholds['Medium']:
                priority = 'Medium'
                priority_color = 'yellow'
                priority_icon = '⭐'
            else:
                priority = 'Low'
                priority_color = 'gray'
                priority_icon = '📋'
            
            # Generate factors affecting prediction
            factors = self._generate_factors(features, probability)
            
            # Generate recommendation
            recommendation = self._generate_recommendation(probability, features)
            
            # Calculate confidence based on data completeness
            if features['application_completeness'] < 0.5:
                confidence *= 0.7
            
            return {
                'success': True,
                'probability': probability,
                'priority': priority,
                'priority_level': priority,
                'priority_color': priority_color,
                'priority_icon': priority_icon,
                'confidence': confidence,
                'factors': factors,
                'recommendation': recommendation,
                'features_used': features,
                'using_ml': self.model is not None,
                'message': f"Prediction complete. Priority: {priority} (Confidence: {confidence:.1%})"
            }
            
        except Exception as e:
            logger.error(f"Prediction error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'probability': 0.5,
                'priority': 'Medium',
                'priority_level': 'Medium',
                'confidence': 0.5,
                'factors': [],
                'recommendation': 'Unable to generate prediction due to insufficient data',
                'using_ml': False
            }
    
    def _rule_based_prediction(self, features: Dict) -> float:
        """Fallback rule-based prediction when ML model is not available"""
        score = 0.5
        
        # Total points impact (best is <=24, worst is >35)
        total_points = features.get('total_points', 30)
        if total_points <= 24:
            score += 0.3
        elif total_points <= 28:
            score += 0.2
        elif total_points <= 32:
            score += 0.1
        elif total_points >= 36:
            score -= 0.2
        elif total_points >= 40:
            score -= 0.3
        
        # Subjects count impact
        subjects_count = features.get('subjects_count', 0)
        if subjects_count >= 8:
            score += 0.15
        elif subjects_count >= 6:
            score += 0.05
        elif subjects_count < 6:
            score -= 0.25
        
        # Points per subject (average grade)
        points_per_subject = features.get('points_per_subject', 5)
        if points_per_subject <= 2:
            score += 0.2
        elif points_per_subject <= 3:
            score += 0.1
        elif points_per_subject >= 4:
            score -= 0.1
        
        # Credit subjects
        if features.get('has_credit_english', False):
            score += 0.05
        if features.get('has_credit_math', False):
            score += 0.1
        if features.get('has_credit_science', False):
            score += 0.05
        
        # Application completeness
        score += features.get('application_completeness', 0.5) * 0.1
        
        # Competition (if available)
        programme_applicants = features.get('programme_applicants_count', 50)
        programme_capacity = features.get('programme_capacity', 50)
        if programme_capacity > 0:
            competition_ratio = programme_applicants / programme_capacity
            if competition_ratio < 0.8:
                score += 0.05
            elif competition_ratio > 1.5:
                score -= 0.1
        
        return min(max(score, 0.1), 0.95)
    
    def _generate_factors(self, features: Dict, probability: float) -> List[Dict]:
        """Generate factors that influenced the prediction"""
        factors = []
        
        # Academic performance factors
        total_points = features.get('total_points', 30)
        if total_points <= 24:
            factors.append({
                'factor': 'Excellent MSCE performance',
                'impact': 'positive',
                'details': f"Total points: {total_points} (Excellent range: ≤24)"
            })
        elif total_points <= 28:
            factors.append({
                'factor': 'Good MSCE performance',
                'impact': 'positive',
                'details': f"Total points: {total_points} (Good range: 25-28)"
            })
        elif total_points <= 32:
            factors.append({
                'factor': 'Average MSCE performance',
                'impact': 'neutral',
                'details': f"Total points: {total_points} (Average range: 29-32)"
            })
        elif total_points >= 36:
            factors.append({
                'factor': 'MSCE performance needs improvement',
                'impact': 'negative',
                'details': f"Total points: {total_points} (Below average: ≥36)"
            })
        
        # Subjects count
        subjects_count = features.get('subjects_count', 0)
        if subjects_count >= 8:
            factors.append({
                'factor': 'Strong subject portfolio',
                'impact': 'positive',
                'details': f"{subjects_count} MSCE subjects (minimum required: 6)"
            })
        elif subjects_count < 6:
            factors.append({
                'factor': 'Insufficient subjects',
                'impact': 'negative',
                'details': f"Only {subjects_count} subjects (minimum 6 required)"
            })
        
        # Credit subjects
        if features.get('has_credit_math', False):
            factors.append({
                'factor': 'Strong performance in Mathematics',
                'impact': 'positive',
                'details': 'Credit or better in Mathematics'
            })
        else:
            factors.append({
                'factor': 'Mathematics grade needs improvement',
                'impact': 'negative',
                'details': 'Credit in Mathematics enhances chances'
            })
        
        if features.get('has_credit_english', False):
            factors.append({
                'factor': 'Good performance in English',
                'impact': 'positive',
                'details': 'Credit or better in English'
            })
        
        if features.get('has_credit_science', False):
            factors.append({
                'factor': 'Strong science background',
                'impact': 'positive',
                'details': 'Credit or better in a science subject'
            })
        
        # Application completeness
        completeness = features.get('application_completeness', 0)
        completeness_pct = completeness * 100
        if completeness_pct >= 80:
            factors.append({
                'factor': 'Complete application',
                'impact': 'positive',
                'details': f"Application {completeness_pct:.0f}% complete"
            })
        elif completeness_pct < 50:
            factors.append({
                'factor': 'Incomplete application',
                'impact': 'negative',
                'details': f"Application only {completeness_pct:.0f}% complete - add missing information"
            })
        
        # Documents and fee
        if features.get('documents_uploaded', False):
            factors.append({
                'factor': 'Supporting documents uploaded',
                'impact': 'positive',
                'details': 'All required documents submitted'
            })
        
        if features.get('fee_paid', False):
            factors.append({
                'factor': 'Application fee paid',
                'impact': 'positive',
                'details': 'Fee payment verified'
            })
        else:
            factors.append({
                'factor': 'Pending fee payment',
                'impact': 'negative',
                'details': 'Complete fee payment to finalize application'
            })
        
        return factors
    
    def _generate_recommendation(self, probability: float, features: Dict) -> str:
        """Generate recommendation based on prediction"""
        if probability >= 0.8:
            return "Strongly recommend admission. Excellent candidate with high probability of success."
        elif probability >= 0.6:
            return "Recommend admission. Good candidate with strong academic background."
        elif probability >= 0.4:
            return "Consider for admission with review. Candidate meets minimum requirements."
        else:
            # Provide specific improvement suggestions
            suggestions = []
            if not features.get('has_credit_math', False):
                suggestions.append("improve Mathematics grade")
            if not features.get('has_credit_english', False):
                suggestions.append("improve English grade")
            if features.get('subjects_count', 0) < 6:
                suggestions.append("add more MSCE subjects (minimum 6 required)")
            if features.get('total_points', 30) > 32:
                suggestions.append("improve overall MSCE performance")
            if not features.get('documents_uploaded', False):
                suggestions.append("upload all required supporting documents")
            if not features.get('fee_paid', False):
                suggestions.append("complete fee payment")
            
            suggestions_text = ", ".join(suggestions) if suggestions else "improve overall application"
            
            return f"Admission not recommended at this time. To improve chances: {suggestions_text} before reapplying."
    
    def load_model(self):
        """Load the trained model from train_model.py"""
        try:
            if self.model_path.exists():
                with open(self.model_path, 'rb') as f:
                    self.model = pickle.load(f)
                logger.info(f"✅ Model loaded from {self.model_path}")
            else:
                logger.warning(f"⚠️ Model not found at {self.model_path}")
                self.model = None
            
            if self.scaler_path.exists():
                with open(self.scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
                logger.info(f"✅ Scaler loaded from {self.scaler_path}")
            else:
                logger.warning(f"⚠️ Scaler not found at {self.scaler_path}")
                self.scaler = None
            
            if self.features_path.exists():
                with open(self.features_path, 'rb') as f:
                    loaded_features = pickle.load(f)
                    logger.info(f"✅ Features loaded from {self.features_path}")
            
            # Load model info if available
            if self.model_info_path.exists():
                with open(self.model_info_path, 'r') as f:
                    self.model_info = json.load(f)
                    logger.info(f"✅ Model info loaded from {self.model_info_path}")
            
            return self.model is not None
            
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            self.model = None
            self.scaler = None
            return False
    
    def save_model(self):
        """Save the trained model (for training script)"""
        if self.model:
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            logger.info(f"Model saved to {self.model_path}")
        
        if self.scaler:
            with open(self.scaler_path, 'wb') as f:
                pickle.dump(self.scaler, f)
            logger.info(f"Scaler saved to {self.scaler_path}")
        
        if self.feature_columns:
            with open(self.features_path, 'wb') as f:
                pickle.dump(self.feature_columns, f)
            logger.info(f"Features saved to {self.features_path}")
    
    def get_model_info(self) -> Dict:
        """Get information about the current model"""
        info = {
            'model_loaded': self.model is not None,
            'model_path': str(self.model_path) if self.model_path.exists() else None,
            'scaler_loaded': self.scaler is not None,
            'feature_columns': self.feature_columns,
            'priority_thresholds': self.priority_thresholds
        }
        
        if self.model_info_path.exists():
            try:
                with open(self.model_info_path, 'r') as f:
                    trained_info = json.load(f)
                    info['trained_model_info'] = trained_info
            except:
                pass
        
        return info
    
    def get_feature_importance(self) -> Dict:
        """Get feature importance from the trained model"""
        if self.model is not None and hasattr(self.model, 'feature_importances_'):
            importance = dict(zip(self.feature_columns, self.model.feature_importances_))
            # Sort by importance
            importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
            return importance
        return {}


# Singleton instance
admission_predictor = AdmissionPredictor()