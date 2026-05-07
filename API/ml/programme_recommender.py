"""
Programme Recommendation System using MSCE Results
Based on Mzuzu University 2026/27 Admission Requirements
"""

import pandas as pd
import numpy as np
import re
from typing import List, Dict, Any, Tuple
from pathlib import Path

class ProgrammeRecommender:
    """Recommends programmes based on MSCE results and ML model"""
    
    def __init__(self, excel_path: str = None):
        self.programmes_df = None
        self.tfidf_matrix = None
        self.vectorizer = None
        self.grade_points = {
            '1': 1, '2': 2, '3': 3, '4': 5, '5': 5,
            '6': 7, '7': 7, '8': 8, '9': 8, 'U': 9
        }
        
        # Define the path to the Excel file
        if excel_path is None:
            # Try to find the Excel file in common locations
            possible_paths = [
                Path(__file__).parent / 'all.xlsx',
                Path(__file__).parent.parent / 'all.xlsx',
                Path(__file__).parent.parent.parent / 'all.xlsx',
                Path('/run/media/lewin/DATA/fourthyear-project/API/API/ml/all.xlsx'),
            ]
            for path in possible_paths:
                if path.exists():
                    excel_path = str(path)
                    break
        
        self.excel_path = excel_path
        self.load_programmes_from_excel()
        
        if self.programmes_df is None or len(self.programmes_df) == 0:
            raise ValueError("No programme data loaded. Please ensure all.xlsx file exists in the API/ml/ directory")
    
    def determine_application_category(self, name: str, duration: str, entry_req: str) -> str:
        """
        Determine which application category this programme belongs to:
        degree, masters, phd, diploma, certificate
        """
        name_lower = name.lower()
        entry_lower = entry_req.lower() if entry_req else ''
        
        # PhD / Doctorate programmes
        if any(word in name_lower for word in ['phd', 'doctorate', 'doctoral', 'dphil']):
            return 'phd'
        
        # Master's programmes
        if any(word in name_lower for word in ['master', 'masters', 'msc', 'ma', 'mba', 'med', 'mcomm']):
            return 'masters'
        
        # Bachelor's degree programmes
        if any(word in name_lower for word in ['bachelor', 'degree', 'bsc', 'ba', 'bcom', 'bed', 'beng', 'generic', 'upgrading']):
            return 'degree'
        
        # Diploma programmes
        if any(word in name_lower for word in ['diploma', 'advanced diploma']):
            return 'diploma'
        
        # Certificate programmes
        if any(word in name_lower for word in ['certificate', 'short course', 'foundation']):
            return 'certificate'
        
        # Check duration for inference
        if duration and 'year' in str(duration).lower():
            dur_str = str(duration).lower()
            if '1' in dur_str and 'year' in dur_str:
                return 'certificate'
            elif '2' in dur_str and 'year' in dur_str:
                return 'diploma'
            elif '3' in dur_str and 'year' in dur_str:
                return 'degree'
            elif '4' in dur_str and 'year' in dur_str:
                return 'degree'
        
        # Default to degree for undergraduate programmes
        return 'degree'
    
    def extract_required_subjects_from_entry_requirements(self, entry_req: str) -> List[str]:
        """Extract required subjects from entry requirements text"""
        if not entry_req or pd.isna(entry_req):
            return []
        
        subjects = []
        entry_req_lower = entry_req.lower()
        
        subject_list = [
            ('English', r'english'),
            ('Mathematics', r'mathematics|math|maths'),
            ('Biology', r'biology'),
            ('Chemistry', r'chemistry'),
            ('Physics', r'physics'),
            ('Physical Science', r'physical science'),
            ('Geography', r'geography'),
            ('History', r'history'),
            ('Chichewa', r'chichewa'),
            ('French', r'french'),
            ('Computer Studies', r'computer studies|computer science|ict'),
            ('Agriculture', r'agriculture'),
            ('Home Economics', r'home economics'),
            ('Commerce', r'commerce'),
            ('Accounts', r'accounts|accounting'),
            ('Bible Knowledge', r'bible knowledge|bible'),
            ('Social Studies', r'social studies|social and development studies'),
            ('Life Skills', r'life skills'),
        ]
        
        for subject, pattern in subject_list:
            if re.search(pattern, entry_req_lower):
                subjects.append(subject)
        
        return subjects
    
    def extract_credits_from_entry_requirements(self, entry_req: str) -> int:
        """Extract required number of credits from entry requirements"""
        if not entry_req or pd.isna(entry_req):
            return 6
        
        entry_req_lower = entry_req.lower()
        
        patterns = [
            r'(\d+)\s*credits',
            r'at least (\d+)\s*credits',
            r'minimum of (\d+)\s*credits',
            r'(\d+)\s*six credits',
            r'with at least (\d+)\s*credits',
            r'contains at least (\d+)\s*credits',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, entry_req_lower)
            if match:
                return int(match.group(1))
        
        return 6
    
    def extract_points_from_entry_requirements(self, entry_req: str) -> int:
        """Extract maximum points allowed from entry requirements"""
        if not entry_req or pd.isna(entry_req):
            return 30
        
        entry_req_lower = entry_req.lower()
        
        patterns = [
            r'not more than (\d+)\s*points',
            r'≤\s*(\d+)\s*points',
            r'less than (\d+)\s*points',
            r'maximum of (\d+)\s*points',
            r'aggregate of (\d+)\s*points',
            r'total points not exceeding (\d+)',
            r'points not exceeding (\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, entry_req_lower)
            if match:
                return int(match.group(1))
        
        if '≤30' in entry_req_lower or '≤ 30' in entry_req_lower:
            return 30
        if 'less than 30' in entry_req_lower:
            return 29
        
        return 30
    
    def determine_programme_type(self, name: str, entry_req: str) -> str:
        """Determine if programme is upgrading or generic"""
        name_lower = name.lower()
        entry_lower = entry_req.lower() if entry_req else ''
        
        if 'upgrading' in name_lower or 'upgrad' in name_lower:
            return 'upgrading'
        elif 't2' in entry_lower or 'teaching certificate' in entry_lower:
            return 'upgrading'
        else:
            return 'generic'
    
    def infer_school_from_name(self, name: str) -> str:
        """Infer the school/faculty from programme name"""
        name_lower = name.lower()
        
        if any(word in name_lower for word in ['education', 'teaching', 'teacher']):
            return 'Faculty of Education'
        elif any(word in name_lower for word in ['nursing', 'health', 'midwifery']):
            return 'Faculty of Health Sciences'
        elif any(word in name_lower for word in ['politics', 'international', 'development', 'theology', 'religious', 'communication', 'library', 'history', 'heritage']):
            return 'Faculty of Humanities and Social Sciences'
        elif any(word in name_lower for word in ['forestry', 'fisheries', 'surveying', 'estate', 'planning', 'water', 'environmental']):
            return 'Faculty of Environmental Sciences'
        elif any(word in name_lower for word in ['renewable', 'energy', 'ict', 'information', 'technology', 'innovation']):
            return 'Faculty of Science, Technology and Innovation'
        elif any(word in name_lower for word in ['tourism', 'hospitality', 'culinary', 'sports']):
            return 'Faculty of Tourism, Hospitality and Management'
        else:
            return 'Faculty of Education'
    
    def load_programmes_from_excel(self):
        """Load programmes from Excel file"""
        if not self.excel_path or not Path(self.excel_path).exists():
            raise FileNotFoundError(f"Excel file not found at {self.excel_path}")
        
        print(f"📊 Loading programmes from Excel: {self.excel_path}")
        
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Programmes')
            print(f"✅ Loaded {len(df)} programmes from Excel")
            
            programmes_data = []
            id_counter = 1
            
            for _, row in df.iterrows():
                name = row.get('Programme', '')
                if pd.isna(name) or name == '':
                    continue
                
                duration = row.get('Duration', '4 Years')
                code = row.get('Programme Code', '')
                entry_req = row.get('Entry Requirements', '')
                quota = row.get('Quota', 0)
                
                if pd.isna(quota) or quota == '':
                    quota = 0
                else:
                    try:
                        quota = int(float(quota))
                    except:
                        quota = 0
                
                if pd.isna(code) or code == '':
                    code = ''
                else:
                    code = str(code).strip()
                
                if pd.isna(duration) or duration == '':
                    duration = '4 Years'
                else:
                    duration = str(duration).strip()
                
                required_subjects = self.extract_required_subjects_from_entry_requirements(entry_req)
                required_credits = self.extract_credits_from_entry_requirements(entry_req)
                min_points = self.extract_points_from_entry_requirements(entry_req)
                programme_type = self.determine_programme_type(name, entry_req)
                application_category = self.determine_application_category(name, duration, entry_req)
                school = self.infer_school_from_name(name)
                
                programmes_data.append({
                    "id": id_counter,
                    "name": str(name),
                    "duration": str(duration),
                    "type": programme_type,
                    "application_category": application_category,
                    "required_credits": required_credits,
                    "subjects": required_subjects,
                    "min_points": min_points,
                    "code": str(code),
                    "quota": quota,
                    "school": school,
                    "entry_requirements": str(entry_req)
                })
                
                id_counter += 1
            
            self.programmes_df = pd.DataFrame(programmes_data)
            
            self.programmes_df['code'] = self.programmes_df['code'].fillna('')
            self.programmes_df['quota'] = self.programmes_df['quota'].fillna(0)
            self.programmes_df['subjects'] = self.programmes_df['subjects'].apply(lambda x: x if isinstance(x, list) else [])
            self.programmes_df['application_category'] = self.programmes_df['application_category'].fillna('degree')
            
            print(f"✅ Processed {len(self.programmes_df)} programmes")
            
            print("\n📊 Programme distribution by application category:")
            category_counts = self.programmes_df['application_category'].value_counts()
            for cat, count in category_counts.items():
                print(f"  {cat.upper()}: {count} programmes")
            
        except Exception as e:
            raise Exception(f"Error loading Excel file: {e}")
    
    def calculate_average_points(self, subjects: List[Dict]) -> float:
        """Calculate average points from subject results"""
        points = [self.grade_points.get(str(s['grade']).upper(), 9) for s in subjects]
        return sum(points) / len(points) if points else 0
    
    def check_subject_requirements(self, programme: Dict, subjects: List[Dict]) -> Tuple[bool, List[str]]:
        """Check if student meets subject requirements"""
        student_subjects = [s['subject'].lower() for s in subjects]
        required = [s.lower() for s in programme.get('subjects', []) if s]
        
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
        _, missing = self.check_subject_requirements(programme, subjects)
        required_count = len(programme.get('subjects', []))
        if required_count > 0:
            matched_count = required_count - len(missing)
            subject_score = (matched_count / required_count) * 40
        else:
            subject_score = 20
        score += subject_score
        
        # Points requirement (35%)
        points_met, total_points = self.check_points_requirement(programme, subjects)
        if points_met:
            points_score = 35
        else:
            needed = programme.get('min_points', 30)
            if needed > 0:
                ratio = max(0, 1 - ((total_points - needed) / needed))
                points_score = ratio * 35
            else:
                points_score = 35
        score += points_score
        
        # Credits count (25%)
        required_credits = programme.get('required_credits', 4)
        student_credits = len(subjects)
        if student_credits >= required_credits:
            credit_score = 25
        else:
            credit_score = (student_credits / required_credits) * 25
        score += credit_score
        
        return min(100, score)
    
    def recommend_programmes(self, subjects: List[Dict], top_n: int = 10, 
                            programme_type: str = 'all', 
                            application_category: str = 'all') -> List[Dict[str, Any]]:
        """
        Recommend programmes based on student's MSCE results
        
        Args:
            subjects: List of dicts with 'subject' and 'grade' keys
            top_n: Number of recommendations to return
            programme_type: 'upgrading', 'generic', or 'all'
            application_category: 'degree', 'masters', 'phd', 'diploma', 'certificate', or 'all'
        
        Returns:
            List of programme recommendations with scores
        """
        if not subjects or self.programmes_df is None or len(self.programmes_df) == 0:
            return []
        
        recommendations = []
        
        for _, programme in self.programmes_df.iterrows():
            # Filter by programme type
            if programme_type != 'all' and programme.get('type') != programme_type:
                continue
            
            # Filter by application category
            if application_category != 'all' and programme.get('application_category') != application_category:
                continue
            
            fit_score = self.get_programme_fit_score(programme.to_dict(), subjects)
            
            subject_met, missing_subjects = self.check_subject_requirements(programme.to_dict(), subjects)
            points_met, total_points = self.check_points_requirement(programme.to_dict(), subjects)
            
            student_credits = len(subjects)
            required_credits = programme.get('required_credits', 4)
            
            if subject_met and points_met and student_credits >= required_credits:
                eligibility = "Eligible"
            elif subject_met and not points_met:
                eligibility = "Points Issue"
            elif not subject_met and points_met:
                eligibility = "Missing Subjects"
            else:
                eligibility = "Not Eligible"
            
            probability = fit_score / 100
            
            recommendations.append({
                "id": int(programme['id']),
                "name": str(programme['name']),
                "code": str(programme.get('code', '')),
                "duration": str(programme.get('duration', 'N/A')),
                "type": str(programme.get('type', 'generic')),
                "application_category": str(programme.get('application_category', 'degree')),
                "fit_score": round(fit_score, 1),
                "admission_probability": round(probability * 100, 1),
                "eligibility": eligibility,
                "required_subjects": programme.get('subjects', []),
                "missing_subjects": missing_subjects,
                "min_points": int(programme.get('min_points', 30)),
                "required_credits": int(programme.get('required_credits', 4)),
                "quota": int(programme.get('quota', 0))
            })
        
        recommendations.sort(key=lambda x: x['fit_score'], reverse=True)
        
        for i, rec in enumerate(recommendations[:top_n]):
            rec['rank'] = i + 1
        
        return recommendations[:top_n]
    
    def get_programmes_by_category(self, application_category: str) -> List[Dict]:
        """Get all programmes for a specific application category"""
        if self.programmes_df is None:
            return []
        
        filtered = self.programmes_df[self.programmes_df['application_category'] == application_category]
        
        programmes = []
        for _, prog in filtered.iterrows():
            programmes.append({
                "id": int(prog['id']),
                "name": str(prog['name']),
                "code": str(prog.get('code', '')),
                "duration": str(prog.get('duration', 'N/A')),
                "type": str(prog.get('type', 'generic')),
                "application_category": str(prog.get('application_category', 'degree')),
                "quota": int(prog.get('quota', 0))
            })
        
        return programmes
    
    def get_all_programmes(self) -> List[Dict]:
        """Get all programmes with basic info"""
        if self.programmes_df is None:
            return []
        
        programmes = []
        for _, prog in self.programmes_df.iterrows():
            programmes.append({
                "id": int(prog['id']),
                "name": str(prog['name']),
                "code": str(prog.get('code', '')),
                "duration": str(prog.get('duration', 'N/A')),
                "type": str(prog.get('type', 'generic')),
                "application_category": str(prog.get('application_category', 'degree')),
                "quota": int(prog.get('quota', 0)),
                "required_credits": int(prog.get('required_credits', 4)),
                "min_points": int(prog.get('min_points', 30))
            })
        
        return programmes
    
    def get_category_statistics(self) -> Dict:
        """Get statistics about programme distribution by category"""
        if self.programmes_df is None:
            return {}
        
        category_counts = self.programmes_df['application_category'].value_counts().to_dict()
        
        return {
            "total_programmes": len(self.programmes_df),
            "by_category": category_counts,
            "categories": {
                "degree": category_counts.get('degree', 0),
                "masters": category_counts.get('masters', 0),
                "phd": category_counts.get('phd', 0),
                "diploma": category_counts.get('diploma', 0),
                "certificate": category_counts.get('certificate', 0)
            }
        }


# Singleton instance
_recommender = None

def get_recommender() -> ProgrammeRecommender:
    global _recommender
    if _recommender is None:
        _recommender = ProgrammeRecommender()
    return _recommender