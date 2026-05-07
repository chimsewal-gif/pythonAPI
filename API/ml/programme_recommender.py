"""
Programme Recommendation System using MSCE Results
Based on Mzuzu University 2026/27 Admission Requirements
"""

import pandas as pd
import numpy as np
import pickle
import os
from typing import List, Dict, Any, Tuple

class ProgrammeRecommender:
    """Recommends programmes based on MSCE results and ML model"""
    
    def __init__(self, model_path: str = None):
        self.programmes_df = None
        self.tfidf_matrix = None
        self.vectorizer = None
        self.grade_points = {
            '1': 1, '2': 2, '3': 3, '4': 5, '5': 5,
            '6': 7, '7': 7, '8': 8, '9': 8, 'U': 9
        }
        self.load_programmes_data()
        
    def load_programmes_data(self):
        """Load programmes from CSV data with proper handling of missing values"""
        # Programme data from mzuni_programmes.csv
        programmes_data = [
            # Upgrading Programmes
            {"id": 1, "name": "Bachelor of Education (Arts) - Upgrading (2yr)", "duration": "2 Years", "type": "upgrading", "required_credits": 4, "subjects": ["English"], "min_points": 0, "code": "", "quota": 0},
            {"id": 2, "name": "Bachelor of Education (Arts) - Upgrading (4yr)", "duration": "4 Years", "type": "upgrading", "required_credits": 6, "subjects": ["English"], "min_points": 30, "code": "", "quota": 0},
            {"id": 3, "name": "Bachelor of Education (Languages) - Upgrading (2yr)", "duration": "2 Years", "type": "upgrading", "required_credits": 4, "subjects": ["English", "Chichewa", "French"], "min_points": 0, "code": "", "quota": 0},
            {"id": 4, "name": "Bachelor of Education (Languages) - Upgrading (4yr)", "duration": "4 Years", "type": "upgrading", "required_credits": 6, "subjects": ["English", "Chichewa", "French"], "min_points": 30, "code": "", "quota": 0},
            {"id": 5, "name": "Bachelor of Education (Science) - Upgrading (2yr)", "duration": "2 Years", "type": "upgrading", "required_credits": 4, "subjects": ["English", "Mathematics", "Biology", "Physics", "Chemistry"], "min_points": 0, "code": "", "quota": 0},
            {"id": 6, "name": "Bachelor of Education (Science) - Upgrading (4yr)", "duration": "4 Years", "type": "upgrading", "required_credits": 6, "subjects": ["English", "Mathematics", "Biology", "Physics", "Chemistry"], "min_points": 30, "code": "", "quota": 0},
            {"id": 7, "name": "Bachelor of Education (ICT) - Upgrading", "duration": "4 Years", "type": "upgrading", "required_credits": 6, "subjects": ["English", "Mathematics", "Computer Studies"], "min_points": 30, "code": "", "quota": 0},
            
            # Generic Programmes
            {"id": 20, "name": "Bachelor of Science in Nursing and Midwifery", "duration": "4 Years", "code": "MZU-BSNM", "type": "generic", "required_credits": 6, "subjects": ["English", "Mathematics", "Chemistry", "Physics", "Biology"], "min_points": 30, "quota": 20},
            {"id": 21, "name": "BA Politics and Governance", "duration": "4 Years", "code": "MZU-BPOL", "type": "generic", "required_credits": 6, "subjects": ["English", "Mathematics"], "min_points": 30, "quota": 3},
            {"id": 22, "name": "BA International Relations", "duration": "4 Years", "code": "MZU-BIRD", "type": "generic", "required_credits": 6, "subjects": ["English", "Mathematics"], "min_points": 30, "quota": 3},
            {"id": 23, "name": "BA Development Studies", "duration": "4 Years", "code": "MZU-BDEV", "type": "generic", "required_credits": 6, "subjects": ["English", "Mathematics"], "min_points": 30, "quota": 3},
            {"id": 28, "name": "BSc Renewable Energy Engineering", "duration": "5 Years", "code": "MZUNI-BRESE", "type": "generic", "required_credits": 6, "subjects": ["English", "Mathematics", "Physics", "Chemistry"], "min_points": 30, "quota": 10},
            {"id": 29, "name": "BSc Information and Communication Technology", "duration": "4 Years", "code": "MZUNI-ICT", "type": "generic", "required_credits": 6, "subjects": ["English", "Mathematics"], "min_points": 30, "quota": 8},
            {"id": 30, "name": "BSc Forestry", "duration": "4 Years", "code": "MZU-BScF", "type": "generic", "required_credits": 6, "subjects": ["English", "Biology", "Mathematics"], "min_points": 30, "quota": 30},
            {"id": 31, "name": "BSc Fisheries and Aquatic Sciences", "duration": "4 Years", "code": "MZU-BSFS", "type": "generic", "required_credits": 6, "subjects": ["Biology", "English", "Mathematics"], "min_points": 30, "quota": 10},
            {"id": 32, "name": "BSc Land Surveying", "duration": "4 Years", "code": "MZU-BSLS", "type": "generic", "required_credits": 6, "subjects": ["Mathematics", "Geography", "English", "Physics"], "min_points": 30, "quota": 10},
            {"id": 33, "name": "BSc Estate Management", "duration": "4 Years", "code": "MZU-BSEM", "type": "generic", "required_credits": 6, "subjects": ["English", "Mathematics", "Geography"], "min_points": 30, "quota": 10},
            {"id": 34, "name": "BSc Town and Regional Planning", "duration": "4 Years", "code": "MZU-BSTRP", "type": "generic", "required_credits": 6, "subjects": ["Mathematics", "Geography", "English"], "min_points": 30, "quota": 10},
            {"id": 35, "name": "BSc Water Resources Engineering", "duration": "4 Years", "code": "MZUNI-BSWREM", "type": "generic", "required_credits": 6, "subjects": ["Mathematics", "English", "Physics"], "min_points": 30, "quota": 20},
        ]
        
        self.programmes_df = pd.DataFrame(programmes_data)
        
        # Replace NaN with empty string for code and 0 for quota
        self.programmes_df['code'] = self.programmes_df['code'].fillna('')
        self.programmes_df['quota'] = self.programmes_df['quota'].fillna(0)
        
    def calculate_points(self, grades: List[str]) -> float:
        """Calculate total points from grades"""
        total = 0
        for grade in grades:
            total += self.grade_points.get(str(grade).upper(), 9)
        return total
    
    def calculate_average_points(self, subjects: List[Dict]) -> float:
        """Calculate average points from subject results"""
        points = [self.grade_points.get(str(s['grade']).upper(), 9) for s in subjects]
        return sum(points) / len(points) if points else 0
    
    def check_subject_requirements(self, programme: Dict, subjects: List[Dict]) -> Tuple[bool, List[str]]:
        """Check if student meets subject requirements"""
        student_subjects = [s['subject'].lower() for s in subjects]
        required = [s.lower() for s in programme.get('subjects', [])]
        
        missing = [r for r in required if r not in student_subjects]
        met = len(missing) == 0
        
        return met, missing
    
    def check_points_requirement(self, programme: Dict, subjects: List[Dict]) -> Tuple[bool, float]:
        """Check if student meets points requirement"""
        total_points = sum([self.grade_points.get(str(s['grade']).upper(), 9) for s in subjects])
        required_points = programme.get('min_points', 30)
        required_credits = programme.get('required_credits', 4)
        
        if len(subjects) >= required_credits:
            met = total_points <= required_points if required_points > 0 else True
            return met, total_points
        return False, total_points
    
    def get_programme_fit_score(self, programme: Dict, subjects: List[Dict]) -> float:
        """Calculate fit score (0-100) for a programme"""
        score = 0
        
        # Subject matching (40%)
        subject_met, missing = self.check_subject_requirements(programme, subjects)
        required_count = len(programme.get('subjects', []))
        if required_count > 0:
            matched_count = required_count - len(missing)
            subject_score = (matched_count / required_count) * 40
        else:
            subject_score = 40
        score += subject_score
        
        # Points requirement (30%)
        points_met, total_points = self.check_points_requirement(programme, subjects)
        if points_met:
            points_score = 30
        else:
            # Partial score based on how close to requirement
            needed = programme.get('min_points', 30)
            if needed > 0:
                ratio = max(0, 1 - ((total_points - needed) / needed))
                points_score = ratio * 30
            else:
                points_score = 30
        score += points_score
        
        # Credits count (30%)
        required_credits = programme.get('required_credits', 4)
        student_credits = len(subjects)
        if student_credits >= required_credits:
            credit_score = 30
        else:
            credit_score = (student_credits / required_credits) * 30
        score += credit_score
        
        return min(100, score)
    
    def recommend_programmes(self, subjects: List[Dict], top_n: int = 10, 
                            programme_type: str = 'all') -> List[Dict[str, Any]]:
        """
        Recommend programmes based on student's MSCE results
        
        Args:
            subjects: List of dicts with 'subject' and 'grade' keys
            top_n: Number of recommendations to return
            programme_type: 'upgrading', 'generic', or 'all'
        
        Returns:
            List of programme recommendations with scores
        """
        if not subjects:
            return []
        
        recommendations = []
        
        for _, programme in self.programmes_df.iterrows():
            # Filter by programme type
            if programme_type != 'all' and programme.get('type') != programme_type:
                continue
            
            # Calculate fit score
            fit_score = self.get_programme_fit_score(programme.to_dict(), subjects)
            
            # Check requirements
            subject_met, missing_subjects = self.check_subject_requirements(programme.to_dict(), subjects)
            points_met, total_points = self.check_points_requirement(programme.to_dict(), subjects)
            
            # Eligibility status
            if subject_met and points_met and len(subjects) >= programme.get('required_credits', 4):
                eligibility = "Eligible"
            elif subject_met and not points_met:
                eligibility = "Points Issue"
            elif not subject_met and points_met:
                eligibility = "Missing Subjects"
            else:
                eligibility = "Not Eligible"
            
            # Calculate predicted admission probability
            probability = fit_score / 100
            
            # Safely get values with defaults
            programme_id = int(programme['id'])
            programme_name = str(programme['name'])
            programme_code = str(programme.get('code', '')) if pd.notna(programme.get('code')) else ''
            programme_duration = str(programme.get('duration', 'N/A'))
            programme_type_val = str(programme.get('type', 'generic'))
            required_subjects = programme.get('subjects', [])
            min_points = int(programme.get('min_points', 30)) if pd.notna(programme.get('min_points')) else 30
            required_credits = int(programme.get('required_credits', 4)) if pd.notna(programme.get('required_credits')) else 4
            quota = int(programme.get('quota', 0)) if pd.notna(programme.get('quota')) else 0
            
            recommendations.append({
                "id": programme_id,
                "name": programme_name,
                "code": programme_code,
                "duration": programme_duration,
                "type": programme_type_val,
                "fit_score": round(fit_score, 1),
                "admission_probability": round(probability * 100, 1),
                "eligibility": eligibility,
                "required_subjects": required_subjects,
                "missing_subjects": missing_subjects,
                "min_points": min_points,
                "required_credits": required_credits,
                "quota": quota
            })
        
        # Sort by fit score (descending)
        recommendations.sort(key=lambda x: x['fit_score'], reverse=True)
        
        # Add rank
        for i, rec in enumerate(recommendations[:top_n]):
            rec['rank'] = i + 1
        
        return recommendations[:top_n]
    
    def predict_admission_probability(self, programme_id: int, subjects: List[Dict]) -> Dict:
        """Predict admission probability for a specific programme"""
        programme = self.programmes_df[self.programmes_df['id'] == programme_id]
        if programme.empty:
            return {"error": "Programme not found"}
        
        programme = programme.iloc[0].to_dict()
        fit_score = self.get_programme_fit_score(programme, subjects)
        probability = fit_score / 100
        
        subject_met, missing = self.check_subject_requirements(programme, subjects)
        points_met, total_points = self.check_points_requirement(programme, subjects)
        
        return {
            "programme_id": programme_id,
            "programme_name": programme['name'],
            "fit_score": round(fit_score, 1),
            "admission_probability": round(probability * 100, 1),
            "meets_subject_requirements": subject_met,
            "meets_points_requirements": points_met,
            "missing_subjects": missing,
            "total_points": total_points,
            "min_points_required": programme.get('min_points', 30),
            "subjects_count": len(subjects),
            "required_subjects_count": programme.get('required_credits', 4)
        }


# Singleton instance
_recommender = None

def get_recommender() -> ProgrammeRecommender:
    global _recommender
    if _recommender is None:
        _recommender = ProgrammeRecommender()
    return _recommender