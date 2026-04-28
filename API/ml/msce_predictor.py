import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import joblib
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class MSCEPredictor:
    """Machine Learning model for predicting admission based on MSCE results"""
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.label_encoders = {}

        self.feature_columns = [
            'english_grade', 'math_grade', 'best_science_grade',
            'total_points', 'num_subjects', 'average_grade',
            'has_credit_english', 'has_credit_math', 'has_credit_science'
        ]
        self.model_path = Path(__file__).parent / 'models' / 'msce_admission_model.pkl'
        self.scaler_path = Path(__file__).parent / 'models' / 'msce_scaler.pkl'
        self.load_model()
    
    def grade_to_points(self, grade: str) -> int:
        """Convert MSCE grade to points (1=best, 6=worst)"""
        grade_map = {
            'A': 1, 'A*': 1,
            'B': 2, 'B+': 2,
            'C': 3, 'C+': 3,
            'D': 4, 'D+': 4,
            'E': 5,
            'F': 6, 'O': 4, 'S': 5
        }
        grade_upper = str(grade).upper().strip()
        return grade_map.get(grade_upper, 5)
    
    def is_credit(self, grade: str) -> bool:
        """Check if grade is a credit (C or better)"""
        points = self.grade_to_points(grade)
        return points <= 3
    
    
    def extract_features(self, subjects_data):
        """Extract features from subject data"""
        features = {}
        
        # Find English grade
        english_grade = None
        math_grade = None
        best_science_grade = None
        science_subjects = ['PHYSICS', 'CHEMISTRY', 'BIOLOGY', 'SCIENCE', 'GENERAL SCIENCE']
        
        for subject in subjects_data:
            subject_name = subject.get('subject', '').upper()
            grade = subject.get('grade', '')
            
            if 'ENGLISH' in subject_name:
                english_grade = grade
            elif 'MATH' in subject_name or 'MATHEMATICS' in subject_name:
                math_grade = grade
            elif any(sci in subject_name for sci in science_subjects):
                current_points = self.grade_to_points(grade)
                best_points = self.grade_to_points(best_science_grade) if best_science_grade else 99
                if current_points < best_points:
                    best_science_grade = grade
        
        # Calculate numerical features
        all_grades = [self.grade_to_points(s.get('grade', '')) for s in subjects_data if s.get('grade')]
        
        features['english_points'] = self.grade_to_points(english_grade) if english_grade else 5
        features['math_points'] = self.grade_to_points(math_grade) if math_grade else 5
        features['science_points'] = self.grade_to_points(best_science_grade) if best_science_grade else 5
        
        features['english_grade'] = self.grade_to_points(english_grade) if english_grade else 5
        features['math_grade'] = self.grade_to_points(math_grade) if math_grade else 5
        features['best_science_grade'] = self.grade_to_points(best_science_grade) if best_science_grade else 5
        
        features['total_points'] = sum(all_grades) if all_grades else 30
        features['num_subjects'] = len(all_grades)
        features['average_grade'] = features['total_points'] / max(features['num_subjects'], 1)
        
        features['has_credit_english'] = 1 if english_grade and self.is_credit(english_grade) else 0
        features['has_credit_math'] = 1 if math_grade and self.is_credit(math_grade) else 0
        features['has_credit_science'] = 1 if best_science_grade and self.is_credit(best_science_grade) else 0
        
        return features
    
    def predict(self, subjects_data):
        """Predict admission probability for a student"""
        try:
            features = self.extract_features(subjects_data)
            feature_vector = np.array([[features[col] for col in self.feature_columns]])
            
            if self.model is not None:
                # Scale features
                feature_vector = self.scaler.transform(feature_vector)
                probability = self.model.predict_proba(feature_vector)[0][1]
            else:
                # Fallback: rule-based prediction
                probability = self._rule_based_prediction(features)
            
            # Determine prediction category
            if probability >= 0.7:
                prediction = 1  # Strong admit
                message = "Strong candidate - High probability of admission"
            elif probability >= 0.5:
                prediction = 2  # Likely admit
                message = "Good candidate - Likely to be admitted"
            elif probability >= 0.3:
                prediction = 3  # Borderline
                message = "Borderline candidate - Needs improvement in key subjects"
            else:
                prediction = 4  # Weak
                message = "Weak candidate - Consider retaking exams or alternative programs"
            
            return {
                'success': True,
                'probability': float(probability),
                'prediction': prediction,
                'message': message,
                'features': features,
                'using_ml': self.model is not None
            }
            
        except Exception as e:
            logger.error(f"Prediction error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'probability': 0.5,
                'prediction': 3,
                'using_ml': False
            }
    
    def _rule_based_prediction(self, features):
        """Fallback rule-based prediction when ML model is not available"""
        score = 0.5  # Base score
        
        # English grade impact
        if features['english_points'] <= 2:
            score += 0.2
        elif features['english_points'] >= 5:
            score -= 0.15
        
        # Math grade impact
        if features['math_points'] <= 2:
            score += 0.2
        elif features['math_points'] >= 5:
            score -= 0.15
        
        # Science grade impact
        if features['science_points'] <= 2:
            score += 0.15
        elif features['science_points'] >= 5:
            score -= 0.1
        
        # Average grade impact
        if features['average_grade'] <= 2.5:
            score += 0.2
        elif features['average_grade'] >= 4.5:
            score -= 0.2
        
        return min(max(score, 0.1), 0.95)
    
    def train_from_csv(self, csv_path, target_column='admitted'):
        """Train the model from a CSV file"""
        try:
            df = pd.read_csv(csv_path)
            
            # Prepare features
            X = df[self.feature_columns]
            y = df[target_column]
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train model
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            self.model.fit(X_train_scaled, y_train)
            
            # Evaluate
            y_pred = self.model.predict(X_test_scaled)
            y_pred_proba = self.model.predict_proba(X_test_scaled)[:, 1]
            
            metrics = {
                'accuracy': accuracy_score(y_test, y_pred),
                'precision': precision_score(y_test, y_pred),
                'recall': recall_score(y_test, y_pred),
                'f1_score': f1_score(y_test, y_pred),
                'roc_auc': roc_auc_score(y_test, y_pred_proba)
            }
            
            # Save model
            self.save_model()
            
            return {
                'success': True,
                'metrics': metrics,
                'message': f"Model trained successfully. Accuracy: {metrics['accuracy']:.2%}"
            }
            
        except Exception as e:
            logger.error(f"Training error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def save_model(self):
        """Save the trained model"""
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

# Singleton instance
msce_predictor = MSCEPredictor()