import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import joblib
import os
from pathlib import Path
import logging
import re
from typing import List, Dict

logger = logging.getLogger(__name__)

class MSCEPredictor:
    """Machine Learning model for predicting admission based on MSCE results"""
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        
        # Define the path to the Excel file
        self.excel_path = None
        possible_paths = [
            Path(__file__).parent / 'all.xlsx',
            Path(__file__).parent.parent / 'all.xlsx',
            Path(__file__).parent.parent.parent / 'all.xlsx',
            Path('/run/media/lewin/DATA/fourthyear-project/API/API/ml/all.xlsx'),
        ]
        for path in possible_paths:
            if path.exists():
                self.excel_path = str(path)
                break
        
        self.feature_columns = [
            'english_grade', 'math_grade', 'best_science_grade',
            'total_points', 'num_subjects', 'average_grade',
            'has_credit_english', 'has_credit_math', 'has_credit_science',
            'meets_min_credits', 'points_within_limit', 'subject_count_ratio'
        ]
        
        self.model_path = Path(__file__).parent / 'models' / 'msce_admission_model.pkl'
        self.scaler_path = Path(__file__).parent / 'models' / 'msce_scaler.pkl'
        
        # Create models directory if it doesn't exist
        (Path(__file__).parent / 'models').mkdir(exist_ok=True)
        
        self.load_model()
    
    def grade_to_points(self, grade: str) -> int:
        """Convert MSCE grade to points (1=best, 6=worst)"""
        grade_map = {
            '1': 1, 'A': 1, 'A*': 1,
            '2': 2, 'B': 2, 'B+': 2,
            '3': 3, 'C': 3, 'C+': 3,
            '4': 4, 'D': 4, 'D+': 4,
            '5': 5, 'E': 5,
            '6': 6, 'F': 6, 'U': 9
        }
        grade_upper = str(grade).upper().strip()
        return grade_map.get(grade_upper, 5)
    
    def is_credit(self, grade: str) -> bool:
        """Check if grade is a credit (3 or better / C or better)"""
        points = self.grade_to_points(grade)
        return points <= 3
    
    def load_programmes_from_excel(self) -> pd.DataFrame:
        """Load programmes from Excel file to extract admission criteria"""
        if not self.excel_path or not Path(self.excel_path).exists():
            logger.warning(f"Excel file not found at {self.excel_path}")
            return pd.DataFrame()
        
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Programmes')
            logger.info(f"Loaded {len(df)} programmes from Excel")
            return df
        except Exception as e:
            logger.error(f"Error loading Excel file: {e}")
            return pd.DataFrame()
    
    def extract_subjects_from_text(self, text: str) -> List[str]:
        """Extract subject names from text"""
        subjects = []
        subject_patterns = [
            'English', 'Mathematics', 'Math', 'Biology', 'Chemistry', 'Physics',
            'Physical Science', 'Geography', 'History', 'Chichewa', 'French',
            'Computer Studies', 'Agriculture', 'Home Economics', 'Commerce',
            'Accounts', 'Bible Knowledge', 'Social Studies', 'Life Skills'
        ]
        
        text_lower = text.lower()
        for subject in subject_patterns:
            if subject.lower() in text_lower:
                subjects.append(subject)
        
        return subjects
    
    def extract_admission_criteria_from_programmes(self) -> Dict:
        """Extract admission criteria from programme data"""
        df = self.load_programmes_from_excel()
        if df.empty:
            return {}
        
        criteria = {
            'min_credits': 6,
            'max_points': 30,
            'required_subjects': ['English', 'Mathematics'],
            'science_subjects': ['Biology', 'Chemistry', 'Physics', 'Physical Science'],
            'humanities_subjects': ['History', 'Geography', 'Social Studies', 'Bible Knowledge'],
        }
        
        min_credits_list = []
        max_points_list = []
        all_required_subjects = set()
        
        for _, row in df.iterrows():
            entry_req = str(row.get('Entry Requirements', ''))
            
            credit_match = re.search(r'(\d+)\s*credits', entry_req.lower())
            if credit_match:
                min_credits_list.append(int(credit_match.group(1)))
            
            point_match = re.search(r'(\d+)\s*points', entry_req.lower())
            if point_match:
                max_points_list.append(int(point_match.group(1)))
            
            subjects = self.extract_subjects_from_text(entry_req)
            all_required_subjects.update(subjects)
        
        if min_credits_list:
            criteria['min_credits'] = max(min_credits_list)
        if max_points_list:
            criteria['max_points'] = min(max_points_list)
        if all_required_subjects:
            criteria['required_subjects'] = list(all_required_subjects)[:5]
        
        return criteria
    
    def extract_features(self, subjects_data: List[Dict]) -> Dict:
        """Extract features from subject data"""
        features = {
            'english_grade': 5,
            'math_grade': 5,
            'best_science_grade': 5,
            'total_points': 30,
            'num_subjects': 0,
            'average_grade': 5,
            'has_credit_english': 0,
            'has_credit_math': 0,
            'has_credit_science': 0,
            'meets_min_credits': 0,
            'points_within_limit': 0,
            'subject_count_ratio': 0
        }
        
        criteria = self.extract_admission_criteria_from_programmes()
        min_credits = criteria.get('min_credits', 6)
        max_points = criteria.get('max_points', 30)
        
        english_grade = None
        math_grade = None
        best_science_grade = None
        science_subjects = ['BIOLOGY', 'CHEMISTRY', 'PHYSICS', 'SCIENCE', 'PHYSICAL SCIENCE']
        
        all_grades = []
        
        for subject in subjects_data:
            subject_name = subject.get('subject', '').upper()
            grade = subject.get('grade', '')
            
            if not grade:
                continue
                
            points = self.grade_to_points(grade)
            all_grades.append(points)
            
            if 'ENGLISH' in subject_name:
                english_grade = grade
                features['english_grade'] = points
                features['has_credit_english'] = 1 if self.is_credit(grade) else 0
            elif 'MATH' in subject_name or 'MATHEMATICS' in subject_name:
                math_grade = grade
                features['math_grade'] = points
                features['has_credit_math'] = 1 if self.is_credit(grade) else 0
            elif any(sci in subject_name for sci in science_subjects):
                current_points = points
                best_points = self.grade_to_points(best_science_grade) if best_science_grade else 99
                if current_points < best_points:
                    best_science_grade = grade
                    features['best_science_grade'] = points
                    features['has_credit_science'] = 1 if self.is_credit(grade) else 0
        
        features['total_points'] = sum(all_grades) if all_grades else 30
        features['num_subjects'] = len(all_grades)
        features['average_grade'] = features['total_points'] / max(features['num_subjects'], 1)
        
        features['meets_min_credits'] = 1 if features['num_subjects'] >= min_credits else 0
        features['points_within_limit'] = 1 if features['total_points'] <= max_points else 0
        features['subject_count_ratio'] = features['num_subjects'] / max(min_credits, 1)
        
        return features
    
    def generate_training_data(self, num_samples: int = 2000) -> pd.DataFrame:
        """Generate synthetic training data based on programme requirements"""
        criteria = self.extract_admission_criteria_from_programmes()
        min_credits = criteria.get('min_credits', 6)
        max_points = criteria.get('max_points', 30)
        
        np.random.seed(42)
        
        data = []
        
        for _ in range(num_samples):
            num_subjects = np.random.randint(4, 11)
            
            english_points = np.random.choice([1, 2, 3, 4, 5, 6, 9], p=[0.1, 0.15, 0.2, 0.2, 0.15, 0.1, 0.1])
            math_points = np.random.choice([1, 2, 3, 4, 5, 6, 9], p=[0.1, 0.15, 0.2, 0.2, 0.15, 0.1, 0.1])
            science_points = np.random.choice([1, 2, 3, 4, 5, 6, 9], p=[0.1, 0.15, 0.2, 0.2, 0.15, 0.1, 0.1])
            
            other_grades = np.random.choice([1, 2, 3, 4, 5, 6, 9], size=num_subjects - 3, p=[0.1, 0.15, 0.2, 0.2, 0.15, 0.1, 0.1])
            
            total_points = english_points + math_points + science_points + sum(other_grades)
            average_grade = total_points / num_subjects
            
            meets_credits = num_subjects >= min_credits
            meets_points = total_points <= max_points
            meets_english = english_points <= 3
            meets_math = math_points <= 3
            meets_science = science_points <= 3
            
            score = 0
            if meets_credits:
                score += 0.25
            if meets_points:
                score += 0.25
            if meets_english:
                score += 0.2
            if meets_math:
                score += 0.15
            if meets_science:
                score += 0.15
            
            score += np.random.normal(0, 0.1)
            probability = min(max(score, 0), 1)
            admitted = 1 if probability > 0.5 else 0
            
            data.append({
                'english_grade': english_points,
                'math_grade': math_points,
                'best_science_grade': science_points,
                'total_points': total_points,
                'num_subjects': num_subjects,
                'average_grade': average_grade,
                'has_credit_english': 1 if english_points <= 3 else 0,
                'has_credit_math': 1 if math_points <= 3 else 0,
                'has_credit_science': 1 if science_points <= 3 else 0,
                'meets_min_credits': 1 if meets_credits else 0,
                'points_within_limit': 1 if meets_points else 0,
                'subject_count_ratio': num_subjects / max(min_credits, 1),
                'admitted': admitted,
                'admission_probability': probability
            })
        
        return pd.DataFrame(data)
    
    def train(self, num_samples: int = 2000):
        """Train the model"""
        try:
            df = self.generate_training_data(num_samples)
            
            if df.empty:
                return {
                    'success': False,
                    'error': 'Could not generate training data'
                }
            
            feature_cols = [col for col in self.feature_columns if col in df.columns]
            X = df[feature_cols]
            y = df['admitted']
            
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            self.model = RandomForestClassifier(
                n_estimators=150,
                max_depth=12,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42
            )
            self.model.fit(X_train_scaled, y_train)
            
            y_pred = self.model.predict(X_test_scaled)
            y_pred_proba = self.model.predict_proba(X_test_scaled)[:, 1]
            
            metrics = {
                'accuracy': accuracy_score(y_test, y_pred),
                'precision': precision_score(y_test, y_pred, zero_division=0),
                'recall': recall_score(y_test, y_pred, zero_division=0),
                'f1_score': f1_score(y_test, y_pred, zero_division=0),
                'roc_auc': roc_auc_score(y_test, y_pred_proba)
            }
            
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
    
    def predict(self, subjects_data: List[Dict]) -> Dict:
        """Predict admission probability for a student"""
        try:
            features = self.extract_features(subjects_data)
            feature_vector = np.array([[features[col] for col in self.feature_columns if col in features]])
            
            if self.model is not None:
                feature_vector = self.scaler.transform(feature_vector)
                probability = self.model.predict_proba(feature_vector)[0][1]
            else:
                criteria = self.extract_admission_criteria_from_programmes()
                probability = self._rule_based_prediction(features, criteria)
            
            if probability >= 0.75:
                prediction = 1
                message = "Excellent candidate - Very high probability of admission"
            elif probability >= 0.6:
                prediction = 2
                message = "Good candidate - Likely to be admitted"
            elif probability >= 0.4:
                prediction = 3
                message = "Borderline candidate - Consider improving key subjects"
            else:
                prediction = 4
                message = "Weak candidate - Consider retaking exams or alternative programs"
            
            feedback = self._generate_feedback(features)
            
            return {
                'success': True,
                'probability': float(probability),
                'prediction': prediction,
                'message': message,
                'features': features,
                'feedback': feedback,
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
    
    def _rule_based_prediction(self, features: Dict, criteria: Dict) -> float:
        """Fallback rule-based prediction"""
        min_credits = criteria.get('min_credits', 6)
        max_points = criteria.get('max_points', 30)
        
        score = 0.5
        
        if features.get('meets_min_credits', 0):
            score += 0.15
        elif features.get('num_subjects', 0) >= min_credits - 1:
            score += 0.05
        else:
            score -= 0.1
        
        if features.get('points_within_limit', 0):
            score += 0.15
        elif features.get('total_points', 30) <= max_points + 10:
            score += 0.05
        else:
            score -= 0.1
        
        if features.get('has_credit_english', 0):
            score += 0.1
        else:
            score -= 0.05
        
        if features.get('has_credit_math', 0):
            score += 0.1
        else:
            score -= 0.05
        
        if features.get('has_credit_science', 0):
            score += 0.1
        else:
            score -= 0.05
        
        avg_grade = features.get('average_grade', 5)
        if avg_grade <= 3:
            score += 0.15
        elif avg_grade >= 5:
            score -= 0.15
        
        return min(max(score, 0.1), 0.95)
    
    def _generate_feedback(self, features: Dict) -> List[str]:
        """Generate specific feedback for the student"""
        feedback = []
        
        if not features.get('meets_min_credits', 0):
            feedback.append(f"⚠️ You have only {features.get('num_subjects', 0)} subjects. Minimum required: 6 credits")
        
        if not features.get('points_within_limit', 0):
            feedback.append(f"⚠️ Your total points ({features.get('total_points', 0)}) exceed the maximum required: 30 points")
        
        if not features.get('has_credit_english', 0):
            feedback.append("⚠️ English grade needs improvement (credit or better required)")
        
        if not features.get('has_credit_math', 0):
            feedback.append("⚠️ Mathematics grade needs improvement (credit or better required)")
        
        if not features.get('has_credit_science', 0):
            feedback.append("⚠️ Science subject grade needs improvement (credit or better required)")
        
        if features.get('average_grade', 5) <= 3:
            feedback.append("✅ Excellent academic performance!")
        elif features.get('average_grade', 5) <= 4:
            feedback.append("✅ Good academic performance")
        
        return feedback
    
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
    
    def get_model_info(self) -> Dict:
        """Get information about the current model"""
        info = {
            'model_loaded': self.model is not None,
            'model_path': str(self.model_path) if self.model_path.exists() else None,
            'excel_path': self.excel_path,
            'feature_columns': self.feature_columns,
            'excel_exists': self.excel_path and Path(self.excel_path).exists()
        }
        
        if self.model:
            info['model_type'] = type(self.model).__name__
            info['n_features'] = self.model.n_features_in_ if hasattr(self.model, 'n_features_in_') else len(self.feature_columns)
        
        return info


# Singleton instance
msce_predictor = MSCEPredictor()