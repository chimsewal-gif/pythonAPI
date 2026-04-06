from ninja import NinjaAPI, Router, Schema
from ninja.errors import HttpError
from typing import Optional, List
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.conf import settings
import jwt
import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from datetime import datetime, timedelta, timezone
from .models import Applicant, NextOfKin, SubjectRecord, Department, Programme, Application

api = NinjaAPI()
router = Router()

# ==================== SCHEMAS ====================
class DocumentUploadSchema(Schema):
    msce: Optional[str] = None
    msce_size: Optional[int] = None
    msce_name: Optional[str] = None
    id_card: Optional[str] = None
    id_card_size: Optional[int] = None
    id_card_name: Optional[str] = None
    payment_proof: Optional[str] = None
    payment_proof_size: Optional[int] = None
    payment_proof_name: Optional[str] = None

class DocumentResponseSchema(Schema):
    success: bool
    message: str
    data: Optional[DocumentUploadSchema] = None

class SubjectRecordSchema(Schema):
    qualification: str
    centre_number: str
    exam_number: str
    subject: str
    grade: str
    year: str

class ProgrammeSelectionSchema(Schema):
    programme_id: int
    name: str
    department: str
    duration: str
    category: str
    code: Optional[str] = None

class SubjectRecordResponse(Schema):
    id: int
    qualification: str
    centre_number: str
    exam_number: str
    subject: str
    grade: str
    year: str
    created_at: Optional[str] = None

class ApplicantRegistrationSchema(Schema):
    title: str
    firstname: str
    middlename: Optional[str] = None
    lastname: str
    dob: Optional[str] = None
    email: str
    phone: Optional[str] = None
    password: str
    role: str = 'guest'

class LoginSchema(Schema):
    email_or_username: str
    password: str

class UpdateRoleSchema(Schema):
    role: str

class PersonalDetailsSchema(Schema):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    email: str
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    national_id: Optional[str] = None
    home_district: Optional[str] = None
    physical_address: Optional[str] = None

class NextOfKinSchema(Schema):
    title: str
    relationship: str
    first_name: str
    last_name: str
    mobile1: str
    mobile2: Optional[str] = None
    email: Optional[str] = None
    address: str

class AuthResponseSchema(Schema):
    success: bool
    message: str
    user: Optional[dict] = None
    token: Optional[str] = None

class VerifyTokenResponse(Schema):
    success: bool
    message: str
    user: Optional[dict] = None

class DepartmentSchema(Schema):
    name: str
    code: str
    description: Optional[str] = None
    head_of_department: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    established_date: Optional[str] = None
    is_active: bool = True

class ProgrammeSchema(Schema):
    name: str
    description: Optional[str] = None
    department: str
    duration: str
    category: str
    code: Optional[str] = None
    is_active: bool = True

# ==================== JWT HELPER FUNCTIONS ====================

def create_jwt_token(user):
    payload = {
        'user_id': user.id,
        'username': user.username,
        'email': user.email,
        'exp': datetime.now(timezone.utc) + timedelta(days=7),
        'iat': datetime.now(timezone.utc)
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

def decode_jwt_token(token):
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
    except:
        return None

def get_user_from_token(request):
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        raise HttpError(401, "No authorization token provided")
    
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HttpError(401, "Invalid authorization header format")
    
    token = parts[1]
    payload = decode_jwt_token(token)
    if not payload:
        raise HttpError(401, "Invalid or expired token")
    
    try:
        return User.objects.get(id=payload['user_id'])
    except User.DoesNotExist:
        raise HttpError(401, "User not found")

# ==================== AUTH ENDPOINTS ====================

@router.post("/login", response={200: AuthResponseSchema, 401: dict})
@router.post("/login/", response={200: AuthResponseSchema, 401: dict})
def login_user(request, data: LoginSchema):
    try:
        print(f"📝 Login attempt for: {data.email_or_username}")
        
        if '@' in data.email_or_username:
            try:
                user = User.objects.get(email=data.email_or_username)
            except User.DoesNotExist:
                raise HttpError(401, "Invalid credentials")
        else:
            try:
                user = User.objects.get(username=data.email_or_username)
            except User.DoesNotExist:
                raise HttpError(401, "Invalid credentials")
        
        if user.check_password(data.password):
            token = create_jwt_token(user)
            
            try:
                applicant = Applicant.objects.get(user=user)
                role = applicant.program or 'guest'
            except Applicant.DoesNotExist:
                role = 'guest'
            
            return {
                "success": True,
                "message": "Login successful",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "username": user.username,
                    "role": role
                },
                "token": token
            }
        else:
            raise HttpError(401, "Invalid credentials")
            
    except HttpError:
        raise
    except Exception as e:
        print(f"Login error: {str(e)}")
        raise HttpError(500, f"Login failed: {str(e)}")

@router.post("/register", response={201: AuthResponseSchema, 400: dict})
@router.post("/register/", response={201: AuthResponseSchema, 400: dict})
def register_applicant(request, data: ApplicantRegistrationSchema):
    try:
        print(f"Registration attempt for: {data.email}")
        
        if User.objects.filter(email=data.email).exists():
            raise HttpError(400, "Email already registered")
        
        user = User.objects.create_user(
            username=data.email,
            email=data.email,
            password=data.password,
            first_name=data.firstname,
            last_name=data.lastname
        )
        
        applicant = Applicant.objects.create(
            user=user,
            first_name=data.firstname,
            middle_name=data.middlename or "",
            last_name=data.lastname,
            email=data.email,
            phone=data.phone or "",
            date_of_birth=data.dob if data.dob else None,
            program=data.role if data.role != 'guest' else None,
            status='pending'
        )
        
        token = create_jwt_token(user)
        
        return {
            "success": True,
            "message": "Registration successful!",
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "role": data.role
            },
            "token": token
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Registration error: {str(e)}")
        raise HttpError(400, f"Registration failed: {str(e)}")

@router.get("/me", response={200: dict, 401: dict})
@router.get("/me/", response={200: dict, 401: dict})
def get_current_user(request):
    try:
        user = get_user_from_token(request)
        
        try:
            applicant = Applicant.objects.get(user=user)
            role = applicant.program or 'guest'
        except Applicant.DoesNotExist:
            role = 'guest'
        
        return {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "role": role,
            "is_authenticated": True
        }
    except HttpError:
        raise
    except Exception as e:
        print(f"Error getting current user: {str(e)}")
        raise HttpError(401, f"Authentication error: {str(e)}")

@router.post("/logout", response={200: dict})
@router.post("/logout/", response={200: dict})
def logout_user(request):
    return {"success": True, "message": "Logged out successfully"}

@router.post("/update-role", response={200: AuthResponseSchema, 400: dict, 401: dict})
@router.post("/update-role/", response={200: AuthResponseSchema, 400: dict, 401: dict})
def update_user_role(request, data: UpdateRoleSchema):
    try:
        user = get_user_from_token(request)
        role = data.role
        
        valid_roles = ['odl', 'postgraduate', 'diploma', 'international', 'weekend', 'masters']
        if role not in valid_roles:
            return {
                "success": False,
                "message": f"Invalid role. Must be one of: {', '.join(valid_roles)}",
                "user": None
            }
        
        try:
            applicant = Applicant.objects.get(user=user)
            applicant.program = role
            applicant.save()
        except Applicant.DoesNotExist:
            Applicant.objects.create(
                user=user,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
                program=role
            )
        
        return {
            "success": True,
            "message": f"Application type updated to {role} successfully",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": role
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error updating role: {str(e)}")
        return {
            "success": False,
            "message": f"Error updating role: {str(e)}",
            "user": None
        }

# ==================== PERSONAL DETAILS ENDPOINTS ====================

@router.post("/personal-details", response={200: dict, 401: dict})
@router.post("/personal-details/", response={200: dict, 401: dict})
def save_personal_details(request, data: PersonalDetailsSchema):
    try:
        print("=" * 50)
        print("SAVING PERSONAL DETAILS")
        print(f"Received data: {data.dict()}")
        
        user = get_user_from_token(request)
        print(f"User: {user.username} (ID: {user.id})")
        
        user.first_name = data.first_name
        user.last_name = data.last_name
        user.email = data.email
        user.save()
        print("User model updated")
        
        applicant, created = Applicant.objects.get_or_create(user=user)
        print(f"Applicant {'created' if created else 'retrieved'}")
        
        applicant.first_name = data.first_name
        applicant.middle_name = data.middle_name or ""
        applicant.last_name = data.last_name
        applicant.email = data.email
        applicant.phone = data.phone or ""
        
        gender_mapping = {
            'Male': 'M',
            'Female': 'F',
            'Other': 'O',
            'male': 'M',
            'female': 'F',
            'other': 'O'
        }
        
        if data.gender:
            applicant.gender = gender_mapping.get(data.gender, 'O')
        
        if data.date_of_birth:
            applicant.date_of_birth = data.date_of_birth
        
        if data.nationality:
            applicant.nationality = data.nationality
        if data.national_id:
            applicant.national_id = data.national_id
        if data.home_district:
            applicant.home_district = data.home_district
        if data.physical_address:
            applicant.physical_address = data.physical_address
        
        applicant.save()
        print("Applicant profile updated")
        
        gender_reverse = {v: k for k, v in gender_mapping.items()}
        
        return {
            "success": True,
            "message": "Personal details saved successfully",
            "data": {
                "id": applicant.id,
                "first_name": applicant.first_name,
                "middle_name": applicant.middle_name,
                "last_name": applicant.last_name,
                "email": applicant.email,
                "phone": applicant.phone,
                "gender": gender_reverse.get(applicant.gender, 'Other'),
                "date_of_birth": applicant.date_of_birth,
                "nationality": applicant.nationality,
                "national_id": applicant.national_id,
                "home_district": applicant.home_district,
                "physical_address": applicant.physical_address
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }

@router.get("/personal-details", response={200: dict, 401: dict})
@router.get("/personal-details/", response={200: dict, 401: dict})
def get_personal_details(request):
    try:
        user = get_user_from_token(request)
        
        gender_mapping = {
            'M': 'Male',
            'F': 'Female',
            'O': 'Other',
            '': ''
        }
        
        try:
            applicant = Applicant.objects.get(user=user)
            data = {
                "first_name": applicant.first_name,
                "middle_name": applicant.middle_name,
                "last_name": applicant.last_name,
                "email": applicant.email,
                "phone": applicant.phone,
                "gender": gender_mapping.get(applicant.gender, ''),
                "date_of_birth": applicant.date_of_birth,
                "nationality": applicant.nationality,
                "national_id": applicant.national_id,
                "home_district": applicant.home_district,
                "physical_address": applicant.physical_address
            }
        except Applicant.DoesNotExist:
            data = {
                "first_name": user.first_name,
                "middle_name": "",
                "last_name": user.last_name,
                "email": user.email,
                "phone": "",
                "gender": "",
                "date_of_birth": None,
                "nationality": "",
                "national_id": "",
                "home_district": "",
                "physical_address": ""
            }
        
        return {
            "success": True,
            "message": "Personal details retrieved successfully",
            "data": data
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

# ==================== NEXT OF KIN ENDPOINTS ====================

@router.post("/next-of-kin", response={200: dict, 401: dict})
@router.post("/next-of-kin/", response={200: dict, 401: dict})
def save_next_of_kin(request, data: NextOfKinSchema):
    try:
        user = get_user_from_token(request)
        
        next_of_kin = NextOfKin.objects.create(
            user=user,
            title=data.title,
            relationship=data.relationship,
            first_name=data.first_name,
            last_name=data.last_name,
            mobile1=data.mobile1,
            mobile2=data.mobile2,
            email=data.email,
            address=data.address,
        )
        
        return {
            "success": True,
            "message": "Next of kin details saved successfully",
            "data": {
                "id": next_of_kin.id,
                "title": next_of_kin.title,
                "relationship": next_of_kin.relationship,
                "first_name": next_of_kin.first_name,
                "last_name": next_of_kin.last_name,
                "mobile1": next_of_kin.mobile1,
                "mobile2": next_of_kin.mobile2,
                "email": next_of_kin.email,
                "address": next_of_kin.address
            }
        }
    except HttpError:
        raise
    except Exception as e:
        print(f"Error saving next of kin: {str(e)}")
        raise HttpError(500, f"Failed to save: {str(e)}")

@router.get("/next-of-kin", response={200: dict, 401: dict})
@router.get("/next-of-kin/", response={200: dict, 401: dict})
def get_next_of_kin(request):
    try:
        user = get_user_from_token(request)
        next_of_kin_list = NextOfKin.objects.filter(user=user).order_by('-created_at')
        
        data = []
        for kin in next_of_kin_list:
            data.append({
                "id": kin.id,
                "title": kin.title,
                "relationship": kin.relationship,
                "first_name": kin.first_name,
                "last_name": kin.last_name,
                "mobile1": kin.mobile1,
                "mobile2": kin.mobile2,
                "email": kin.email,
                "address": kin.address
            })
        
        return {
            "success": True,
            "message": "Next of kin details retrieved successfully",
            "data": data
        }
    except HttpError:
        raise
    except Exception as e:
        return {
            "success": True,
            "message": "No next of kin details found",
            "data": []
        }

@router.put("/next-of-kin/{kin_id}", response={200: dict, 401: dict, 404: dict})
@router.put("/next-of-kin/{kin_id}/", response={200: dict, 401: dict, 404: dict})
def update_next_of_kin(request, kin_id: int, data: NextOfKinSchema):
    try:
        user = get_user_from_token(request)
        
        try:
            next_of_kin = NextOfKin.objects.get(id=kin_id, user=user)
        except NextOfKin.DoesNotExist:
            raise HttpError(404, "Next of kin not found")
        
        next_of_kin.title = data.title
        next_of_kin.relationship = data.relationship
        next_of_kin.first_name = data.first_name
        next_of_kin.last_name = data.last_name
        next_of_kin.mobile1 = data.mobile1
        next_of_kin.mobile2 = data.mobile2
        next_of_kin.email = data.email
        next_of_kin.address = data.address
        next_of_kin.save()
        
        return {
            "success": True,
            "message": "Next of kin updated successfully",
            "data": {
                "id": next_of_kin.id,
                "title": next_of_kin.title,
                "relationship": next_of_kin.relationship,
                "first_name": next_of_kin.first_name,
                "last_name": next_of_kin.last_name,
                "mobile1": next_of_kin.mobile1,
                "mobile2": next_of_kin.mobile2,
                "email": next_of_kin.email,
                "address": next_of_kin.address
            }
        }
    except HttpError:
        raise
    except Exception as e:
        print(f"Error updating next of kin: {str(e)}")
        raise HttpError(500, f"Failed to update: {str(e)}")

@router.delete("/next-of-kin/{kin_id}", response={200: dict, 401: dict, 404: dict})
@router.delete("/next-of-kin/{kin_id}/", response={200: dict, 401: dict, 404: dict})
def delete_next_of_kin(request, kin_id: int):
    try:
        user = get_user_from_token(request)
        
        try:
            next_of_kin = NextOfKin.objects.get(id=kin_id, user=user)
        except NextOfKin.DoesNotExist:
            raise HttpError(404, "Next of kin not found")
        
        next_of_kin.delete()
        
        return {
            "success": True,
            "message": "Next of kin deleted successfully",
            "data": None
        }
    except HttpError:
        raise
    except Exception as e:
        print(f"Error deleting next of kin: {str(e)}")
        raise HttpError(500, f"Failed to delete: {str(e)}")

# ==================== TEST ENDPOINTS ====================

@router.get("/test", response={200: dict})
@router.get("/test/", response={200: dict})
def test_endpoint(request):
    return {
        "status": "success",
        "message": "API is working!",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.get("/verify-token", response={200: dict, 401: dict})
@router.get("/verify-token/", response={200: dict, 401: dict})
def verify_token(request):
    """Verify if the JWT token is valid"""
    try:
        user = get_user_from_token(request)
        return {
            "valid": True,
            "success": True,
            "message": "Token is valid",
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username
            }
        }
    except HttpError:
        return {
            "valid": False,
            "success": False,
            "message": "Invalid or expired token"
        }
    except Exception as e:
        return {
            "valid": False,
            "success": False,
            "message": f"Error: {str(e)}"
        }

@router.get("/csrf", response={200: dict})
@router.get("/csrf/", response={200: dict})
def get_csrf_token(request):
    """Return CSRF token (simplified for JWT auth)"""
    return {
        "success": True,
        "message": "CSRF token not required for JWT authentication",
        "csrfToken": "not-required-for-jwt"
    }

# ==================== SUBJECT RECORDS ENDPOINTS ====================

@router.get("/subject-records", response={200: dict, 401: dict})
@router.get("/subject-records/", response={200: dict, 401: dict})
def get_subject_records(request):
    """Get all subject records for the authenticated user"""
    try:
        user = get_user_from_token(request)
        records = SubjectRecord.objects.filter(user=user).order_by('-year', 'subject')
        
        data = []
        for record in records:
            data.append({
                "id": record.id,
                "qualification": record.qualification,
                "centre_number": record.centre_number,
                "exam_number": record.exam_number,
                "subject": record.subject,
                "grade": record.grade,
                "year": record.year,
                "created_at": record.created_at.isoformat() if record.created_at else None
            })
        
        return {
            "success": True,
            "message": "Subject records retrieved successfully",
            "data": data,
            "count": len(data)
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching subject records: {str(e)}")
        return {
            "success": True,
            "message": "No subject records found",
            "data": [],
            "count": 0
        }

@router.post("/subject-records", response={200: dict, 401: dict})
@router.post("/subject-records/", response={200: dict, 401: dict})
def create_subject_record(request, data: SubjectRecordSchema):
    """Create a new subject record"""
    try:
        user = get_user_from_token(request)
        
        current_year = datetime.now().year
        year = int(data.year)
        if year < 1950 or year > current_year + 1:
            raise HttpError(400, f"Year must be between 1950 and {current_year + 1}")
        
        record = SubjectRecord.objects.create(
            user=user,
            qualification=data.qualification,
            centre_number=data.centre_number,
            exam_number=data.exam_number,
            subject=data.subject,
            grade=data.grade,
            year=data.year
        )
        
        return {
            "success": True,
            "message": "Subject record created successfully",
            "data": {
                "id": record.id,
                "qualification": record.qualification,
                "centre_number": record.centre_number,
                "exam_number": record.exam_number,
                "subject": record.subject,
                "grade": record.grade,
                "year": record.year
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error creating subject record: {str(e)}")
        raise HttpError(500, f"Failed to create subject record: {str(e)}")

@router.put("/subject-records/{record_id}", response={200: dict, 401: dict, 404: dict})
@router.put("/subject-records/{record_id}/", response={200: dict, 401: dict, 404: dict})
def update_subject_record(request, record_id: int, data: SubjectRecordSchema):
    """Update an existing subject record"""
    try:
        user = get_user_from_token(request)
        
        try:
            record = SubjectRecord.objects.get(id=record_id, user=user)
        except SubjectRecord.DoesNotExist:
            raise HttpError(404, "Subject record not found")
        
        current_year = datetime.now().year
        year = int(data.year)
        if year < 1950 or year > current_year + 1:
            raise HttpError(400, f"Year must be between 1950 and {current_year + 1}")
        
        record.qualification = data.qualification
        record.centre_number = data.centre_number
        record.exam_number = data.exam_number
        record.subject = data.subject
        record.grade = data.grade
        record.year = data.year
        record.save()
        
        return {
            "success": True,
            "message": "Subject record updated successfully",
            "data": {
                "id": record.id,
                "qualification": record.qualification,
                "centre_number": record.centre_number,
                "exam_number": record.exam_number,
                "subject": record.subject,
                "grade": record.grade,
                "year": record.year
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error updating subject record: {str(e)}")
        raise HttpError(500, f"Failed to update subject record: {str(e)}")

@router.delete("/subject-records/{record_id}", response={200: dict, 401: dict, 404: dict})
@router.delete("/subject-records/{record_id}/", response={200: dict, 401: dict, 404: dict})
def delete_subject_record(request, record_id: int):
    """Delete a subject record"""
    try:
        user = get_user_from_token(request)
        
        try:
            record = SubjectRecord.objects.get(id=record_id, user=user)
        except SubjectRecord.DoesNotExist:
            raise HttpError(404, "Subject record not found")
        
        record.delete()
        
        return {
            "success": True,
            "message": "Subject record deleted successfully",
            "data": None
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error deleting subject record: {str(e)}")
        raise HttpError(500, f"Failed to delete subject record: {str(e)}")

# ==================== DEPARTMENT ENDPOINTS ====================

@router.get("/departments", response={200: dict, 401: dict})
@router.get("/departments/", response={200: dict, 401: dict})
def get_departments(request):
    """Get all departments"""
    try:
        user = get_user_from_token(request)
        
        departments_list = Department.objects.all().order_by('name')
        
        data = []
        for dept in departments_list:
            data.append({
                "id": dept.id,
                "name": dept.name,
                "code": dept.code,
                "description": dept.description,
                "head_of_department": dept.head_of_department,
                "email": dept.email,
                "phone": dept.phone,
                "established_date": dept.established_date.isoformat() if dept.established_date else None,
                "is_active": dept.is_active,
                "created_at": dept.created_at.isoformat() if dept.created_at else None,
                "updated_at": dept.updated_at.isoformat() if dept.updated_at else None
            })
        
        return {
            "success": True,
            "message": "Departments retrieved successfully",
            "data": data,
            "count": len(data)
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching departments: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to fetch departments: {str(e)}",
            "data": [],
            "count": 0
        }

@router.get("/departments/{department_id}", response={200: dict, 404: dict, 401: dict})
@router.get("/departments/{department_id}/", response={200: dict, 404: dict, 401: dict})
def get_department(request, department_id: int):
    """Get a single department by ID"""
    try:
        user = get_user_from_token(request)
        
        try:
            dept = Department.objects.get(id=department_id)
        except Department.DoesNotExist:
            raise HttpError(404, "Department not found")
        
        return {
            "success": True,
            "message": "Department retrieved successfully",
            "data": {
                "id": dept.id,
                "name": dept.name,
                "code": dept.code,
                "description": dept.description,
                "head_of_department": dept.head_of_department,
                "email": dept.email,
                "phone": dept.phone,
                "established_date": dept.established_date.isoformat() if dept.established_date else None,
                "is_active": dept.is_active,
                "created_at": dept.created_at.isoformat() if dept.created_at else None,
                "updated_at": dept.updated_at.isoformat() if dept.updated_at else None
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching department: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

@router.post("/departments", response={201: dict, 400: dict, 401: dict})
@router.post("/departments/", response={201: dict, 400: dict, 401: dict})
def create_department(request, data: DepartmentSchema):
    """Create a new department"""
    try:
        user = get_user_from_token(request)
        
        if Department.objects.filter(name=data.name).exists():
            return {
                "success": False,
                "message": f"Department with name '{data.name}' already exists"
            }
        
        if Department.objects.filter(code=data.code).exists():
            return {
                "success": False,
                "message": f"Department with code '{data.code}' already exists"
            }
        
        established_date = None
        if data.established_date:
            try:
                established_date = datetime.strptime(data.established_date, "%Y-%m-%d").date()
            except ValueError:
                return {
                    "success": False,
                    "message": "Invalid date format. Use YYYY-MM-DD"
                }
        
        dept = Department.objects.create(
            name=data.name,
            code=data.code,
            description=data.description or "",
            head_of_department=data.head_of_department or "",
            email=data.email or "",
            phone=data.phone or "",
            established_date=established_date,
            is_active=data.is_active
        )
        
        return {
            "success": True,
            "message": "Department created successfully",
            "data": {
                "id": dept.id,
                "name": dept.name,
                "code": dept.code,
                "description": dept.description,
                "head_of_department": dept.head_of_department,
                "email": dept.email,
                "phone": dept.phone,
                "established_date": dept.established_date.isoformat() if dept.established_date else None,
                "is_active": dept.is_active
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error creating department: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to create department: {str(e)}"
        }

@router.put("/departments/{department_id}", response={200: dict, 400: dict, 404: dict, 401: dict})
@router.put("/departments/{department_id}/", response={200: dict, 400: dict, 404: dict, 401: dict})
def update_department(request, department_id: int, data: DepartmentSchema):
    """Update an existing department"""
    try:
        user = get_user_from_token(request)
        
        try:
            dept = Department.objects.get(id=department_id)
        except Department.DoesNotExist:
            raise HttpError(404, "Department not found")
        
        if Department.objects.filter(name=data.name).exclude(id=department_id).exists():
            return {
                "success": False,
                "message": f"Department with name '{data.name}' already exists"
            }
        
        if Department.objects.filter(code=data.code).exclude(id=department_id).exists():
            return {
                "success": False,
                "message": f"Department with code '{data.code}' already exists"
            }
        
        established_date = None
        if data.established_date:
            try:
                established_date = datetime.strptime(data.established_date, "%Y-%m-%d").date()
            except ValueError:
                return {
                    "success": False,
                    "message": "Invalid date format. Use YYYY-MM-DD"
                }
        
        dept.name = data.name
        dept.code = data.code
        dept.description = data.description or ""
        dept.head_of_department = data.head_of_department or ""
        dept.email = data.email or ""
        dept.phone = data.phone or ""
        dept.established_date = established_date
        dept.is_active = data.is_active
        dept.save()
        
        return {
            "success": True,
            "message": "Department updated successfully",
            "data": {
                "id": dept.id,
                "name": dept.name,
                "code": dept.code,
                "description": dept.description,
                "head_of_department": dept.head_of_department,
                "email": dept.email,
                "phone": dept.phone,
                "established_date": dept.established_date.isoformat() if dept.established_date else None,
                "is_active": dept.is_active
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error updating department: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to update department: {str(e)}"
        }

@router.delete("/departments/{department_id}", response={200: dict, 404: dict, 401: dict})
@router.delete("/departments/{department_id}/", response={200: dict, 404: dict, 401: dict})
def delete_department(request, department_id: int):
    """Delete a department"""
    try:
        user = get_user_from_token(request)
        
        try:
            dept = Department.objects.get(id=department_id)
        except Department.DoesNotExist:
            raise HttpError(404, "Department not found")
        
        if dept.programmes.exists():
            raise HttpError(400, "Cannot delete department with associated programmes. Remove programmes first.")
        
        dept.delete()
        
        return {
            "success": True,
            "message": "Department deleted successfully",
            "data": None
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error deleting department: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to delete department: {str(e)}"
        }

# ==================== PROGRAMME ENDPOINTS ====================

@router.get("/programmes", response={200: dict, 401: dict})
@router.get("/programmes/", response={200: dict, 401: dict})
def get_programmes(request):
    """Get all programmes"""
    try:
        user = get_user_from_token(request)
        
        programmes_list = Programme.objects.all().order_by('name')
        
        data = []
        for prog in programmes_list:
            data.append({
                "id": prog.id,
                "name": prog.name,
                "description": prog.description,
                "department": prog.department.name if prog.department else "Not Assigned",
                "duration": prog.duration,
                "category": prog.category,
                "code": prog.code,
                "is_active": prog.is_active,
                "created_at": prog.created_at.isoformat() if prog.created_at else None,
                "updated_at": prog.updated_at.isoformat() if prog.updated_at else None
            })
        
        return {
            "success": True,
            "message": "Programmes retrieved successfully",
            "data": data,
            "count": len(data)
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching programmes: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to fetch programmes: {str(e)}",
            "data": [],
            "count": 0
        }

@router.get("/programmes/{programme_id}", response={200: dict, 404: dict, 401: dict})
@router.get("/programmes/{programme_id}/", response={200: dict, 404: dict, 401: dict})
def get_programme(request, programme_id: int):
    """Get a single programme by ID"""
    try:
        user = get_user_from_token(request)
        
        try:
            prog = Programme.objects.get(id=programme_id)
        except Programme.DoesNotExist:
            raise HttpError(404, "Programme not found")
        
        return {
            "success": True,
            "message": "Programme retrieved successfully",
            "data": {
                "id": prog.id,
                "name": prog.name,
                "description": prog.description,
                "department": prog.department.name if prog.department else "Not Assigned",
                "department_id": prog.department.id if prog.department else None,
                "duration": prog.duration,
                "category": prog.category,
                "code": prog.code,
                "is_active": prog.is_active,
                "created_at": prog.created_at.isoformat() if prog.created_at else None,
                "updated_at": prog.updated_at.isoformat() if prog.updated_at else None
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching programme: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

@router.post("/programmes", response={201: dict, 400: dict, 401: dict})
@router.post("/programmes/", response={201: dict, 400: dict, 401: dict})
def create_programme(request, data: ProgrammeSchema):
    """Create a new programme"""
    try:
        user = get_user_from_token(request)
        
        print(f"Creating programme with data: {data.dict()}")
        
        try:
            department_obj = Department.objects.get(name=data.department)
        except Department.DoesNotExist:
            return {
                "success": False,
                "message": f"Department '{data.department}' not found. Please create the department first."
            }, 400
        
        if Programme.objects.filter(name=data.name).exists():
            return {
                "success": False,
                "message": f"Programme with name '{data.name}' already exists"
            }, 400
        
        code = data.code
        if not code:
            code = ''.join(word[0].upper() for word in data.name.split() if word)[:10]
        
        original_code = code
        counter = 1
        while Programme.objects.filter(code=code).exists():
            code = f"{original_code}{counter}"
            counter += 1
        
        prog = Programme.objects.create(
            name=data.name,
            description=data.description or "",
            department=department_obj,
            duration=data.duration,
            category=data.category,
            code=code,
            is_active=data.is_active
        )
        
        return 201, {
            "success": True,
            "message": "Programme created successfully",
            "data": {
                "id": prog.id,
                "name": prog.name,
                "description": prog.description,
                "department": prog.department.name,
                "duration": prog.duration,
                "category": prog.category,
                "code": prog.code,
                "is_active": prog.is_active
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error creating programme: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Failed to create programme: {str(e)}"
        }, 500

@router.put("/programmes/{programme_id}", response={200: dict, 400: dict, 404: dict, 401: dict})
@router.put("/programmes/{programme_id}/", response={200: dict, 400: dict, 404: dict, 401: dict})
def update_programme(request, programme_id: int, data: ProgrammeSchema):
    """Update an existing programme"""
    try:
        user = get_user_from_token(request)
        
        try:
            prog = Programme.objects.get(id=programme_id)
        except Programme.DoesNotExist:
            raise HttpError(404, "Programme not found")
        
        try:
            department_obj = Department.objects.get(name=data.department)
        except Department.DoesNotExist:
            return {
                "success": False,
                "message": f"Department '{data.department}' not found"
            }
        
        if Programme.objects.filter(name=data.name).exclude(id=programme_id).exists():
            return {
                "success": False,
                "message": f"Programme with name '{data.name}' already exists"
            }
        
        code = data.code
        if not code:
            code = ''.join(word[0].upper() for word in data.name.split() if word)[:10]
        
        prog.name = data.name
        prog.description = data.description or ""
        prog.department = department_obj
        prog.duration = data.duration
        prog.category = data.category
        prog.code = code
        prog.is_active = data.is_active
        prog.save()
        
        return {
            "success": True,
            "message": "Programme updated successfully",
            "data": {
                "id": prog.id,
                "name": prog.name,
                "description": prog.description,
                "department": prog.department.name,
                "duration": prog.duration,
                "category": prog.category,
                "code": prog.code,
                "is_active": prog.is_active
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error updating programme: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to update programme: {str(e)}"
        }

@router.delete("/programmes/{programme_id}", response={200: dict, 404: dict, 401: dict})
@router.delete("/programmes/{programme_id}/", response={200: dict, 404: dict, 401: dict})
def delete_programme(request, programme_id: int):
    """Delete a programme"""
    try:
        user = get_user_from_token(request)
        
        try:
            prog = Programme.objects.get(id=programme_id)
        except Programme.DoesNotExist:
            raise HttpError(404, "Programme not found")
        
        if hasattr(prog, 'applications') and prog.applications.exists():
            raise HttpError(400, "Cannot delete programme with associated applications. Remove applications first.")
        
        prog.delete()
        
        return {
            "success": True,
            "message": "Programme deleted successfully",
            "data": None
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error deleting programme: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to delete programme: {str(e)}"
        }

# ==================== PROGRAMME SELECTION ENDPOINTS ====================
# IMPORTANT: These MUST come BEFORE the /applicants/{applicant_id} routes

@router.post("/applicants/select-programme", response={200: dict, 400: dict, 401: dict})
@router.post("/applicants/select-programme/", response={200: dict, 400: dict, 401: dict})
def select_programme(request, data: ProgrammeSelectionSchema):
    """Save the selected programme for the applicant"""
    try:
        user = get_user_from_token(request)
        print(f"📝 Saving programme selection for user {user.username}")
        print(f"📊 Programme data: {data.dict()}")
        
        try:
            applicant = Applicant.objects.get(user=user)
        except Applicant.DoesNotExist:
            print(f"⚠️ Applicant profile not found, creating one...")
            applicant = Applicant.objects.create(
                user=user,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
                status='pending'
            )
        
        programme = None
        try:
            programme = Programme.objects.get(id=data.programme_id)
            print(f"✅ Found programme in database: {programme.name}")
        except Programme.DoesNotExist:
            print(f"⚠️ Programme with ID {data.programme_id} not found in database")
        
        if programme:
            applicant.selected_programme = programme
            applicant.selected_programme_name = programme.name
            applicant.selected_programme_id = programme.id
            applicant.selected_programme_department = programme.department.name if programme.department else data.department
            applicant.selected_programme_duration = programme.duration
            applicant.selected_programme_category = programme.category
            applicant.selected_programme_code = programme.code
        else:
            applicant.selected_programme_name = data.name
            applicant.selected_programme_id = data.programme_id
            applicant.selected_programme_department = data.department
            applicant.selected_programme_duration = data.duration
            applicant.selected_programme_category = data.category
            applicant.selected_programme_code = data.code or ""
        
        applicant.save()
        print(f"✅ Programme selection saved successfully")
        
        if programme:
            try:
                application, created = Application.objects.get_or_create(
                    user=user,
                    programme=programme,
                    defaults={'status': 'pending'}
                )
                if created:
                    print(f"✅ Created application record for {programme.name}")
                else:
                    print(f"ℹ️ Application record already exists")
            except Exception as app_error:
                print(f"⚠️ Could not create application record: {app_error}")
        
        return {
            "success": True,
            "message": f"Programme '{data.name}' selected successfully",
            "data": {
                "id": data.programme_id,
                "name": data.name,
                "department": data.department,
                "duration": data.duration,
                "category": data.category,
                "code": data.code
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"❌ Error selecting programme: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Failed to select programme: {str(e)}"
        }, 400

@router.get("/applicants/programme/selection", response={200: dict, 404: dict, 401: dict})
@router.get("/applicants/programme/selection/", response={200: dict, 404: dict, 401: dict})
def get_selected_programme(request):
    """Get the applicant's selected programme"""
    try:
        user = get_user_from_token(request)
        print(f"📝 Fetching selected programme for user {user.username}")
        
        try:
            applicant = Applicant.objects.get(user=user)
        except Applicant.DoesNotExist:
            print(f"⚠️ Applicant profile not found")
            raise HttpError(404, "Applicant profile not found")
        
        if applicant.selected_programme:
            programme_data = {
                "id": applicant.selected_programme.id,
                "name": applicant.selected_programme.name,
                "department": applicant.selected_programme.department.name if applicant.selected_programme.department else "",
                "duration": applicant.selected_programme.duration,
                "category": applicant.selected_programme.category,
                "code": applicant.selected_programme.code
            }
        elif applicant.selected_programme_name:
            programme_data = {
                "id": applicant.selected_programme_id,
                "name": applicant.selected_programme_name,
                "department": applicant.selected_programme_department,
                "duration": applicant.selected_programme_duration,
                "category": applicant.selected_programme_category,
                "code": applicant.selected_programme_code
            }
        else:
            print(f"⚠️ No programme selected for user {user.username}")
            raise HttpError(404, "No programme selected yet")
        
        print(f"✅ Returning selected programme: {programme_data['name']}")
        return {
            "success": True,
            "message": "Selected programme retrieved successfully",
            "data": programme_data
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"❌ Error getting selected programme: {str(e)}")
        raise HttpError(500, f"Failed to get selected programme: {str(e)}")

@router.delete("/applicants/programme/selection", response={200: dict, 401: dict})
@router.delete("/applicants/programme/selection/", response={200: dict, 401: dict})
def clear_selected_programme(request):
    """Clear the applicant's selected programme"""
    try:
        user = get_user_from_token(request)
        
        try:
            applicant = Applicant.objects.get(user=user)
            applicant.selected_programme = None
            applicant.selected_programme_name = None
            applicant.selected_programme_id = None
            applicant.selected_programme_department = None
            applicant.selected_programme_duration = None
            applicant.selected_programme_category = None
            applicant.selected_programme_code = None
            applicant.save()
            
            return {
                "success": True,
                "message": "Programme selection cleared successfully"
            }
        except Applicant.DoesNotExist:
            return {
                "success": True,
                "message": "No programme selection to clear"
            }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error clearing programme selection: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to clear selection: {str(e)}"
        }, 400

# ==================== APPLICANT MANAGEMENT ENDPOINTS ====================
# These parameterized routes come AFTER the specific programme selection routes

@router.get("/applicants", response={200: dict, 401: dict})
@router.get("/applicants/", response={200: dict, 401: dict})
def get_applicants(request):
    """Get all applicants (admin only)"""
    try:
        user = get_user_from_token(request)
        
        users = User.objects.all().order_by('-date_joined')
        
        applicants = []
        for user_obj in users:
            try:
                applicant = Applicant.objects.get(user=user_obj)
                applicants.append({
                    "id": user_obj.id,
                    "firstname": applicant.first_name or user_obj.first_name,
                    "lastname": applicant.last_name or user_obj.last_name,
                    "email": user_obj.email,
                    "phone": applicant.phone or "",
                    "program": applicant.program or "Not specified",
                    "status": applicant.status,
                    "application_date": applicant.application_date.isoformat() if applicant.application_date else user_obj.date_joined.isoformat()
                })
            except Applicant.DoesNotExist:
                applicants.append({
                    "id": user_obj.id,
                    "firstname": user_obj.first_name,
                    "lastname": user_obj.last_name,
                    "email": user_obj.email,
                    "phone": "",
                    "program": "Not specified",
                    "status": "user",
                    "application_date": user_obj.date_joined.isoformat() if user_obj.date_joined else None
                })
        
        return {
            "success": True,
            "message": f"Found {len(applicants)} applicants",
            "data": applicants,
            "count": len(applicants)
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching applicants: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to fetch applicants: {str(e)}",
            "data": [],
            "count": 0
        }

@router.get("/applicants/{applicant_id}", response={200: dict, 404: dict, 401: dict})
@router.get("/applicants/{applicant_id}/", response={200: dict, 404: dict, 401: dict})
def get_applicant(request, applicant_id: int):
    """Get a single applicant by ID"""
    try:
        user = get_user_from_token(request)
        
        try:
            user_obj = User.objects.get(id=applicant_id)
        except User.DoesNotExist:
            raise HttpError(404, "Applicant not found")
        
        try:
            applicant = Applicant.objects.get(user=user_obj)
            data = {
                "id": user_obj.id,
                "firstname": applicant.first_name or user_obj.first_name,
                "lastname": applicant.last_name or user_obj.last_name,
                "email": user_obj.email,
                "phone": applicant.phone or "",
                "program": applicant.program or "Not specified",
                "status": applicant.status,
                "application_date": applicant.application_date.isoformat() if applicant.application_date else user_obj.date_joined.isoformat()
            }
        except Applicant.DoesNotExist:
            data = {
                "id": user_obj.id,
                "firstname": user_obj.first_name,
                "lastname": user_obj.last_name,
                "email": user_obj.email,
                "phone": "",
                "program": "Not specified",
                "status": "user",
                "application_date": user_obj.date_joined.isoformat() if user_obj.date_joined else None
            }
        
        return {
            "success": True,
            "message": "Applicant found",
            "data": data
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching applicant: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

@router.put("/applicants/{applicant_id}", response={200: dict, 404: dict, 401: dict})
@router.put("/applicants/{applicant_id}/", response={200: dict, 404: dict, 401: dict})
def update_applicant_status(request, applicant_id: int, status: str):
    """Update applicant status"""
    try:
        user = get_user_from_token(request)
        
        valid_statuses = ['pending', 'under_review', 'approved', 'rejected']
        if status not in valid_statuses:
            raise HttpError(400, f"Invalid status. Must be one of: {valid_statuses}")
        
        try:
            applicant = Applicant.objects.get(user_id=applicant_id)
            applicant.status = status
            applicant.save()
        except Applicant.DoesNotExist:
            raise HttpError(404, "Applicant profile not found")
        
        return {
            "success": True,
            "message": f"Applicant {applicant_id} status updated to {status}",
            "data": {
                "applicant_id": applicant_id,
                "status": status
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error updating applicant: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }









# ==================== DOCUMENT UPLOAD ENDPOINTS ====================
# ==================== DOCUMENT UPLOAD ENDPOINTS ====================

import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.http import FileResponse, Http404

# Remove the response models from decorators - let them return directly
@router.post("/applicants/{applicant_id}/documents")
@router.post("/applicants/{applicant_id}/documents/")
def upload_documents(request, applicant_id: int):
    """Upload documents for an applicant"""
    try:
        user = get_user_from_token(request)
        
        # Verify the applicant exists and belongs to the user
        try:
            applicant = Applicant.objects.get(id=applicant_id, user=user)
        except Applicant.DoesNotExist:
            raise HttpError(404, "Applicant not found")
        
        # Create documents directory if it doesn't exist
        docs_dir = os.path.join(settings.MEDIA_ROOT, 'documents', str(applicant_id))
        os.makedirs(docs_dir, exist_ok=True)
        
        result = {}
        
        # Handle MSCE certificate upload
        if 'msce' in request.FILES:
            msce_file = request.FILES['msce']
            # Validate file size (max 5MB)
            if msce_file.size > 5 * 1024 * 1024:
                return {
                    "success": False,
                    "message": "MSCE certificate file size must be less than 5MB"
                }, 400
            
            # Generate unique filename
            ext = msce_file.name.split('.')[-1]
            filename = f"msce_{applicant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            filepath = os.path.join('documents', str(applicant_id), filename)
            
            # Save file
            saved_path = default_storage.save(filepath, ContentFile(msce_file.read()))
            
            result['msce'] = saved_path
            result['msce_size'] = msce_file.size
            result['msce_name'] = msce_file.name
        
        # Handle ID card upload
        if 'id_card' in request.FILES:
            id_file = request.FILES['id_card']
            if id_file.size > 5 * 1024 * 1024:
                return {
                    "success": False,
                    "message": "ID card file size must be less than 5MB"
                }, 400
            
            ext = id_file.name.split('.')[-1]
            filename = f"id_card_{applicant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            filepath = os.path.join('documents', str(applicant_id), filename)
            
            saved_path = default_storage.save(filepath, ContentFile(id_file.read()))
            
            result['id_card'] = saved_path
            result['id_card_size'] = id_file.size
            result['id_card_name'] = id_file.name
        
        # Handle payment proof upload
        if 'payment_proof' in request.FILES:
            payment_file = request.FILES['payment_proof']
            if payment_file.size > 5 * 1024 * 1024:
                return {
                    "success": False,
                    "message": "Payment proof file size must be less than 5MB"
                }, 400
            
            ext = payment_file.name.split('.')[-1]
            filename = f"payment_{applicant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            filepath = os.path.join('documents', str(applicant_id), filename)
            
            saved_path = default_storage.save(filepath, ContentFile(payment_file.read()))
            
            result['payment_proof'] = saved_path
            result['payment_proof_size'] = payment_file.size
            result['payment_proof_name'] = payment_file.name
        
        return {
            "success": True,
            "message": "Documents uploaded successfully",
            "data": result
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error uploading documents: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Failed to upload documents: {str(e)}"
        }, 400

@router.get("/applicants/{applicant_id}/documents")
@router.get("/applicants/{applicant_id}/documents/")
def get_documents(request, applicant_id: int):
    """Get all documents for an applicant"""
    try:
        user = get_user_from_token(request)
        
        # Verify the applicant exists and belongs to the user
        try:
            applicant = Applicant.objects.get(id=applicant_id, user=user)
        except Applicant.DoesNotExist:
            return {
                "success": False,
                "message": "Applicant not found"
            }, 404
        
        # Initialize result with None values
        result = {
            "msce": None,
            "msce_size": None,
            "msce_name": None,
            "id_card": None,
            "id_card_size": None,
            "id_card_name": None,
            "payment_proof": None,
            "payment_proof_size": None,
            "payment_proof_name": None
        }
        
        # Check for existing documents in the filesystem
        docs_dir = os.path.join(settings.MEDIA_ROOT, 'documents', str(applicant_id))
        if os.path.exists(docs_dir):
            for filename in os.listdir(docs_dir):
                filepath = os.path.join(docs_dir, filename)
                if os.path.isfile(filepath):
                    file_size = os.path.getsize(filepath)
                    relative_path = os.path.join('documents', str(applicant_id), filename)
                    
                    if filename.startswith('msce_'):
                        result['msce'] = relative_path
                        result['msce_size'] = file_size
                        result['msce_name'] = filename
                    elif filename.startswith('id_card_'):
                        result['id_card'] = relative_path
                        result['id_card_size'] = file_size
                        result['id_card_name'] = filename
                    elif filename.startswith('payment_'):
                        result['payment_proof'] = relative_path
                        result['payment_proof_size'] = file_size
                        result['payment_proof_name'] = filename
        
        return {
            "success": True,
            "message": "Documents retrieved successfully",
            "data": result
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error getting documents: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to get documents: {str(e)}"
        }, 400

@router.get("/applicants/{applicant_id}/documents/{document_type}")
@router.get("/applicants/{applicant_id}/documents/{document_type}/")
def download_document(request, applicant_id: int, document_type: str):
    """Download a specific document"""
    try:
        user = get_user_from_token(request)
        
        # Verify the applicant exists and belongs to the user
        try:
            applicant = Applicant.objects.get(id=applicant_id, user=user)
        except Applicant.DoesNotExist:
            return {
                "success": False,
                "message": "Applicant not found"
            }, 404
        
        # Validate document type
        valid_types = ['msce', 'id_card', 'payment_proof']
        if document_type not in valid_types:
            return {
                "success": False,
                "message": f"Invalid document type. Must be one of: {', '.join(valid_types)}"
            }, 400
        
        # Find the file
        docs_dir = os.path.join(settings.MEDIA_ROOT, 'documents', str(applicant_id))
        if not os.path.exists(docs_dir):
            return {
                "success": False,
                "message": "No documents found"
            }, 404
        
        # Find the file matching the document type
        file_found = None
        for filename in os.listdir(docs_dir):
            if filename.startswith(document_type):
                file_found = filename
                break
        
        if not file_found:
            return {
                "success": False,
                "message": f"{document_type} document not found"
            }, 404
        
        filepath = os.path.join(docs_dir, file_found)
        
        # Return file for download
        try:
            response = FileResponse(open(filepath, 'rb'), as_attachment=True)
            response['Content-Disposition'] = f'attachment; filename="{file_found}"'
            return response
        except FileNotFoundError:
            return {
                "success": False,
                "message": "File not found"
            }, 404
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error downloading document: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to download document: {str(e)}"
        }, 400

@router.delete("/applicants/{applicant_id}/documents/{document_type}")
@router.delete("/applicants/{applicant_id}/documents/{document_type}/")
def delete_document(request, applicant_id: int, document_type: str):
    """Delete a specific document"""
    try:
        user = get_user_from_token(request)
        
        # Verify the applicant exists and belongs to the user
        try:
            applicant = Applicant.objects.get(id=applicant_id, user=user)
        except Applicant.DoesNotExist:
            return {
                "success": False,
                "message": "Applicant not found"
            }, 404
        
        # Validate document type
        valid_types = ['msce', 'id_card', 'payment_proof']
        if document_type not in valid_types:
            return {
                "success": False,
                "message": f"Invalid document type. Must be one of: {', '.join(valid_types)}"
            }, 400
        
        # Find and delete the file
        docs_dir = os.path.join(settings.MEDIA_ROOT, 'documents', str(applicant_id))
        if not os.path.exists(docs_dir):
            return {
                "success": False,
                "message": "No documents found"
            }, 404
        
        file_found = None
        for filename in os.listdir(docs_dir):
            if filename.startswith(document_type):
                file_found = filename
                break
        
        if not file_found:
            return {
                "success": False,
                "message": f"{document_type} document not found"
            }, 404
        
        filepath = os.path.join(docs_dir, file_found)
        os.remove(filepath)
        
        return {
            "success": True,
            "message": f"{document_type} document deleted successfully"
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error deleting document: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to delete document: {str(e)}"
        }, 400


# Add router to API
api.add_router("/", router)