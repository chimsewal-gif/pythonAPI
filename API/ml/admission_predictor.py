"""
Machine Learning Model for Admission Prediction and Prioritisation
Predicts applicant success probability and assigns priority levels
"""

import pandas as pd
import numpy as np
import joblib
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
        self.scaler = StandardScaler()
        self.feature_columns = [
            'msce_points', 'msce_subjects_count', 'msce_average_grade',
            'has_credit_english', 'has_credit_math', 'has_credit_science',
            'programme_competition_ratio', 'previous_education_level',
            'years_since_msce', 'application_completeness_score'
        ]
        self.priority_thresholds = {
            'High': 0.7,
            'Medium': 0.4,
            'Low': 0.0
        }
        self.model_path = Path(__file__).parent / 'models' / 'admission_predictor.pkl'
        self.scaler_path = Path(__file__).parent / 'models' / 'predictor_scaler.pkl'
        
        # Create models directory
        (Path(__file__).parent / 'models').mkdir(exist_ok=True)
        
        self.load_model()
    
    def calculate_msce_points(self, grade: str) -> int:
        """Convert MSCE grade to points (lower is better)"""
        grade_map = {
            '1': 1, 'A*': 1, 'A': 1,
            '2': 2, 'B': 2,
            '3': 3, 'C': 3,
            '4': 4, 'D': 4,
            '5': 5, 'E': 5,
            '6': 6, 'F': 6,
            'U': 9
        }
        return grade_map.get(str(grade).upper(), 5)
    
    def is_credit(self, grade: str) -> bool:
        """Check if grade is a credit (3 or better)"""
        points = self.calculate_msce_points(grade)
        return points <= 3
    
    def extract_features(self, applicant_data: Dict) -> np.ndarray:
        """Extract features from applicant data for prediction"""
        
        # Get MSCE results
        subject_records = applicant_data.get('subject_records', [])
        msce_subjects = [s for s in subject_records if s.get('qualification') == 'MSCE (Malawi School Certificate of Education)']
        
        # Calculate MSCE metrics
        points_list = []
        has_credit_english = False
        has_credit_math = False
        has_credit_science = False
        
        for subject in msce_subjects:
            grade = subject.get('grade', '')
            points = self.calculate_msce_points(grade)
            points_list.append(points)
            
            subject_name = subject.get('subject', '').lower()
            if 'english' in subject_name:
                has_credit_english = self.is_credit(grade)
            elif 'math' in subject_name or 'mathematics' in subject_name:
                has_credit_math = self.is_credit(grade)
            elif any(sci in subject_name for sci in ['biology', 'chemistry', 'physics', 'science']):
                has_credit_science = self.is_credit(grade)
        
        total_points = sum(points_list) if points_list else 30
        num_subjects = len(points_list)
        average_points = total_points / max(num_subjects, 1)
        
        # Programme competition (based on number of applicants)
        programme_applicants = applicant_data.get('programme_applicants_count', 1)
        programme_capacity = applicant_data.get('programme_capacity', 50)
        competition_ratio = min(programme_applicants / max(programme_capacity, 1), 2.0)
        
        # Years since MSCE
        msce_year = applicant_data.get('msce_year', datetime.now().year)
        years_since_msce = datetime.now().year - msce_year
        
        # Application completeness (0-1 scale)
        completeness_score = self.calculate_completeness_score(applicant_data)
        
        # Education level encoding
        education_level = applicant_data.get('highest_education', 'msce')
        education_map = {
            'msce': 1,
            'diploma': 2,
            'degree': 3,
            'postgraduate': 4
        }
        education_level_encoded = education_map.get(education_level.lower(), 1)
        
        features = {
            'msce_points': total_points,
            'msce_subjects_count': num_subjects,
            'msce_average_grade': average_points,
            'has_credit_english': 1 if has_credit_english else 0,
            'has_credit_math': 1 if has_credit_math else 0,
            'has_credit_science': 1 if has_credit_science else 0,
            'programme_competition_ratio': competition_ratio,
            'previous_education_level': education_level_encoded,
            'years_since_msce': min(years_since_msce, 10),
            'application_completeness_score': completeness_score
        }
        
        # Convert to numpy array
        feature_vector = np.array([[features[col] for col in self.feature_columns]])
        
        return feature_vector, features
    
    def calculate_completeness_score(self, applicant_data: Dict) -> float:
        """Calculate application completeness score (0-1)"""
        score = 0
        total = 6
        
        # Personal details
        if applicant_data.get('personal_details_complete'):
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
            
            # Scale features
            feature_vector_scaled = self.scaler.transform(feature_vector)
            
            # Get prediction probability
            if self.model is not None:
                probability = float(self.model.predict_proba(feature_vector_scaled)[0][1])
                confidence = float(max(self.model.predict_proba(feature_vector_scaled)[0]))
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
                'message': f"Prediction complete. Priority: {priority}"
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
        
        # MSCE points impact
        if features['msce_points'] <= 25:
            score += 0.15
        elif features['msce_points'] >= 35:
            score -= 0.15
        
        # Credit subjects impact
        if features['has_credit_english']:
            score += 0.1
        if features['has_credit_math']:
            score += 0.1
        if features['has_credit_science']:
            score += 0.1
        
        # Subjects count impact
        if features['msce_subjects_count'] >= 8:
            score += 0.1
        elif features['msce_subjects_count'] < 6:
            score -= 0.2
        
        # Application completeness
        score += features['application_completeness_score'] * 0.1
        
        # Competition ratio
        if features['programme_competition_ratio'] < 0.8:
            score += 0.05
        elif features['programme_competition_ratio'] > 1.5:
            score -= 0.1
        
        return min(max(score, 0.1), 0.95)
    
    def _generate_factors(self, features: Dict, probability: float) -> List[Dict]:
        """Generate factors that influenced the prediction"""
        factors = []
        
        # Academic performance factors
        if features['msce_points'] <= 25:
            factors.append({
                'factor': 'Excellent MSCE performance',
                'impact': 'positive',
                'details': f"Total points: {features['msce_points']} (below 25)"
            })
        elif features['msce_points'] >= 35:
            factors.append({
                'factor': 'MSCE performance needs improvement',
                'impact': 'negative',
                'details': f"Total points: {features['msce_points']} (above 35)"
            })
        
        # Credit subjects
        if features['has_credit_english']:
            factors.append({
                'factor': 'Strong performance in English',
                'impact': 'positive',
                'details': 'Credit or better in English'
            })
        
        if features['has_credit_math']:
            factors.append({
                'factor': 'Strong performance in Mathematics',
                'impact': 'positive',
                'details': 'Credit or better in Mathematics'
            })
        
        if features['has_credit_science']:
            factors.append({
                'factor': 'Strong performance in Sciences',
                'impact': 'positive',
                'details': 'Credit or better in a science subject'
            })
        
        # Subjects count
        if features['msce_subjects_count'] >= 8:
            factors.append({
                'factor': 'Comprehensive subject portfolio',
                'impact': 'positive',
                'details': f"{features['msce_subjects_count']} MSCE subjects"
            })
        elif features['msce_subjects_count'] < 6:
            factors.append({
                'factor': 'Insufficient subjects',
                'impact': 'negative',
                'details': f"Only {features['msce_subjects_count']} subjects (minimum 6 required)"
            })
        
        # Application completeness
        completeness_pct = features['application_completeness_score'] * 100
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
                'details': f"Application only {completeness_pct:.0f}% complete"
            })
        
        # Competition
        if features['programme_competition_ratio'] < 0.8:
            factors.append({
                'factor': 'Lower programme competition',
                'impact': 'positive',
                'details': 'Fewer applicants per slot'
            })
        elif features['programme_competition_ratio'] > 1.5:
            factors.append({
                'factor': 'High programme competition',
                'impact': 'negative',
                'details': 'Many applicants for limited slots'
            })
        
        # Education level
        if features['previous_education_level'] >= 3:
            factors.append({
                'factor': 'Higher education background',
                'impact': 'positive',
                'details': 'Previous degree or diploma'
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
            if not features['has_credit_english']:
                suggestions.append("consider improving English grade")
            if not features['has_credit_math']:
                suggestions.append("strengthen Mathematics performance")
            if features['msce_subjects_count'] < 6:
                suggestions.append("add more MSCE subjects")
            
            suggestions_text = " or ".join(suggestions) if suggestions else "improve overall MSCE performance"
            
            return f"Admission not recommended. To improve chances, {suggestions_text} before reapplying."
    
    def generate_training_data(self, historical_applications: List[Dict]) -> pd.DataFrame:
        """
        Generate synthetic training data based on historical applications
        In production, this would use real historical admission data
        """
        np.random.seed(42)
        
        data = []
        
        for _ in range(1000):
            # Generate random but realistic applicant profiles
            msce_points = np.random.choice(range(20, 45), p=[0.05, 0.08, 0.1, 0.12, 0.12, 0.1, 0.1, 0.08, 0.08, 0.07, 0.05, 0.03, 0.02, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01])
            subjects_count = np.random.choice(range(4, 11))
            avg_points = msce_points / max(subjects_count, 1)
            
            has_credit_english = np.random.choice([0, 1], p=[0.3, 0.7])
            has_credit_math = np.random.choice([0, 1], p=[0.4, 0.6])
            has_credit_science = np.random.choice([0, 1], p=[0.35, 0.65])
            
            competition_ratio = np.random.uniform(0.5, 2.0)
            education_level = np.random.choice([1, 2, 3, 4], p=[0.6, 0.2, 0.15, 0.05])
            years_since_msce = np.random.choice(range(0, 8))
            completeness_score = np.random.uniform(0.4, 1.0)
            
            # Determine success outcome based on features
            score = 0
            score += (30 - min(msce_points, 30)) / 30 * 0.3
            score += (subjects_count - 4) / 6 * 0.15
            score += has_credit_english * 0.1
            score += has_credit_math * 0.1
            score += has_credit_science * 0.1
            score += (1 - competition_ratio / 2) * 0.1
            score += (education_level - 1) / 3 * 0.05
            score += completeness_score * 0.1
            
            # Add noise
            score += np.random.normal(0, 0.05)
            
            success = 1 if score > 0.5 else 0
            
            data.append({
                'msce_points': msce_points,
                'msce_subjects_count': subjects_count,
                'msce_average_grade': avg_points,
                'has_credit_english': has_credit_english,
                'has_credit_math': has_credit_math,
                'has_credit_science': has_credit_science,
                'programme_competition_ratio': competition_ratio,
                'previous_education_level': education_level,
                'years_since_msce': years_since_msce,
                'application_completeness_score': completeness_score,
                'success': success
            })
        
        return pd.DataFrame(data)
    
    def train_model(self, historical_data: Optional[List[Dict]] = None):
        """Train the ML model using historical data or generate synthetic data"""
        try:
            if historical_data:
                df = pd.DataFrame(historical_data)
            else:
                df = self.generate_training_data(None)
            
            # Prepare features
            X = df[self.feature_columns]
            y = df['success']
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train model with hyperparameter tuning
            param_grid = {
                'n_estimators': [100, 200],
                'max_depth': [5, 10, 15],
                'min_samples_split': [2, 5, 10],
                'min_samples_leaf': [1, 2, 4]
            }
            
            base_model = RandomForestClassifier(random_state=42, class_weight='balanced')
            grid_search = GridSearchCV(base_model, param_grid, cv=5, scoring='roc_auc', n_jobs=-1)
            grid_search.fit(X_train_scaled, y_train)
            
            self.model = grid_search.best_estimator_
            
            # Evaluate model
            y_pred = self.model.predict(X_test_scaled)
            y_pred_proba = self.model.predict_proba(X_test_scaled)[:, 1]
            
            metrics = {
                'accuracy': accuracy_score(y_test, y_pred),
                'precision': precision_score(y_test, y_pred, zero_division=0),
                'recall': recall_score(y_test, y_pred, zero_division=0),
                'f1_score': f1_score(y_test, y_pred, zero_division=0),
                'roc_auc': roc_auc_score(y_test, y_pred_proba),
                'best_params': grid_search.best_params_
            }
            
            # Save model
            self.save_model()
            
            logger.info(f"Model trained successfully. Accuracy: {metrics['accuracy']:.2%}")
            
            return {
                'success': True,
                'metrics': metrics,
                'message': f"Model trained. AUC: {metrics['roc_auc']:.3f}"
            }
            
        except Exception as e:
            logger.error(f"Training error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def save_model(self):
        """Save the trained model and scaler"""
        if self.model:
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.scaler, self.scaler_path)
            logger.info(f"Model saved to {self.model_path}")
    
    def load_model(self):
        """Load a trained model"""
        if self.model_path.exists() and self.scaler_path.exists():
            try:
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                logger.info(f"Model loaded from {self.model_path}")
                return True
            except Exception as e:
                logger.error(f"Error loading model: {str(e)}")
                return False
        return False
    
    def get_model_info(self) -> Dict:
        """Get information about the current model"""
        return {
            'model_loaded': self.model is not None,
            'model_path': str(self.model_path) if self.model_path.exists() else None,
            'feature_columns': self.feature_columns,
            'priority_thresholds': self.priority_thresholds
        }


# Singleton instance
admission_predictor = AdmissionPredictor()