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
    
    # Define valid application categories
    VALID_CATEGORIES = ['degree', 'masters', 'phd', 'diploma', 'certificate']
    
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
                Path(__file__).parent / 'ALL_PROGRAMS_FINAL.xlsx',
                Path(__file__).parent / 'ALL_PROGRAMS_FINAL.csv',
                Path(__file__).parent.parent / 'ALL_PROGRAMS_FINAL.xlsx',
                Path(__file__).parent.parent / 'ALL_PROGRAMS_FINAL.csv',
                Path(__file__).parent.parent.parent / 'ALL_PROGRAMS_FINAL.xlsx',
                Path(__file__).parent.parent.parent / 'ALL_PROGRAMS_FINAL.csv',
                Path('/run/media/lewin/DATA/fourthyear-project/API/API/ml/ALL_PROGRAMS_FINAL.xlsx'),
                Path('/run/media/lewin/DATA/fourthyear-project/API/API/ml/ALL_PROGRAMS_FINAL.csv'),
            ]
            for path in possible_paths:
                if path.exists():
                    excel_path = str(path)
                    break
        
        self.excel_path = excel_path
        self.load_programmes_from_excel()
        
        if self.programmes_df is None or len(self.programmes_df) == 0:
            raise ValueError("No programme data loaded. Please ensure ALL_PROGRAMS_FINAL.xlsx or ALL_PROGRAMS_FINAL.csv file exists in the API/ml/ directory")
    
    def safe_str(self, value: any) -> str:
        """Safely convert any value to string, handling NaN and None"""
        if value is None or pd.isna(value):
            return ''
        return str(value).strip()
    
    def determine_application_category(self, name: str, duration: str, entry_req: str) -> str:
        """
        Determine which application category this programme belongs to:
        degree, masters, phd, diploma, certificate
        """
        name_lower = self.safe_str(name).lower()
        entry_lower = self.safe_str(entry_req).lower()
        
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
        dur_str = self.safe_str(duration).lower()
        if 'year' in dur_str:
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
        entry_req_str = self.safe_str(entry_req)
        if not entry_req_str:
            return []
        
        subjects = []
        entry_req_lower = entry_req_str.lower()
        
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
        entry_req_str = self.safe_str(entry_req)
        if not entry_req_str:
            return 6
        
        entry_req_lower = entry_req_str.lower()
        
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
        entry_req_str = self.safe_str(entry_req)
        if not entry_req_str:
            return 30
        
        entry_req_lower = entry_req_str.lower()
        
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
        name_lower = self.safe_str(name).lower()
        entry_lower = self.safe_str(entry_req).lower()
        
        if 'upgrading' in name_lower or 'upgrad' in name_lower:
            return 'upgrading'
        elif 't2' in entry_lower or 'teaching certificate' in entry_lower:
            return 'upgrading'
        else:
            return 'generic'
    
    def infer_school_from_name(self, name: str) -> str:
        """Infer the school/faculty from programme name"""
        name_lower = self.safe_str(name).lower()
        
        if any(word in name_lower for word in ['education', 'teaching', 'teacher']):
            return 'Faculty of Education'
        elif any(word in name_lower for word in ['nursing', 'health', 'midwifery', 'optometry', 'biomedical']):
            return 'Faculty of Health Sciences'
        elif any(word in name_lower for word in ['politics', 'international', 'development', 'theology', 'religious', 'communication', 'library', 'history', 'heritage', 'security']):
            return 'Faculty of Humanities and Social Sciences'
        elif any(word in name_lower for word in ['forestry', 'fisheries', 'surveying', 'estate', 'planning', 'water', 'environmental', 'value chain', 'transformative']):
            return 'Faculty of Environmental Sciences'
        elif any(word in name_lower for word in ['renewable', 'energy', 'ict', 'information', 'technology', 'innovation', 'data', 'science']):
            return 'Faculty of Science, Technology and Innovation'
        elif any(word in name_lower for word in ['tourism', 'hospitality', 'culinary', 'sports']):
            return 'Faculty of Tourism, Hospitality and Management'
        else:
            return 'Faculty of Education'
    
    def load_programmes_from_excel(self):
        """Load programmes from Excel or CSV file"""
        if not self.excel_path or not Path(self.excel_path).exists():
            raise FileNotFoundError(f"File not found at {self.excel_path}")
        
        print(f"📊 Loading programmes from file: {self.excel_path}")
        
        try:
            # Determine file type and load accordingly
            file_ext = Path(self.excel_path).suffix.lower()
            
            if file_ext == '.csv':
                # Load CSV file
                df = pd.read_csv(self.excel_path)
                print(f"✅ Loaded {len(df)} programmes from CSV")
                print(f"📋 CSV Columns found: {list(df.columns)}")
            else:
                # Try to load Excel file - handle both sheet names
                try:
                    # First try 'Programmes' sheet
                    df = pd.read_excel(self.excel_path, sheet_name='Programmes')
                except ValueError:
                    # If 'Programmes' not found, try the first sheet
                    print("Sheet 'Programmes' not found, using first sheet")
                    xl = pd.ExcelFile(self.excel_path)
                    sheet_name = xl.sheet_names[0]
                    df = pd.read_excel(self.excel_path, sheet_name=sheet_name)
                    print(f"Using sheet: {sheet_name}")
            
            # If df is empty or doesn't have expected columns, try alternative parsing
            if df is None or len(df) == 0:
                raise ValueError("No data found in file")
            
            # Convert all columns to string where needed and handle NaN
            for col in df.columns:
                if df[col].dtype == 'float64':
                    df[col] = df[col].fillna('')
                    df[col] = df[col].astype(str)
                elif df[col].dtype == 'object':
                    df[col] = df[col].fillna('')
            
            # Check if we have the expected columns, if not try to map from your CSV structure
            if 'Programme' not in df.columns and 'Program' not in df.columns:
                # Try to find the programme name column
                possible_name_cols = ['Programme', 'Program', 'name', 'Name', 'PROGRAMME']
                for col in possible_name_cols:
                    if col in df.columns:
                        df.rename(columns={col: 'Programme'}, inplace=True)
                        break
                else:
                    # If no name column found, use the first column
                    first_col = df.columns[0]
                    df.rename(columns={first_col: 'Programme'}, inplace=True)
                    print(f"Using '{first_col}' as Programme column")
            
            # Ensure required columns exist with defaults
            if 'Programme Code' not in df.columns and 'Programme_Code' not in df.columns and 'Code' not in df.columns:
                df['Programme Code'] = ''
            elif 'Programme_Code' in df.columns:
                df.rename(columns={'Programme_Code': 'Programme Code'}, inplace=True)
            elif 'Code' in df.columns:
                df.rename(columns={'Code': 'Programme Code'}, inplace=True)
            
            if 'Duration' not in df.columns:
                df['Duration'] = '4 Years'
            
            if 'Entry Requirements' not in df.columns and 'Entry_Requirements' in df.columns:
                df.rename(columns={'Entry_Requirements': 'Entry Requirements'}, inplace=True)
            elif 'Entry Requirements' not in df.columns:
                df['Entry Requirements'] = ''
            
            if 'Quota' not in df.columns:
                df['Quota'] = 0
            
            print(f"✅ Loaded {len(df)} programmes")
            print(f"📋 Columns found: {list(df.columns)}")
            
            programmes_data = []
            id_counter = 1
            
            for _, row in df.iterrows():
                # Get programme name
                name = row.get('Programme', row.get('Program', ''))
                if pd.isna(name) or name == '' or name == 'nan':
                    continue
                
                duration = row.get('Duration', '4 Years')
                if pd.isna(duration) or duration == 'nan':
                    duration = '4 Years'
                
                code = row.get('Programme Code', row.get('Code', ''))
                if pd.isna(code) or code == 'nan':
                    code = ''
                
                entry_req = row.get('Entry Requirements', row.get('Entry_Requirements', ''))
                if pd.isna(entry_req) or entry_req == 'nan':
                    entry_req = ''
                
                quota = row.get('Quota', 0)
                if pd.isna(quota) or quota == '' or quota == 'nan':
                    quota = 0
                else:
                    try:
                        quota = int(float(quota))
                    except:
                        quota = 0
                
                # Extract requirements - using safe string conversion
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
            
            # Print sample programmes for debugging
            print("\n📋 Sample programmes by category:")
            for category in self.VALID_CATEGORIES:
                cat_progs = self.programmes_df[self.programmes_df['application_category'] == category]
                if len(cat_progs) > 0:
                    print(f"  {category.upper()}: {len(cat_progs)} programmes")
                    sample = cat_progs.iloc[0]
                    print(f"    Example: {sample['name']}")
                else:
                    print(f"  {category.upper()}: 0 programmes")
            
        except Exception as e:
            print(f"Error loading file: {e}")
            import traceback
            traceback.print_exc()
            raise Exception(f"Error loading file: {e}")
    
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
    
    def predict_admission_probability(self, programme_id: int, subjects: List[Dict]) -> Dict:
        """Predict admission probability for a specific programme"""
        programme_row = self.programmes_df[self.programmes_df['id'] == programme_id]
        if len(programme_row) == 0:
            return {"error": f"Programme with ID {programme_id} not found"}
        
        programme = programme_row.iloc[0].to_dict()
        
        fit_score = self.get_programme_fit_score(programme, subjects)
        subject_met, missing_subjects = self.check_subject_requirements(programme, subjects)
        points_met, total_points = self.check_points_requirement(programme, subjects)
        student_credits = len(subjects)
        required_credits = programme.get('required_credits', 4)
        
        return {
            "programme_id": programme_id,
            "programme_name": programme['name'],
            "fit_score": round(fit_score, 1),
            "admission_probability": round(fit_score, 1),
            "subject_requirements_met": subject_met,
            "points_requirement_met": points_met,
            "credits_requirement_met": student_credits >= required_credits,
            "total_points": total_points,
            "missing_subjects": missing_subjects,
            "required_credits": required_credits,
            "student_credits": student_credits
        }
    
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
        
        # Convert application_category to lowercase for case-insensitive matching
        filter_category = application_category.lower() if application_category != 'all' else 'all'
        
        print(f"\n🎯 Filtering programmes for category: '{filter_category}'")
        print(f"📊 Total programmes available: {len(self.programmes_df)}")
        
        # Count how many programmes match the category
        if filter_category != 'all':
            matching_count = len(self.programmes_df[self.programmes_df['application_category'] == filter_category])
            print(f"📋 Programmes with category '{filter_category}': {matching_count}")
        
        for _, programme in self.programmes_df.iterrows():
            prog_category = programme.get('application_category', 'degree')
            
            # Skip if this programme doesn't match the requested category
            if filter_category != 'all' and prog_category != filter_category:
                continue
            
            # Filter by programme type
            if programme_type != 'all' and programme.get('type') != programme_type:
                continue
            
            fit_score = self.get_programme_fit_score(programme.to_dict(), subjects)
            
            # Include all programmes with fit_score > 0 (not just high scores)
            if fit_score > 0:
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
                    "application_category": prog_category,
                    "fit_score": round(fit_score, 1),
                    "admission_probability": round(probability * 100, 1),
                    "eligibility": eligibility,
                    "required_subjects": programme.get('subjects', []),
                    "missing_subjects": missing_subjects,
                    "min_points": int(programme.get('min_points', 30)),
                    "required_credits": int(programme.get('required_credits', 4)),
                    "quota": int(programme.get('quota', 0))
                })
        
        # Sort by fit score (highest first)
        recommendations.sort(key=lambda x: x['fit_score'], reverse=True)
        
        # Limit to top_n (but don't exceed total available)
        result_count = min(top_n, len(recommendations))
        
        for i, rec in enumerate(recommendations[:result_count]):
            rec['rank'] = i + 1
        
        print(f"📈 Found {len(recommendations)} matching programmes for '{filter_category}', returning top {result_count}")
        
        return recommendations[:result_count]
    
    def get_programmes_by_category(self, application_category: str) -> List[Dict]:
        """Get all programmes for a specific application category"""
        if self.programmes_df is None:
            return []
        
        if application_category != 'all' and application_category in self.VALID_CATEGORIES:
            filtered = self.programmes_df[self.programmes_df['application_category'] == application_category]
        else:
            filtered = self.programmes_df
        
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
    
    def get_programmes_by_category_count(self, application_category: str) -> int:
        """Get the count of programmes for a specific application category"""
        if self.programmes_df is None:
            return 0
        
        if application_category != 'all' and application_category in self.VALID_CATEGORIES:
            return len(self.programmes_df[self.programmes_df['application_category'] == application_category])
        
        return len(self.programmes_df)
    
    def get_available_categories(self) -> List[str]:
        """Get list of available application categories with programmes"""
        if self.programmes_df is None:
            return []
        
        return self.programmes_df['application_category'].unique().tolist()


# Singleton instance
_recommender = None

def get_recommender() -> ProgrammeRecommender:
    global _recommender
    if _recommender is None:
        _recommender = ProgrammeRecommender()
    return _recommender