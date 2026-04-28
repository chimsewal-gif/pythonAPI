from ninja import NinjaAPI, Router, Schema
from ninja.errors import HttpError
from typing import Optional, List
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.conf import settings
import jwt
from typing import Optional, List
import os
import json
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .ml.endpoints import ml_router

from django.http import FileResponse

from datetime import datetime, timedelta, timezone
from .models import (
    Applicant, 
    NextOfKin, 
    SubjectRecord, 
    Department, 
    Programme, 
    Application, 
    FeePayment, 
    FeeStatus, 
    CommitteeMember, 
    Notification, 
    ProgrammeChoice,
    TeachingSubject
)

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

        
@router.post("/register", response={201: AuthResponseSchema, 200: AuthResponseSchema, 400: dict})
@router.post("/register/", response={201: AuthResponseSchema, 200: AuthResponseSchema, 400: dict})
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
        return {"success": False, "message": f"Registration failed: {str(e)}"}



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


# Add this schema class with your other schemas
class UserUpdateSchema(Schema):
    first_name: str
    last_name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[str] = None

# Add this endpoint after your GET /me endpoint
@router.put("/me", response={200: dict, 400: dict, 401: dict})
@router.put("/me/", response={200: dict, 400: dict, 401: dict})
def update_current_user(request, data: UserUpdateSchema):
    """Update current user's profile information"""
    try:
        user = get_user_from_token(request)
        print(f"📝 Updating user profile for {user.username}")
        print(f"Received data: {data.dict()}")
        
        # Update User model fields
        user.first_name = data.first_name
        user.last_name = data.last_name
        user.save()
        
        # Update or create Applicant profile
        try:
            applicant = Applicant.objects.get(user=user)
        except Applicant.DoesNotExist:
            applicant = Applicant.objects.create(
                user=user,
                first_name=data.first_name,
                last_name=data.last_name,
                email=user.email,
                status='pending'
            )
        
        # Update Applicant fields
        applicant.first_name = data.first_name
        applicant.last_name = data.last_name
        applicant.phone = data.phone or ""
        
        if data.address:
            applicant.physical_address = data.address
        
        if data.date_of_birth:
            applicant.date_of_birth = data.date_of_birth
        
        applicant.save()
        
        # Log the activity
        from .models import UserActivityLog, AuditLog
        UserActivityLog.objects.create(
            user=user,
            action="profile_updated",
            details="User profile information updated",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        AuditLog.objects.create(
            user=user,
            action="profile_update",
            resource_type="User",
            resource_id=user.id,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Get the updated role
        try:
            role = applicant.program or 'guest'
        except:
            role = 'guest'
        
        return {
            "success": True,
            "message": "Profile updated successfully",
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "role": role,
                "phone": applicant.phone,
                "address": applicant.physical_address,
                "date_of_birth": applicant.date_of_birth
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error updating user: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Failed to update profile: {str(e)}"
        }


        

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
                "description": prog.description or "",
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
                "description": prog.description or "",
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

@router.post("/programmes")
@router.post("/programmes/")
def create_programme(request, data: ProgrammeSchema):
    """Create a new programme"""
    try:
        user = get_user_from_token(request)
        
        print(f"📝 Creating programme: {data.name}")
        print(f"   Department: {data.department}")
        print(f"   Category: {data.category}")
        print(f"   Duration: {data.duration}")
        
        # Get or create department
        department_obj, created = Department.objects.get_or_create(
            name=data.department,
            defaults={
                'code': data.department[:10].upper().replace(' ', ''),
                'description': f"Department of {data.department}",
                'is_active': True
            }
        )
        
        if created:
            print(f"✅ Created new department: {department_obj.name}")
        
        # Check if programme with same name exists
        if Programme.objects.filter(name=data.name).exists():
            return {
                "success": False,
                "message": f"Programme with name '{data.name}' already exists"
            }
        
        # Generate code if not provided
        code = data.code
        if not code or code == "":
            words = data.name.split()
            code = ''.join(word[0].upper() for word in words if word)[:10]
        
        # Ensure unique code
        original_code = code
        counter = 1
        while Programme.objects.filter(code=code).exists():
            code = f"{original_code}{counter}"
            counter += 1
        
        # Create the programme
        prog = Programme.objects.create(
            name=data.name,
            description=data.description or "",
            department=department_obj,
            duration=data.duration,
            category=data.category,
            code=code,
            is_active=data.is_active
        )
        
        print(f"✅ Programme created: {prog.name} (ID: {prog.id})")
        
        # Return the created programme
        return {
            "id": prog.id,
            "name": prog.name,
            "description": prog.description,
            "department": prog.department.name,
            "duration": prog.duration,
            "category": prog.category,
            "code": prog.code,
            "is_active": prog.is_active
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"❌ Error creating programme: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to create programme: {str(e)}"
        }

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
        }

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
        }

# ==================== PROGRAMME CHOICES ENDPOINTS ====================

class ProgrammeChoiceItemSchema(Schema):
    choice_number: int
    programme_id: int
    programme_name: str
    department: str
    duration: str
    category: str

class ProgrammeChoicesSaveSchema(Schema):
    choices: List[ProgrammeChoiceItemSchema]

@router.post("/applicants/programme-choices", response={200: dict, 400: dict, 401: dict})
def save_programme_choices(request, data: ProgrammeChoicesSaveSchema):
    """Save multiple programme choices for the applicant"""
    try:
        user = get_user_from_token(request)
        print(f"📝 Saving programme choices for user {user.username}")
        print(f"📊 Received {len(data.choices)} choices")
        
        # Validate that we have exactly 6 choices
        if len(data.choices) != 6:
            return {
                "success": False,
                "message": f"You must select exactly 6 programmes. You selected {len(data.choices)}"
            }
        
        # Validate no duplicate programme IDs
        programme_ids = [choice.programme_id for choice in data.choices]
        if len(programme_ids) != len(set(programme_ids)):
            return {
                "success": False,
                "message": "Duplicate programmes detected. Please select 6 different programmes."
            }
        
        # Delete existing choices
        ProgrammeChoice.objects.filter(user=user).delete()
        print(f"🗑️ Deleted existing choices")
        
        # Create new choices
        created_choices = []
        for choice_data in data.choices:
            try:
                programme = Programme.objects.get(id=choice_data.programme_id)
                programme_name = programme.name
                department = programme.department.name if programme.department else choice_data.department
                duration = programme.duration or choice_data.duration
                category = programme.category or choice_data.category
            except Programme.DoesNotExist:
                programme_name = choice_data.programme_name
                department = choice_data.department
                duration = choice_data.duration
                category = choice_data.category
            
            choice = ProgrammeChoice.objects.create(
                user=user,
                choice_number=choice_data.choice_number,
                programme_id=choice_data.programme_id,
                programme_name=programme_name,
                department=department,
                duration=duration,
                category=category
            )
            created_choices.append({
                "id": choice.id,
                "choice_number": choice.choice_number,
                "programme_id": choice.programme_id,
                "programme_name": choice.programme_name,
                "department": choice.department,
                "duration": choice.duration,
                "category": choice.category
            })
        
        print(f"✅ Created {len(created_choices)} new programme choices")
        
        return {
            "success": True,
            "message": f"{len(created_choices)} programme choices saved successfully",
            "choices": created_choices
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"❌ Error saving programme choices: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Failed to save: {str(e)}"
        }

@router.get("/applicants/programme-choices", response={200: dict, 401: dict})
def get_programme_choices(request):
    """Get the applicant's saved programme choices"""
    try:
        user = get_user_from_token(request)
        print(f"📝 Fetching programme choices for user {user.username}")
        
        choices = ProgrammeChoice.objects.filter(user=user).order_by('choice_number')
        
        choices_data = []
        for choice in choices:
            choices_data.append({
                "id": choice.id,
                "choice_number": choice.choice_number,
                "programme_id": choice.programme_id,
                "programme_name": choice.programme_name,
                "department": choice.department,
                "duration": choice.duration,
                "category": choice.category
            })
        
        print(f"✅ Found {len(choices_data)} programme choices")
        
        return {
            "success": True,
            "message": "Programme choices retrieved successfully",
            "choices": choices_data
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"❌ Error fetching programme choices: {str(e)}")
        return {
            "success": False,
            "message": str(e),
            "choices": []
        }

# ==================== APPLICANT SUBMISSIONS ENDPOINTS ====================
@router.get("/applicant-submissions", response={200: dict})
@router.get("/applicant-submissions/", response={200: dict})
def get_applicant_submissions(request):
    """Get all applicant submissions for admin with ML data from database"""
    try:
        user = get_user_from_token(request)
        
        print(f"📋 Fetching applicant submissions for user {user.username}")
        
        applicants = Applicant.objects.all().order_by('-application_date')
        
        submissions = []
        for applicant in applicants:
            user_obj = applicant.user
            
            programme_name = applicant.selected_programme_name
            if not programme_name and applicant.selected_programme:
                programme_name = applicant.selected_programme.name
            if not programme_name:
                programme_name = applicant.program or "Not specified"
            
            reference_number = applicant.reference_number or f"APP-{applicant.id:06d}-{applicant.application_date.strftime('%Y') if applicant.application_date else '2024'}"
            
            # Build ML prediction data from database
            ml_prediction = None
            if applicant.ml_decision:
                ml_prediction = {
                    "decision": applicant.ml_decision,
                    "confidence": float(applicant.ml_confidence) if applicant.ml_confidence else 0,
                    "probability": float(applicant.ml_probability) if applicant.ml_probability else 0,
                    "priority_level": applicant.ml_priority,
                    "factors": applicant.ml_factors or {},
                    "recommendation": applicant.ml_recommendation,
                    "processed_at": applicant.ml_processed_at.isoformat() if applicant.ml_processed_at else None
                }
            
            submissions.append({
                "id": applicant.id,
                "applicant_name": f"{applicant.first_name} {applicant.last_name}".strip() or user_obj.username,
                "programme": programme_name,
                "reference_number": reference_number,
                "status": applicant.status or "pending",
                "submitted_at": applicant.application_date.isoformat() if applicant.application_date else user_obj.date_joined.isoformat(),
                "email": applicant.email or user_obj.email,
                "phone": applicant.phone or "",
                "ml_prediction": ml_prediction,
                "auto_processed": applicant.status in ['approved', 'rejected'] and applicant.ml_decision is not None,
                "last_analyzed_at": applicant.ml_processed_at.isoformat() if applicant.ml_processed_at else None,
                "priority_level": applicant.ml_priority,
                "eligibility_verified": applicant.status in ['approved', 'under_review', 'reviewed'],
                "documents_valid": bool(applicant.msce and applicant.id_card and applicant.payment_proof)
            })
        
        return {
            "success": True,
            "message": f"Found {len(submissions)} submissions",
            "data": submissions,
            "count": len(submissions)
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching submissions: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Failed to fetch submissions: {str(e)}",
            "data": [],
            "count": 0
        }

@router.get("/applicant-submissions/{submission_id}", response={200: dict})
@router.get("/applicant-submissions/{submission_id}/", response={200: dict})
def get_applicant_submission(request, submission_id: int):
    """Get a single applicant submission by ID with ML data from database"""
    try:
        user = get_user_from_token(request)
        
        try:
            applicant = Applicant.objects.get(id=submission_id)
        except Applicant.DoesNotExist:
            return {
                "success": False,
                "message": "Submission not found"
            }
        
        user_obj = applicant.user
        
        programme_name = applicant.selected_programme_name
        if not programme_name and applicant.selected_programme:
            programme_name = applicant.selected_programme.name
        if not programme_name:
            programme_name = applicant.program or "Not specified"
        
        reference_number = applicant.reference_number or f"APP-{applicant.id:06d}-{applicant.application_date.strftime('%Y') if applicant.application_date else '2024'}"
        
        # Build ML prediction from database
        ml_prediction = None
        if applicant.ml_decision:
            ml_prediction = {
                "decision": applicant.ml_decision,
                "confidence": float(applicant.ml_confidence) if applicant.ml_confidence else 0,
                "probability": float(applicant.ml_probability) if applicant.ml_probability else 0,
                "priority_level": applicant.ml_priority,
                "factors": applicant.ml_factors or {},
                "recommendation": applicant.ml_recommendation,
                "processed_at": applicant.ml_processed_at.isoformat() if applicant.ml_processed_at else None
            }
        
        next_of_kin_list = []
        for kin in NextOfKin.objects.filter(user=user_obj):
            next_of_kin_list.append({
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
        
        subject_records = []
        for record in SubjectRecord.objects.filter(user=user_obj):
            subject_records.append({
                "id": record.id,
                "qualification": record.qualification,
                "centre_number": record.centre_number,
                "exam_number": record.exam_number,
                "subject": record.subject,
                "grade": record.grade,
                "year": record.year
            })
        
        submission_data = {
            "id": applicant.id,
            "applicant_name": f"{applicant.first_name} {applicant.last_name}".strip() or user_obj.username,
            "programme": programme_name,
            "reference_number": reference_number,
            "status": applicant.status or "pending",
            "submitted_at": applicant.application_date.isoformat() if applicant.application_date else user_obj.date_joined.isoformat(),
            "email": applicant.email or user_obj.email,
            "phone": applicant.phone or "",
            "first_name": applicant.first_name,
            "last_name": applicant.last_name,
            "middle_name": applicant.middle_name,
            "date_of_birth": applicant.date_of_birth,
            "gender": applicant.gender,
            "nationality": applicant.nationality,
            "national_id": applicant.national_id,
            "home_district": applicant.home_district,
            "physical_address": applicant.physical_address,
            "next_of_kin": next_of_kin_list,
            "subject_records": subject_records,
            "ml_prediction": ml_prediction,
            "last_analyzed_at": applicant.ml_processed_at.isoformat() if applicant.ml_processed_at else None,
            "priority_level": applicant.ml_priority
        }
        
        return {
            "success": True,
            "message": "Submission found",
            "data": submission_data
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching submission: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

# ==================== TEACHING SUBJECTS SCHEMAS ====================
class TeachingSubjectSchema(Schema):
    id: Optional[int] = None
    subject_name: str
    subject_code: str
    teaching_level: str  # 'junior', 'senior', 'both'
    is_major: bool = False

class TeachingSubjectsSaveSchema(Schema):
    subjects: List[TeachingSubjectSchema]

# ==================== TEACHING SUBJECTS ENDPOINTS ====================
@router.get("/teaching-subjects", response={200: dict, 401: dict})
@router.get("/teaching-subjects/", response={200: dict, 401: dict})
def get_teaching_subjects(request):
    """Get all teaching subjects for the authenticated user"""
    try:
        user = get_user_from_token(request)
        
        from .models import TeachingSubject
        
        subjects = TeachingSubject.objects.filter(user=user).order_by('subject_name')
        
        data = []
        for subject in subjects:
            data.append({
                "id": subject.id,
                "subject_name": subject.subject_name,
                "subject_code": subject.subject_code,
                "teaching_level": subject.teaching_level,
                "is_major": subject.is_major
            })
        
        return {
            "success": True,
            "message": "Teaching subjects retrieved successfully",
            "data": data,
            "count": len(data)
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching teaching subjects: {str(e)}")
        return {
            "success": True,
            "message": "No teaching subjects found",
            "data": [],
            "count": 0
        }


@router.post("/teaching-subjects", response={200: dict, 401: dict})
@router.post("/teaching-subjects/", response={200: dict, 401: dict})
def save_teaching_subjects(request, data: TeachingSubjectsSaveSchema):
    """Save all teaching subjects for the authenticated user"""
    try:
        user = get_user_from_token(request)
        
        from .models import TeachingSubject
        
        # Delete existing subjects for this user
        TeachingSubject.objects.filter(user=user).delete()
        
        # Create new subjects
        created_subjects = []
        for subject_data in data.subjects:
            teaching_subject = TeachingSubject.objects.create(
                user=user,
                subject_name=subject_data.subject_name,
                subject_code=subject_data.subject_code,
                teaching_level=subject_data.teaching_level,
                is_major=subject_data.is_major
            )
            created_subjects.append({
                "id": teaching_subject.id,
                "subject_name": teaching_subject.subject_name,
                "subject_code": teaching_subject.subject_code,
                "teaching_level": teaching_subject.teaching_level,
                "is_major": teaching_subject.is_major
            })
        
        return {
            "success": True,
            "message": f"Saved {len(created_subjects)} teaching subjects",
            "data": created_subjects
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error saving teaching subjects: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to save teaching subjects: {str(e)}"
        }


@router.delete("/teaching-subjects/{subject_id}", response={200: dict, 401: dict, 404: dict})
@router.delete("/teaching-subjects/{subject_id}/", response={200: dict, 401: dict, 404: dict})
def delete_teaching_subject(request, subject_id: int):
    """Delete a specific teaching subject"""
    try:
        user = get_user_from_token(request)
        
        from .models import TeachingSubject
        
        try:
            subject = TeachingSubject.objects.get(id=subject_id, user=user)
        except TeachingSubject.DoesNotExist:
            return {
                "success": False,
                "message": "Teaching subject not found"
            }
        
        subject.delete()
        
        return {
            "success": True,
            "message": "Teaching subject deleted successfully"
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error deleting teaching subject: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to delete teaching subject: {str(e)}"
        }    



@router.patch("/applicant-submissions/{submission_id}/status")
@router.patch("/applicant-submissions/{submission_id}/status/")
def update_submission_status(request, submission_id: int):
    """Update the status of an applicant submission"""
    try:
        user = get_user_from_token(request)
        
        body = json.loads(request.body)
        new_status = body.get('status')
        
        if not new_status:
            return {
                "success": False,
                "message": "Status is required"
            }
        
        valid_statuses = ['submitted', 'pending', 'under_review', 'reviewed', 'accepted', 'approved', 'rejected']
        if new_status not in valid_statuses:
            return {
                "success": False,
                "message": f"Invalid status. Must be one of: {valid_statuses}"
            }
        
        try:
            applicant = Applicant.objects.get(id=submission_id)
        except Applicant.DoesNotExist:
            return {
                "success": False,
                "message": "Submission not found"
            }
        
        applicant.status = new_status
        applicant.save()
        
        return {
            "success": True,
            "message": f"Status updated to {new_status}",
            "data": {
                "id": applicant.id,
                "status": applicant.status
            }
        }
        
    except Exception as e:
        print(f"Error updating status: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }



@router.patch("/applicant-submissions/{submission_id}/ml-prediction")
@router.patch("/applicant-submissions/{submission_id}/ml-prediction/")
def update_ml_prediction(request, submission_id: int):
    """Update ML prediction for an applicant submission and save to database"""
    try:
        user = get_user_from_token(request)
        
        body = json.loads(request.body) if request.body else {}
        ml_prediction = body.get('ml_prediction')
        last_analyzed_at = body.get('last_analyzed_at')
        
        print(f"📊 Received ML prediction for submission {submission_id}")
        print(f"ML Prediction data: {ml_prediction}")
        
        if not ml_prediction:
            return {
                "success": False,
                "message": "ML prediction data is required"
            }
        
        try:
            applicant = Applicant.objects.get(id=submission_id)
        except Applicant.DoesNotExist:
            return {
                "success": False,
                "message": "Submission not found"
            }
        
        # ==== STORE ML PREDICTION IN DATABASE ====
        applicant.ml_decision = ml_prediction.get('decision')
        applicant.ml_confidence = ml_prediction.get('confidence')
        applicant.ml_probability = ml_prediction.get('probability', ml_prediction.get('confidence'))
        
        # Calculate priority level based on decision and confidence
        if ml_prediction.get('decision') == 'approve':
            if ml_prediction.get('confidence', 0) > 0.7:
                applicant.ml_priority = 'High'
            else:
                applicant.ml_priority = 'Medium'
        elif ml_prediction.get('decision') == 'reject':
            applicant.ml_priority = 'Low'
        else:
            applicant.ml_priority = 'Medium'
        
        # Store factors and recommendation
        applicant.ml_factors = {
            'reasons': ml_prediction.get('reasons', []),
            'risk_factors': ml_prediction.get('risk_factors', [])
        }
        applicant.ml_recommendation = ml_prediction.get('recommendation', '')
        applicant.ml_processed_at = datetime.now()
        applicant.ml_raw_response = ml_prediction
        applicant.save()
        # =======================================
        
        print(f"✅ ML Prediction saved to database for {applicant.first_name} {applicant.last_name}:")
        print(f"   Decision: {applicant.ml_decision}")
        print(f"   Confidence: {applicant.ml_confidence}")
        print(f"   Priority: {applicant.ml_priority}")
        
        return {
            "success": True,
            "message": "ML prediction saved successfully",
            "data": {
                "id": applicant.id,
                "ml_prediction": {
                    "decision": applicant.ml_decision,
                    "confidence": applicant.ml_confidence,
                    "probability": applicant.ml_probability,
                    "priority_level": applicant.ml_priority,
                    "factors": applicant.ml_factors,
                    "recommendation": applicant.ml_recommendation,
                    "processed_at": applicant.ml_processed_at.isoformat() if applicant.ml_processed_at else None
                }
            }
        }
        
    except Exception as e:
        print(f"Error saving ML prediction: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Failed to save ML prediction: {str(e)}"
        }




# ==================== APPLICANT MANAGEMENT ENDPOINTS ====================

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

# ==================== DOCUMENT UPLOAD ENDPOINTS ====================
# In your API views.py or api.py - Make sure this endpoint properly saves files

@router.post("/applicants/{applicant_id}/documents")
@router.post("/applicants/{applicant_id}/documents/")
def upload_documents(request, applicant_id: int):
    """Upload documents for an applicant and store references in database"""
    try:
        user = get_user_from_token(request)
        
        try:
            applicant = Applicant.objects.get(id=applicant_id, user=user)
        except Applicant.DoesNotExist:
            return {"success": False, "message": "Applicant not found"}, 404
        
        docs_dir = os.path.join(settings.MEDIA_ROOT, 'documents', str(applicant_id))
        os.makedirs(docs_dir, exist_ok=True)
        
        result = {}
        
        # Handle MSCE certificate upload
        if 'msce' in request.FILES:
            msce_file = request.FILES['msce']
            if msce_file.size > 5 * 1024 * 1024:
                return {"success": False, "message": "File size must be less than 5MB"}, 400
            
            # Delete old file if exists
            if applicant.msce:
                old_path = os.path.join(settings.MEDIA_ROOT, applicant.msce)
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            ext = msce_file.name.split('.')[-1]
            filename = f"msce_{applicant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            filepath = os.path.join('documents', str(applicant_id), filename)
            saved_path = default_storage.save(filepath, ContentFile(msce_file.read()))
            
            # Save to database immediately
            applicant.msce = saved_path
            applicant.msce_size = msce_file.size
            applicant.msce_name = msce_file.name
            applicant.save()  # IMPORTANT: Save to database
            
            result['msce'] = saved_path
            result['msce_size'] = msce_file.size
            result['msce_name'] = msce_file.name
        
        # Handle ID Card upload
        if 'id_card' in request.FILES:
            id_file = request.FILES['id_card']
            if id_file.size > 5 * 1024 * 1024:
                return {"success": False, "message": "File size must be less than 5MB"}, 400
            
            if applicant.id_card:
                old_path = os.path.join(settings.MEDIA_ROOT, applicant.id_card)
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            ext = id_file.name.split('.')[-1]
            filename = f"id_card_{applicant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            filepath = os.path.join('documents', str(applicant_id), filename)
            saved_path = default_storage.save(filepath, ContentFile(id_file.read()))
            
            applicant.id_card = saved_path
            applicant.id_card_size = id_file.size
            applicant.id_card_name = id_file.name
            applicant.save()  # IMPORTANT: Save to database
            
            result['id_card'] = saved_path
            result['id_card_size'] = id_file.size
            result['id_card_name'] = id_file.name
        
        # Handle Payment Proof upload
        if 'payment_proof' in request.FILES:
            payment_file = request.FILES['payment_proof']
            if payment_file.size > 5 * 1024 * 1024:
                return {"success": False, "message": "File size must be less than 5MB"}, 400
            
            if applicant.payment_proof:
                old_path = os.path.join(settings.MEDIA_ROOT, applicant.payment_proof)
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            ext = payment_file.name.split('.')[-1]
            filename = f"payment_{applicant_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            filepath = os.path.join('documents', str(applicant_id), filename)
            saved_path = default_storage.save(filepath, ContentFile(payment_file.read()))
            
            applicant.payment_proof = saved_path
            applicant.payment_proof_size = payment_file.size
            applicant.payment_proof_name = payment_file.name
            applicant.save()  # IMPORTANT: Save to database
            
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
        return {"success": False, "message": f"Failed to upload: {str(e)}"}, 500

        

@router.get("/applicants/{applicant_id}/documents")
@router.get("/applicants/{applicant_id}/documents/")
def get_documents(request, applicant_id: int):
    """Get all documents for an applicant from database"""
    try:
        user = get_user_from_token(request)
        
        try:
            applicant = Applicant.objects.get(id=applicant_id, user=user)
        except Applicant.DoesNotExist:
            return {
                "success": False,
                "message": "Applicant not found"
            }, 404
        
        # Return stored document paths from the applicant record
        result = {
            "msce": applicant.msce,
            "msce_size": applicant.msce_size,
            "msce_name": applicant.msce_name,
            "id_card": applicant.id_card,
            "id_card_size": applicant.id_card_size,
            "id_card_name": applicant.id_card_name,
            "payment_proof": applicant.payment_proof,
            "payment_proof_size": applicant.payment_proof_size,
            "payment_proof_name": applicant.payment_proof_name
        }
        
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
        }, 500


@router.delete("/applicants/{applicant_id}/documents/{field}")
@router.delete("/applicants/{applicant_id}/documents/{field}/")
def delete_document(request, applicant_id: int, field: str):
    """Delete a specific document for an applicant"""
    try:
        user = get_user_from_token(request)
        
        # Validate the field name
        valid_fields = ['msce', 'id_card', 'payment_proof']
        if field not in valid_fields:
            return {
                "success": False,
                "message": f"Invalid document field. Must be one of: {', '.join(valid_fields)}"
            }, 400
        
        try:
            applicant = Applicant.objects.get(id=applicant_id, user=user)
        except Applicant.DoesNotExist:
            return {
                "success": False,
                "message": "Applicant not found"
            }, 404
        
        # Get the document path from the applicant record
        doc_path = getattr(applicant, field, None)
        
        if not doc_path:
            return {
                "success": False,
                "message": f"No {field} document found to delete"
            }, 404
        
        # Delete the physical file
        if doc_path:
            file_path = os.path.join(settings.MEDIA_ROOT, doc_path)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"✅ Deleted physical file: {file_path}")
                except Exception as e:
                    print(f"Error deleting file: {e}")
        
        # Remove the fields from the applicant record
        setattr(applicant, field, None)
        setattr(applicant, f"{field}_size", None)
        setattr(applicant, f"{field}_name", None)
        applicant.save()
        print(f"✅ Removed {field} reference from applicant record")
        
        return {
            "success": True,
            "message": f"{field.replace('_', ' ').title()} document deleted successfully"
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error deleting document: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Failed to delete document: {str(e)}"
        }, 500




# ==================== DOCUMENTS ENDPOINTS (without applicant_id) ====================

@router.get("/documents", response={200: dict, 401: dict})
@router.get("/documents/", response={200: dict, 401: dict})
def get_all_documents(request):
    """Get all documents for the authenticated user"""
    try:
        user = get_user_from_token(request)
        
        from .models import Document
        
        documents = Document.objects.filter(user=user).order_by('-uploaded_at')
        
        documents_data = []
        for doc in documents:
            documents_data.append({
                "id": doc.id,
                "name": doc.name,
                "type": doc.document_type,
                "url": doc.file.url if doc.file else None,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                "verified": getattr(doc, 'verified', False),
                "verified_at": getattr(doc, 'verified_at', None),
                "size": getattr(doc, 'size', None)
            })
        
        return {
            "success": True,
            "message": "Documents retrieved successfully",
            "data": documents_data,
            "count": len(documents_data)
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching documents: {str(e)}")
        return {
            "success": True,
            "message": "No documents found",
            "data": [],
            "count": 0
        }


@router.post("/documents", response={200: dict, 401: dict})
@router.post("/documents/", response={200: dict, 401: dict})
def upload_document(request):
    """Upload a document for the authenticated user"""
    try:
        user = get_user_from_token(request)
        
        if 'file' not in request.FILES:
            return {
                "success": False,
                "message": "No file provided"
            }
        
        file = request.FILES['file']
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'application/pdf']
        if file.content_type not in allowed_types:
            return {
                "success": False,
                "message": "Invalid file type. Please upload JPG, PNG, or PDF"
            }
        
        # Validate file size (max 5MB)
        if file.size > 5 * 1024 * 1024:
            return {
                "success": False,
                "message": "File size must be less than 5MB"
            }
        
        document_type = request.POST.get('document_type', 'other')
        document_name = request.POST.get('document_name', file.name)
        
        # Create documents directory if it doesn't exist
        docs_dir = os.path.join(settings.MEDIA_ROOT, 'documents', str(user.id))
        os.makedirs(docs_dir, exist_ok=True)
        
        # Save file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        ext = file.name.split('.')[-1]
        filename = f"{document_type}_{user.id}_{timestamp}.{ext}"
        filepath = os.path.join('documents', str(user.id), filename)
        
        saved_path = default_storage.save(filepath, ContentFile(file.read()))
        
        # Create Document record
        Document.objects.create(
            user=user,
            file=saved_path,
            document_type=document_type,
            name=document_name,
            size=file.size
        )
        
        return {
            "success": True,
            "message": "Document uploaded successfully",
            "data": {
                "file_path": saved_path,
                "file_name": file.name,
                "file_size": file.size,
                "document_type": document_type
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error uploading document: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to upload document: {str(e)}"
        }


@router.delete("/documents/{document_id}", response={200: dict, 401: dict, 404: dict})
@router.delete("/documents/{document_id}/", response={200: dict, 401: dict, 404: dict})
def delete_document_by_id(request, document_id: int):
    """Delete a document by ID"""
    try:
        user = get_user_from_token(request)
        
        from .models import Document
        
        try:
            document = Document.objects.get(id=document_id, user=user)
        except Document.DoesNotExist:
            return {
                "success": False,
                "message": "Document not found"
            }
        
        # Delete physical file
        if document.file:
            file_path = os.path.join(settings.MEDIA_ROOT, document.file.name)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting file: {e}")
        
        document.delete()
        
        return {
            "success": True,
            "message": "Document deleted successfully"
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error deleting document: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to delete document: {str(e)}"
        }



        
# ==================== DASHBOARD STATS ENDPOINT ====================

@router.get("/dashboard/stats", response={200: dict})
@router.get("/dashboard/stats/", response={200: dict})
def dashboard_stats(request):
    """Get dashboard statistics for admin"""
    try:
        user = get_user_from_token(request)
        
        print(f"📊 Fetching dashboard stats for user {user.username}")
        
        total_applicants = Applicant.objects.count()
        total_applications = Applicant.objects.exclude(
            selected_programme__isnull=True
        ).exclude(
            selected_programme_name__isnull=True
        ).count()
        total_programmes = Programme.objects.count()
        
        stats_data = {
            "totalApplicants": total_applicants,
            "totalApplications": total_applications,
            "totalProgrammes": total_programmes
        }
        
        return {
            "success": True,
            "message": "Dashboard stats retrieved successfully",
            "data": stats_data
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching dashboard stats: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to fetch dashboard stats: {str(e)}",
            "data": {
                "totalApplicants": 0,
                "totalApplications": 0,
                "totalProgrammes": 0
            }
        }

# ==================== APPLICATION FEES SUBMISSION ENDPOINT ====================
@router.post("/application-fees", response={200: dict, 400: dict, 401: dict})
@router.post("/application-fees/", response={200: dict, 400: dict, 401: dict})
def submit_application_fees(request):
    """Handle application fee submission and save to FeePayment model"""
    try:
        user = get_user_from_token(request)
        print(f"📝 Processing application fee for user {user.username}")
        
        if 'deposit_slip' not in request.FILES:
            return {
                "success": False,
                "message": "Deposit slip is required"
            }
        
        deposit_slip = request.FILES['deposit_slip']
        
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'application/pdf']
        if deposit_slip.content_type not in allowed_types:
            return {
                "success": False,
                "message": "Invalid file type. Please upload JPG, PNG, or PDF"
            }
        
        if deposit_slip.size > 5 * 1024 * 1024:
            return {
                "success": False,
                "message": "File size must be less than 5MB"
            }
        
        fees_dir = os.path.join(settings.MEDIA_ROOT, 'fees', str(user.id))
        os.makedirs(fees_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        ext = deposit_slip.name.split('.')[-1]
        filename = f"deposit_slip_{user.id}_{timestamp}.{ext}"
        filepath = os.path.join('fees', str(user.id), filename)
        
        # Save the file
        saved_path = default_storage.save(filepath, ContentFile(deposit_slip.read()))
        
        # CRITICAL: Save to FeePayment model
        fee_payment, created = FeePayment.objects.get_or_create(user=user)
        fee_payment.deposit_slip_path = saved_path  # Store the path
        fee_payment.status = 'pending'
        fee_payment.amount = 25000  # Or get from request
        fee_payment.uploaded_at = datetime.now()
        fee_payment.save()
        
        print(f"✅ Saved fee payment to database: ID={fee_payment.id}, Path={saved_path}")
        
        # Also update the Applicant model's payment_proof field for compatibility
        try:
            applicant = Applicant.objects.get(user=user)
            applicant.payment_proof = saved_path
            applicant.payment_proof_name = deposit_slip.name
            applicant.payment_proof_size = deposit_slip.size
            applicant.save()
            print(f"✅ Updated Applicant payment_proof field")
        except Applicant.DoesNotExist:
            print(f"⚠️ Applicant not found for user {user.username}")
        
        return {
            "success": True,
            "message": "Deposit slip submitted successfully!",
            "data": {
                "file_path": saved_path,
                "file_name": deposit_slip.name,
                "file_size": deposit_slip.size,
                "status": "pending"
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"❌ Error submitting application fees: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Failed to submit deposit slip: {str(e)}"
        }


@router.get("/application-fees", response={200: dict, 401: dict})
@router.get("/application-fees/", response={200: dict, 401: dict})
def get_application_fees(request):
    """Get application fee status for the current user"""
    try:
        user = get_user_from_token(request)
        print(f"📝 Fetching application fee status for user {user.username}")
        
        # First check FeePayment model
        from .models import FeePayment
        import os
        from django.conf import settings
        
        try:
            fee_payment = FeePayment.objects.get(user=user)
            
            # Check if the file actually exists
            file_exists = False
            if fee_payment.deposit_slip_path:
                full_path = os.path.join(settings.MEDIA_ROOT, fee_payment.deposit_slip_path)
                file_exists = os.path.exists(full_path)
            
            return {
                "success": True,
                "data": {
                    "status": fee_payment.status,
                    "deposit_slip_path": fee_payment.deposit_slip_path if file_exists else None,
                    "file_path": fee_payment.deposit_slip_path if file_exists else None,
                    "uploaded_at": fee_payment.uploaded_at.isoformat() if fee_payment.uploaded_at else None,
                    "amount": float(fee_payment.amount)
                }
            }
        except FeePayment.DoesNotExist:
            print(f"⚠️ No FeePayment record found for user {user.username}")
        
        # Check Applicant model's payment_proof field as fallback
        try:
            from .models import Applicant
            applicant = Applicant.objects.get(user=user)
            if applicant.payment_proof:
                print(f"✅ Found payment_proof in Applicant model: {applicant.payment_proof}")
                return {
                    "success": True,
                    "data": {
                        "status": "pending",
                        "deposit_slip_path": applicant.payment_proof,
                        "file_path": applicant.payment_proof,
                        "file_name": applicant.payment_proof_name,
                        "uploaded_at": applicant.application_date.isoformat() if applicant.application_date else None,
                        "amount": 25000
                    }
                }
        except Applicant.DoesNotExist:
            pass
        
        # Check if file exists in media directory
        fees_dir = os.path.join(settings.MEDIA_ROOT, 'fees', str(user.id))
        if os.path.exists(fees_dir):
            files = os.listdir(fees_dir)
            deposit_slips = [f for f in files if f.startswith('deposit_slip_')]
            if deposit_slips:
                latest_slip = sorted(deposit_slips)[-1]
                print(f"✅ Found deposit slip file in directory: {latest_slip}")
                return {
                    "success": True,
                    "data": {
                        "status": "pending",
                        "deposit_slip_path": os.path.join('fees', str(user.id), latest_slip),
                        "file_path": os.path.join('fees', str(user.id), latest_slip),
                        "file_name": latest_slip,
                        "uploaded_at": datetime.fromtimestamp(os.path.getmtime(os.path.join(fees_dir, latest_slip))).isoformat(),
                        "amount": 25000
                    }
                }
        
        return {
            "success": True,
            "data": None
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching application fees: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Failed to fetch status: {str(e)}"
        }



        
# ==================== GET SINGLE APPLICANT ENDPOINT ====================

@router.get("/applicants/{applicant_id}", response={200: dict, 404: dict, 401: dict})
@router.get("/applicants/{applicant_id}/", response={200: dict, 404: dict, 401: dict})
def get_single_applicant(request, applicant_id: int):
    """Get a single applicant by ID"""
    try:
        user = get_user_from_token(request)
        
        try:
            user_obj = User.objects.get(id=applicant_id)
        except User.DoesNotExist:
            return {
                "success": False,
                "message": f"User with ID {applicant_id} not found"
            }
        
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
                "physical_address": applicant.physical_address or "",
                "date_of_birth": applicant.date_of_birth,
                "gender": applicant.gender,
                "nationality": applicant.nationality,
                "national_id": applicant.national_id,
                "home_district": applicant.home_district,
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
                "physical_address": "",
                "date_of_birth": None,
                "gender": None,
                "nationality": "",
                "national_id": "",
                "home_district": "",
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

# ==================== SUBMIT APPLICATION ENDPOINT ====================
@router.post("/submit", response={200: dict, 400: dict, 401: dict, 409: dict})
@router.post("/submit/", response={200: dict, 400: dict, 401: dict, 409: dict})
def submit_application(request):
    """Final submission of application"""
    try:
        user = get_user_from_token(request)
        print(f"📝 Finalizing application for user {user.username}")
        
        import json
        body = json.loads(request.body) if request.body else {}
        programme_id = body.get('programme_id')
        
        if not programme_id:
            return {
                "success": False,
                "message": "Programme ID is required"
            }
        
        try:
            applicant = Applicant.objects.get(user=user)
        except Applicant.DoesNotExist:
            return {
                "success": False,
                "message": "Applicant profile not found. Please complete your profile first."
            }
        
        # Check if already submitted
        if applicant.status == 'submitted':
            if not hasattr(applicant, 'reference_number') or not applicant.reference_number:
                applicant.reference_number = generate_reference_number(applicant.id)
                applicant.save()
            
            return {
                "success": False,
                "message": "Application already submitted",
                "is_duplicate": True,
                "submission": {
                    "id": applicant.id,
                    "reference_number": applicant.reference_number,
                    "status": applicant.status,
                    "submitted_at": applicant.application_date.isoformat() if applicant.application_date else None,
                    "programme_name": applicant.selected_programme_name or applicant.program or "Not specified"
                },
                "email_sent": False
            }
        
        missing_items = []
        
        if not applicant.first_name or not applicant.last_name or not applicant.email:
            missing_items.append("Personal details")
        
        if not NextOfKin.objects.filter(user=user).exists():
            missing_items.append("Next of kin information")
        
        if not SubjectRecord.objects.filter(user=user).exists():
            missing_items.append("Academic records")
        
        if missing_items:
            return {
                "success": False,
                "message": f"Cannot submit application. Missing: {', '.join(missing_items)}",
                "data": {
                    "missing_items": missing_items
                }
            }
        
        reference_number = generate_reference_number(applicant.id)
        applicant.reference_number = reference_number
        applicant.status = 'submitted'
        applicant.application_date = datetime.now()
        applicant.save()
        
        print(f"✅ Application submitted successfully for user {user.username}")
        print(f"📋 Reference number: {reference_number}")
        
        # ========== CREATE NOTIFICATION ==========
        try:
            from .models import Notification
            
            # Create notification for application submission
            notification_title = "Application Submitted Successfully"
            notification_message = f"Your application has been submitted successfully. Reference Number: {reference_number}. We will notify you once it's reviewed."
            notification_link = "/dashboard/my-applications"
            
            Notification.objects.create(
                user=user,
                title=notification_title,
                message=notification_message,
                notification_type="application",
                is_read=False,
                link=notification_link
            )
            print(f"✅ Notification created for user {user.username}")
            
        except Exception as notif_error:
            print(f"⚠️ Could not create notification: {notif_error}")
        # ========================================
        
        email_sent = False
        try:
            email_sent = send_application_confirmation_email(
                user_email=applicant.email,
                user_name=f"{applicant.first_name} {applicant.last_name}",
                reference_number=reference_number,
                programme_name=applicant.selected_programme_name or "your selected programme"
            )
        except Exception as email_error:
            print(f"⚠️ Email sending failed: {email_error}")
        
        return {
            "success": True,
            "message": "Your application has been submitted successfully!",
            "data": {
                "id": applicant.id,
                "reference_number": reference_number,
                "status": applicant.status,
                "submitted_at": applicant.application_date.isoformat(),
                "programme_name": applicant.selected_programme_name or applicant.program or "Not specified"
            },
            "email_sent": email_sent,
            "is_duplicate": False
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error submitting application: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Failed to submit application: {str(e)}"
        }
# ==================== SUBMISSION STATUS ENDPOINT ====================
@router.get("/submit/status", response={200: dict, 401: dict})
@router.get("/submit/status/", response={200: dict, 401: dict})
def get_submission_status(request):
    """Check if application has been submitted"""
    try:
        user = get_user_from_token(request)
        
        try:
            applicant = Applicant.objects.get(user=user)
            is_submitted = applicant.status == 'submitted'
            reference_number = getattr(applicant, 'reference_number', None)
            
            return {
                "success": True,
                "message": "Submission status retrieved",
                "data": {
                    "is_submitted": is_submitted,
                    "reference_number": reference_number,
                    "status": applicant.status,
                    "submitted_at": applicant.application_date.isoformat() if applicant.application_date else None
                }
            }
        except Applicant.DoesNotExist:
            return {
                "success": True,
                "message": "No application found",
                "data": {
                    "is_submitted": False,
                    "reference_number": None,
                    "status": "not_started",
                    "submitted_at": None
                }
            }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error checking submission status: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }, 500

        
# Helper function to generate reference number
def generate_reference_number(applicant_id):
    """Generate a unique reference number"""
    from datetime import datetime
    prefix = 'MZU'
    year = datetime.now().strftime('%Y')
    month = datetime.now().strftime('%m')
    day = datetime.now().strftime('%d')
    random_num = str(applicant_id).zfill(6)
    timestamp = str(int(datetime.now().timestamp()))[-4:]
    
    return f"{prefix}/{year}/{month}/{day}/{random_num}-{timestamp}"

# Email helper function
def send_application_confirmation_email(user_email, user_name, reference_number, programme_name):
    """Send application confirmation email to applicant"""
    try:
        subject = f'Application Confirmation - {reference_number}'
        
        html_message = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #059669, #047857); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ padding: 20px; background: #f9fafb; border: 1px solid #e5e7eb; }}
                .reference {{ background: #f0fdf4; padding: 15px; border-radius: 8px; text-align: center; margin: 20px 0; }}
                .reference-number {{ font-size: 24px; font-weight: bold; color: #059669; font-family: monospace; letter-spacing: 2px; }}
                .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #6b7280; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Application Received!</h1>
                </div>
                <div class="content">
                    <p>Dear <strong>{user_name}</strong>,</p>
                    <p>Thank you for submitting your application. We have successfully received your application for the <strong>{programme_name}</strong> programme.</p>
                    
                    <div class="reference">
                        <p>Your Application Reference Number:</p>
                        <div class="reference-number">{reference_number}</div>
                        <p>Please keep this number for future reference</p>
                    </div>
                    
                    <h3>Next Steps:</h3>
                    <ol>
                        <li>Your application will be reviewed by the admissions committee</li>
                        <li>You will receive updates via email regarding your application status</li>
                        <li>Please check your application portal regularly for updates</li>
                        <li>Use your reference number for any inquiries</li>
                    </ol>
                    
                    <p>Best regards,<br>
                    <strong>Admissions Office</strong></p>
                </div>
                <div class="footer">
                    <p>This is an automated message, please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        plain_message = f"""
        Application Confirmation - {reference_number}
        
        Dear {user_name},
        
        Thank you for submitting your application for the {programme_name} programme.
        
        Your Application Reference Number: {reference_number}
        
        Please keep this number for future reference.
        
        Best regards,
        Admissions Office
        """
        
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [user_email],
            fail_silently=False,
            html_message=html_message
        )
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False

# ==================== COMMITTEE MANAGEMENT ENDPOINTS ====================

class CommitteeMemberSchema(Schema):
    name: str
    role: str
    email: str
    phone: Optional[str] = None
    department: Optional[str] = None
    bio: Optional[str] = None

class CommitteeMemberUpdateSchema(Schema):
    name: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    bio: Optional[str] = None
    is_active: Optional[bool] = None

@router.get("/committee/members")
@router.get("/committee/members/")
def get_committee_members(request):
    """Get all committee members from database"""
    try:
        user = get_user_from_token(request)
        
        from .models import CommitteeMember
        
        members = CommitteeMember.objects.filter(is_active=True).order_by('order', 'name')
        
        members_data = []
        for member in members:
            members_data.append({
                "id": member.id,
                "name": member.name,
                "role": member.role,
                "email": member.email,
                "phone": member.phone or "",
                "department": member.department or "",
                "bio": member.bio or "",
                "order": member.order,
                "is_active": member.is_active,
            })
        
        return {
            "success": True,
            "message": f"Found {len(members_data)} committee members",
            "data": members_data,
            "count": len(members_data)
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching committee members: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": str(e),
            "data": []
        }

@router.get("/committee/members/{member_id}")
@router.get("/committee/members/{member_id}/")
def get_committee_member(request, member_id: int):
    """Get a single committee member by ID"""
    try:
        user = get_user_from_token(request)
        
        from .models import CommitteeMember
        
        try:
            member = CommitteeMember.objects.get(id=member_id)
        except CommitteeMember.DoesNotExist:
            return {
                "success": False,
                "message": f"Committee member with ID {member_id} not found"
            }
        
        return {
            "success": True,
            "message": "Committee member retrieved successfully",
            "data": {
                "id": member.id,
                "name": member.name,
                "role": member.role,
                "email": member.email,
                "phone": member.phone or "",
                "department": member.department or "",
                "bio": member.bio or "",
                "order": member.order,
                "is_active": member.is_active,
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching committee member: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

@router.post("/committee/members")
@router.post("/committee/members/")
def create_committee_member(request, data: CommitteeMemberSchema):
    """Create a new committee member in database"""
    try:
        user = get_user_from_token(request)
        
        from .models import CommitteeMember
        
        if CommitteeMember.objects.filter(email=data.email).exists():
            return {
                "success": False,
                "message": f"Committee member with email {data.email} already exists"
            }
        
        member = CommitteeMember.objects.create(
            name=data.name,
            role=data.role,
            email=data.email,
            phone=data.phone or "",
            department=data.department or "",
            bio=data.bio or "",
            order=CommitteeMember.objects.count() + 1
        )
        
        return {
            "success": True,
            "message": "Committee member created successfully",
            "data": {
                "id": member.id,
                "name": member.name,
                "role": member.role,
                "email": member.email,
                "phone": member.phone,
                "department": member.department,
                "bio": member.bio,
                "order": member.order,
                "is_active": member.is_active
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error creating committee member: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

@router.put("/committee/members/{member_id}")
@router.put("/committee/members/{member_id}/")
def update_committee_member(request, member_id: int, data: CommitteeMemberUpdateSchema):
    """Update a committee member in database"""
    try:
        user = get_user_from_token(request)
        
        from .models import CommitteeMember
        
        try:
            member = CommitteeMember.objects.get(id=member_id)
        except CommitteeMember.DoesNotExist:
            return {
                "success": False,
                "message": f"Committee member with ID {member_id} not found"
            }
        
        if data.name is not None:
            member.name = data.name
        if data.role is not None:
            member.role = data.role
        if data.email is not None:
            if CommitteeMember.objects.filter(email=data.email).exclude(id=member_id).exists():
                return {
                    "success": False,
                    "message": f"Committee member with email {data.email} already exists"
                }
            member.email = data.email
        if data.phone is not None:
            member.phone = data.phone
        if data.department is not None:
            member.department = data.department
        if data.bio is not None:
            member.bio = data.bio
        if data.is_active is not None:
            member.is_active = data.is_active
        
        member.save()
        
        return {
            "success": True,
            "message": "Committee member updated successfully",
            "data": {
                "id": member.id,
                "name": member.name,
                "role": member.role,
                "email": member.email,
                "phone": member.phone,
                "department": member.department,
                "bio": member.bio,
                "order": member.order,
                "is_active": member.is_active
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error updating committee member: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

@router.delete("/committee/members/{member_id}")
@router.delete("/committee/members/{member_id}/")
def delete_committee_member(request, member_id: int):
    """Delete a committee member from database"""
    try:
        user = get_user_from_token(request)
        
        from .models import CommitteeMember
        
        try:
            member = CommitteeMember.objects.get(id=member_id)
        except CommitteeMember.DoesNotExist:
            return {
                "success": False,
                "message": f"Committee member with ID {member_id} not found"
            }
        
        member_name = member.name
        member.delete()
        
        return {
            "success": True,
            "message": f"Committee member '{member_name}' deleted successfully"
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error deleting committee member: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

@router.patch("/committee/members/reorder")
@router.patch("/committee/members/reorder/")
def reorder_committee_members(request):
    """Reorder committee members"""
    try:
        user = get_user_from_token(request)
        
        import json
        body = json.loads(request.body) if request.body else {}
        member_ids = body.get('member_ids', [])
        
        if not member_ids:
            return {
                "success": False,
                "message": "Member IDs are required"
            }
        
        from .models import CommitteeMember
        
        for index, member_id in enumerate(member_ids):
            try:
                member = CommitteeMember.objects.get(id=member_id)
                member.order = index
                member.save()
            except CommitteeMember.DoesNotExist:
                pass
        
        return {
            "success": True,
            "message": "Committee members reordered successfully"
        }
        
    except Exception as e:
        print(f"Error reordering committee members: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

# ==================== NOTIFICATION ENDPOINTS ====================

def get_time_ago(dt):
    """Convert datetime to 'X minutes/hours/days ago' string"""
    if not dt:
        return "recent"
    
    from django.utils import timezone
    now = timezone.now()
    diff = now - dt
    
    if diff.days > 7:
        return dt.strftime("%b %d, %Y")
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "just now"

def create_notification(user, title, message, notification_type='info', link=None):
    """Create a notification for a user"""
    try:
        from .models import Notification
        
        notification = Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link
        )
        return notification
    except Exception as e:
        print(f"Error creating notification: {str(e)}")
        return None

@router.get("/notifications", response={200: dict, 401: dict})
@router.get("/notifications/", response={200: dict, 401: dict})
def get_notifications(request):
    """Get all notifications for the authenticated user"""
    try:
        user = get_user_from_token(request)
        
        from .models import Notification
        
        notifications = Notification.objects.filter(user=user).order_by('-created_at')[:20]
        
        notifications_data = []
        for notif in notifications:
            notifications_data.append({
                "id": notif.id,
                "title": notif.title,
                "message": notif.message,
                "notification_type": notif.notification_type,
                "is_read": notif.is_read,
                "link": notif.link,
                "created_at": notif.created_at.isoformat() if notif.created_at else None,
                "time_ago": get_time_ago(notif.created_at) if notif.created_at else "recent"
            })
        
        unread_count = Notification.objects.filter(user=user, is_read=False).count()
        
        return {
            "success": True,
            "message": "Notifications retrieved successfully",
            "data": notifications_data,
            "unread_count": unread_count
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching notifications: {str(e)}")
        return {
            "success": True,
            "message": "No notifications found",
            "data": [],
            "unread_count": 0
        }

@router.get("/notifications/unread/count", response={200: dict, 401: dict})
@router.get("/notifications/unread/count/", response={200: dict, 401: dict})
def get_unread_notifications_count(request):
    """Get count of unread notifications"""
    try:
        user = get_user_from_token(request)
        
        from .models import Notification
        
        unread_count = Notification.objects.filter(user=user, is_read=False).count()
        
        return {
            "success": True,
            "count": unread_count
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching unread count: {str(e)}")
        return {
            "success": True,
            "count": 0
        }

@router.put("/notifications/{notification_id}/read", response={200: dict, 401: dict, 404: dict})
@router.put("/notifications/{notification_id}/read/", response={200: dict, 401: dict, 404: dict})
def mark_notification_as_read(request, notification_id: int):
    """Mark a specific notification as read"""
    try:
        user = get_user_from_token(request)
        
        from .models import Notification
        
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            notification.is_read = True
            notification.save()
            
            return {
                "success": True,
                "message": "Notification marked as read"
            }
        except Notification.DoesNotExist:
            return {
                "success": False,
                "message": "Notification not found"
            }
            
    except HttpError:
        raise
    except Exception as e:
        print(f"Error marking notification as read: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

@router.put("/notifications/read-all", response={200: dict, 401: dict})
@router.put("/notifications/read-all/", response={200: dict, 401: dict})
def mark_all_notifications_as_read(request):
    """Mark all notifications as read for the user"""
    try:
        user = get_user_from_token(request)
        
        from .models import Notification
        
        updated_count = Notification.objects.filter(user=user, is_read=False).update(is_read=True)
        
        return {
            "success": True,
            "message": f"Marked {updated_count} notifications as read",
            "updated_count": updated_count
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error marking all as read: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

@router.post("/notifications", response={200: dict, 401: dict})
@router.post("/notifications/", response={200: dict, 401: dict})
def create_notification_endpoint(request):
    """Create a notification (for internal use)"""
    try:
        user = get_user_from_token(request)
        
        import json
        body = json.loads(request.body) if request.body else {}
        
        title = body.get('title')
        message = body.get('message')
        notification_type = body.get('notification_type', 'info')
        link = body.get('link')
        
        if not title or not message:
            return {
                "success": False,
                "message": "Title and message are required"
            }
        
        notification = create_notification(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link
        )
        
        return {
            "success": True,
            "message": "Notification created successfully",
            "data": {
                "id": notification.id,
                "title": notification.title,
                "message": notification.message
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error creating notification: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

# ==================== PASSWORD RESET WITH OTP ====================

import random
from django.core.cache import cache
from django.core.mail import send_mail

class PasswordResetOTPSchema(Schema):
    email: str

class VerifyOTPSchema(Schema):
    email: str
    otp: str

class PasswordResetConfirmSchema(Schema):
    token: str
    email: str
    new_password: str
    confirm_password: str

@router.post("/password-reset/send-otp")
@router.post("/password-reset/send-otp/")
def send_password_reset_otp(request, data: PasswordResetOTPSchema):
    """Send OTP to user's email for password reset"""
    try:
        email = data.email
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return {
                "success": True,
                "message": "If an account exists, an OTP has been sent."
            }
        
        otp = f"{random.randint(100000, 999999)}"
        cache_key = f"password_reset_otp_{email}"
        cache.set(cache_key, otp, timeout=600)
        
        print(f"OTP for {email}: {otp}")
        
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #059669, #047857); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                .otp {{ font-size: 32px; font-weight: bold; color: #059669; text-align: center; padding: 20px; letter-spacing: 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Password Reset OTP</h1>
                </div>
                <div class="content" style="padding: 20px;">
                    <p>Hello {user.username},</p>
                    <p>Your OTP is: <strong style="font-size: 24px;">{otp}</strong></p>
                    <p>This OTP will expire in 10 minutes.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        send_mail(
            'Password Reset OTP',
            f'Your OTP for password reset is: {otp}. Valid for 10 minutes.',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
            html_message=html_message
        )
        
        return {
            "success": True,
            "message": "OTP sent successfully."
        }
        
    except Exception as e:
        print(f"Send OTP error: {str(e)}")
        return {
            "success": False,
            "message": "Failed to send OTP. Please try again."
        }

@router.post("/password-reset/verify-otp")
@router.post("/password-reset/verify-otp/")
def verify_password_reset_otp(request, data: VerifyOTPSchema):
    """Verify OTP and return reset token"""
    try:
        email = data.email
        otp = data.otp
        
        cache_key = f"password_reset_otp_{email}"
        stored_otp = cache.get(cache_key)
        
        if not stored_otp:
            return {
                "success": False,
                "message": "OTP has expired. Please request a new one."
            }
        
        if stored_otp != otp:
            return {
                "success": False,
                "message": "Invalid OTP. Please try again."
            }
        
        import uuid
        reset_token = str(uuid.uuid4())
        
        token_cache_key = f"password_reset_token_{reset_token}"
        cache.set(token_cache_key, email, timeout=3600)
        
        cache.delete(cache_key)
        
        return {
            "success": True,
            "message": "OTP verified successfully.",
            "reset_token": reset_token
        }
        
    except Exception as e:
        print(f"Verify OTP error: {str(e)}")
        return {
            "success": False,
            "message": "Failed to verify OTP. Please try again."
        }

@router.post("/password-reset/confirm")
@router.post("/password-reset/confirm/")
def password_reset_confirm(request, data: PasswordResetConfirmSchema):
    """Confirm password reset with token"""
    try:
        token = data.token
        email = data.email
        new_password = data.new_password
        confirm_password = data.confirm_password
        
        if new_password != confirm_password:
            return {
                "success": False,
                "message": "Passwords do not match"
            }
        
        if len(new_password) < 8:
            return {
                "success": False,
                "message": "Password must be at least 8 characters"
            }
        
        token_cache_key = f"password_reset_token_{token}"
        stored_email = cache.get(token_cache_key)
        
        if not stored_email or stored_email != email:
            return {
                "success": False,
                "message": "Invalid or expired reset link. Please request a new one."
            }
        
        try:
            user = User.objects.get(email=email)
            user.set_password(new_password)
            user.save()
            cache.delete(token_cache_key)
            
            return {
                "success": True,
                "message": "Password has been reset successfully. Please login with your new password."
            }
        except User.DoesNotExist:
            return {
                "success": False,
                "message": "User not found."
            }
        
    except Exception as e:
        print(f"Password reset confirm error: {str(e)}")
        return {
            "success": False,
            "message": "Failed to reset password. Please try again."
        }


# Add this schema with your other schemas
class EducationSchema(Schema):
    qualification_type: str
    institution: str
    start_date: str
    end_date: Optional[str] = None
    currently_studying: bool = False

# Add these education endpoints after your other endpoints (before the final api.add_router lines)

# ==================== EDUCATION ENDPOINTS ====================

@router.get("/education", response={200: dict, 401: dict})
@router.get("/education/", response={200: dict, 401: dict})
def get_education(request):
    """Get all education records for the authenticated user"""
    try:
        user = get_user_from_token(request)
        
        # Get education records from database
        # Assuming you have an Education model, or create one
        from .models import Education
        
        records = Education.objects.filter(user=user).order_by('-start_date')
        
        data = []
        for record in records:
            data.append({
                "id": record.id,
                "qualification_type": record.qualification_type,
                "institution": record.institution,
                "start_date": record.start_date.isoformat() if record.start_date else None,
                "end_date": record.end_date.isoformat() if record.end_date else None,
                "currently_studying": record.currently_studying,
            })
        
        return {
            "success": True,
            "message": "Education records retrieved successfully",
            "data": data,
            "count": len(data)
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching education: {str(e)}")
        return {
            "success": True,
            "message": "No education records found",
            "data": [],
            "count": 0
        }


@router.post("/education", response={200: dict, 401: dict})
@router.post("/education/", response={200: dict, 401: dict})
def create_education(request, data: EducationSchema):
    """Create a new education record"""
    try:
        user = get_user_from_token(request)
        
        from .models import Education
        
        record = Education.objects.create(
            user=user,
            qualification_type=data.qualification_type,
            institution=data.institution,
            start_date=data.start_date,
            end_date=data.end_date if not data.currently_studying else None,
            currently_studying=data.currently_studying,
        )
        
        return {
            "success": True,
            "message": "Education record created successfully",
            "data": {
                "id": record.id,
                "qualification_type": record.qualification_type,
                "institution": record.institution,
                "start_date": record.start_date.isoformat() if record.start_date else None,
                "end_date": record.end_date.isoformat() if record.end_date else None,
                "currently_studying": record.currently_studying,
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error creating education: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to create education record: {str(e)}"
        }


@router.put("/education/{record_id}", response={200: dict, 401: dict, 404: dict})
@router.put("/education/{record_id}/", response={200: dict, 401: dict, 404: dict})
def update_education(request, record_id: int, data: EducationSchema):
    """Update an education record"""
    try:
        user = get_user_from_token(request)
        
        from .models import Education
        
        try:
            record = Education.objects.get(id=record_id, user=user)
        except Education.DoesNotExist:
            return {
                "success": False,
                "message": "Education record not found"
            }
        
        record.qualification_type = data.qualification_type
        record.institution = data.institution
        record.start_date = data.start_date
        record.end_date = data.end_date if not data.currently_studying else None
        record.currently_studying = data.currently_studying
        record.save()
        
        return {
            "success": True,
            "message": "Education record updated successfully",
            "data": {
                "id": record.id,
                "qualification_type": record.qualification_type,
                "institution": record.institution,
                "start_date": record.start_date.isoformat() if record.start_date else None,
                "end_date": record.end_date.isoformat() if record.end_date else None,
                "currently_studying": record.currently_studying,
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error updating education: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to update education record: {str(e)}"
        }


@router.delete("/education/{record_id}", response={200: dict, 401: dict, 404: dict})
@router.delete("/education/{record_id}/", response={200: dict, 401: dict, 404: dict})
def delete_education(request, record_id: int):
    """Delete an education record"""
    try:
        user = get_user_from_token(request)
        
        from .models import Education
        
        try:
            record = Education.objects.get(id=record_id, user=user)
        except Education.DoesNotExist:
            return {
                "success": False,
                "message": "Education record not found"
            }
        
        record.delete()
        
        return {
            "success": True,
            "message": "Education record deleted successfully",
            "data": None
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error deleting education: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to delete education record: {str(e)}"
        }


# Add this schema with your other schemas
class WorkHistorySchema(Schema):
    organization: str
    job_title: str
    employment_type: Optional[str] = None
    location: Optional[str] = None
    location_type: Optional[str] = None
    start_date: str
    end_date: Optional[str] = None
    currently_working: bool = False
    responsibilities: Optional[str] = None

# ==================== WORK HISTORY ENDPOINTS ====================

@router.get("/work-history", response={200: dict, 401: dict})
@router.get("/work-history/", response={200: dict, 401: dict})
def get_work_history(request):
    """Get all work history records for the authenticated user"""
    try:
        user = get_user_from_token(request)
        
        from .models import WorkHistory
        
        records = WorkHistory.objects.filter(user=user).order_by('-start_date')
        
        data = []
        for record in records:
            data.append({
                "id": record.id,
                "organization": record.organization,
                "job_title": record.job_title,
                "employment_type": record.employment_type,
                "location": record.location,
                "location_type": record.location_type,
                "start_date": record.start_date.isoformat() if record.start_date else None,
                "end_date": record.end_date.isoformat() if record.end_date else None,
                "currently_working": record.currently_working,
                "responsibilities": record.responsibilities,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "updated_at": record.updated_at.isoformat() if record.updated_at else None
            })
        
        return {
            "success": True,
            "message": "Work history retrieved successfully",
            "data": data,
            "count": len(data)
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching work history: {str(e)}")
        return {
            "success": True,
            "message": "No work history found",
            "data": [],
            "count": 0
        }


@router.post("/work-history", response={200: dict, 401: dict})
@router.post("/work-history/", response={200: dict, 401: dict})
def create_work_history(request, data: WorkHistorySchema):
    """Create a new work history record"""
    try:
        user = get_user_from_token(request)
        
        from .models import WorkHistory
        
        record = WorkHistory.objects.create(
            user=user,
            organization=data.organization,
            job_title=data.job_title,
            employment_type=data.employment_type,
            location=data.location,
            location_type=data.location_type,
            start_date=data.start_date,
            end_date=data.end_date if not data.currently_working else None,
            currently_working=data.currently_working,
            responsibilities=data.responsibilities,
        )
        
        return {
            "success": True,
            "message": "Work history record created successfully",
            "data": {
                "id": record.id,
                "organization": record.organization,
                "job_title": record.job_title,
                "employment_type": record.employment_type,
                "location": record.location,
                "location_type": record.location_type,
                "start_date": record.start_date.isoformat() if record.start_date else None,
                "end_date": record.end_date.isoformat() if record.end_date else None,
                "currently_working": record.currently_working,
                "responsibilities": record.responsibilities,
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error creating work history: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to create work history record: {str(e)}"
        }


@router.put("/work-history/{record_id}", response={200: dict, 401: dict, 404: dict})
@router.put("/work-history/{record_id}/", response={200: dict, 401: dict, 404: dict})
def update_work_history(request, record_id: int, data: WorkHistorySchema):
    """Update a work history record"""
    try:
        user = get_user_from_token(request)
        
        from .models import WorkHistory
        
        try:
            record = WorkHistory.objects.get(id=record_id, user=user)
        except WorkHistory.DoesNotExist:
            return {
                "success": False,
                "message": "Work history record not found"
            }
        
        record.organization = data.organization
        record.job_title = data.job_title
        record.employment_type = data.employment_type
        record.location = data.location
        record.location_type = data.location_type
        record.start_date = data.start_date
        record.end_date = data.end_date if not data.currently_working else None
        record.currently_working = data.currently_working
        record.responsibilities = data.responsibilities
        record.save()
        
        return {
            "success": True,
            "message": "Work history record updated successfully",
            "data": {
                "id": record.id,
                "organization": record.organization,
                "job_title": record.job_title,
                "employment_type": record.employment_type,
                "location": record.location,
                "location_type": record.location_type,
                "start_date": record.start_date.isoformat() if record.start_date else None,
                "end_date": record.end_date.isoformat() if record.end_date else None,
                "currently_working": record.currently_working,
                "responsibilities": record.responsibilities,
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error updating work history: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to update work history record: {str(e)}"
        }


@router.delete("/work-history/{record_id}", response={200: dict, 401: dict, 404: dict})
@router.delete("/work-history/{record_id}/", response={200: dict, 401: dict, 404: dict})
def delete_work_history(request, record_id: int):
    """Delete a work history record"""
    try:
        user = get_user_from_token(request)
        
        from .models import WorkHistory
        
        try:
            record = WorkHistory.objects.get(id=record_id, user=user)
        except WorkHistory.DoesNotExist:
            return {
                "success": False,
                "message": "Work history record not found"
            }
        
        record.delete()
        
        return {
            "success": True,
            "message": "Work history record deleted successfully",
            "data": None
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error deleting work history: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to delete work history record: {str(e)}"
        }

# Add this schema with your other schemas
class PublicationSchema(Schema):
    title: str
    journal: str
    year: str
    link: Optional[str] = None
    authors: Optional[str] = None
    doi: Optional[str] = None

# ==================== PUBLICATIONS ENDPOINTS ====================

@router.get("/publications", response={200: dict, 401: dict})
@router.get("/publications/", response={200: dict, 401: dict})
def get_publications(request):
    """Get all publications for the authenticated user"""
    try:
        user = get_user_from_token(request)
        
        from .models import Publication
        
        records = Publication.objects.filter(user=user).order_by('-year')
        
        data = []
        for record in records:
            data.append({
                "id": record.id,
                "title": record.title,
                "journal": record.journal,
                "year": record.year,
                "link": record.link,
                "authors": record.authors,
                "doi": record.doi,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "updated_at": record.updated_at.isoformat() if record.updated_at else None
            })
        
        return {
            "success": True,
            "message": "Publications retrieved successfully",
            "data": data,
            "count": len(data)
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching publications: {str(e)}")
        return {
            "success": True,
            "message": "No publications found",
            "data": [],
            "count": 0
        }


@router.post("/publications", response={200: dict, 401: dict})
@router.post("/publications/", response={200: dict, 401: dict})
def create_publication(request, data: PublicationSchema):
    """Create a new publication record"""
    try:
        user = get_user_from_token(request)
        
        from .models import Publication
        
        # Validate year
        current_year = datetime.now().year
        year = int(data.year)
        if year < 1900 or year > current_year + 5:
            return {
                "success": False,
                "message": f"Year must be between 1900 and {current_year + 5}"
            }
        
        record = Publication.objects.create(
            user=user,
            title=data.title,
            journal=data.journal,
            year=data.year,
            link=data.link,
            authors=data.authors,
            doi=data.doi,
        )
        
        return {
            "success": True,
            "message": "Publication created successfully",
            "data": {
                "id": record.id,
                "title": record.title,
                "journal": record.journal,
                "year": record.year,
                "link": record.link,
                "authors": record.authors,
                "doi": record.doi,
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error creating publication: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to create publication: {str(e)}"
        }


@router.put("/publications/{record_id}", response={200: dict, 401: dict, 404: dict})
@router.put("/publications/{record_id}/", response={200: dict, 401: dict, 404: dict})
def update_publication(request, record_id: int, data: PublicationSchema):
    """Update a publication record"""
    try:
        user = get_user_from_token(request)
        
        from .models import Publication
        
        try:
            record = Publication.objects.get(id=record_id, user=user)
        except Publication.DoesNotExist:
            return {
                "success": False,
                "message": "Publication not found"
            }
        
        # Validate year
        current_year = datetime.now().year
        year = int(data.year)
        if year < 1900 or year > current_year + 5:
            return {
                "success": False,
                "message": f"Year must be between 1900 and {current_year + 5}"
            }
        
        record.title = data.title
        record.journal = data.journal
        record.year = data.year
        record.link = data.link
        record.authors = data.authors
        record.doi = data.doi
        record.save()
        
        return {
            "success": True,
            "message": "Publication updated successfully",
            "data": {
                "id": record.id,
                "title": record.title,
                "journal": record.journal,
                "year": record.year,
                "link": record.link,
                "authors": record.authors,
                "doi": record.doi,
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error updating publication: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to update publication: {str(e)}"
        }


@router.delete("/publications/{record_id}", response={200: dict, 401: dict, 404: dict})
@router.delete("/publications/{record_id}/", response={200: dict, 401: dict, 404: dict})
def delete_publication(request, record_id: int):
    """Delete a publication record"""
    try:
        user = get_user_from_token(request)
        
        from .models import Publication
        
        try:
            record = Publication.objects.get(id=record_id, user=user)
        except Publication.DoesNotExist:
            return {
                "success": False,
                "message": "Publication not found"
            }
        
        record.delete()
        
        return {
            "success": True,
            "message": "Publication deleted successfully",
            "data": None
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error deleting publication: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to delete publication: {str(e)}"
        }

# Add this schema with your other schemas
class EssaySchema(Schema):
    motivation: str
    research_concept_note: Optional[str] = None

# ==================== ESSAY ENDPOINTS ====================

@router.get("/essay", response={200: dict, 401: dict})
@router.get("/essay/", response={200: dict, 401: dict})
def get_essay(request):
    """Get essay for the authenticated user"""
    try:
        user = get_user_from_token(request)
        
        from .models import Essay
        
        try:
            essay = Essay.objects.get(user=user)
            return {
                "success": True,
                "message": "Essay retrieved successfully",
                "data": {
                    "id": essay.id,
                    "motivation": essay.motivation,
                    "research_concept_note": essay.research_concept_note,
                    "created_at": essay.created_at.isoformat() if essay.created_at else None,
                    "updated_at": essay.updated_at.isoformat() if essay.updated_at else None
                }
            }
        except Essay.DoesNotExist:
            return {
                "success": True,
                "message": "No essay found",
                "data": {
                    "motivation": "",
                    "research_concept_note": ""
                }
            }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching essay: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to fetch essay: {str(e)}",
            "data": None
        }


@router.post("/essay", response={200: dict, 401: dict})
@router.post("/essay/", response={200: dict, 401: dict})
def save_essay(request, data: EssaySchema):
    """Save or update essay for the authenticated user"""
    try:
        user = get_user_from_token(request)
        
        from .models import Essay
        
        # Validate word count for motivation (max 500 words)
        motivation_words = len(data.motivation.split())
        if motivation_words > 500:
            return {
                "success": False,
                "message": f"Motivation exceeds 500 words. Current word count: {motivation_words}"
            }
        
        # Validate word count for research concept note if provided (max 1000 words)
        if data.research_concept_note:
            research_words = len(data.research_concept_note.split())
            if research_words > 1000:
                return {
                    "success": False,
                    "message": f"Research concept note exceeds 1000 words. Current word count: {research_words}"
                }
        
        essay, created = Essay.objects.update_or_create(
            user=user,
            defaults={
                'motivation': data.motivation,
                'research_concept_note': data.research_concept_note,
            }
        )
        
        return {
            "success": True,
            "message": "Essay saved successfully",
            "data": {
                "id": essay.id,
                "motivation": essay.motivation,
                "research_concept_note": essay.research_concept_note,
                "word_count": {
                    "motivation": motivation_words,
                    "research_concept_note": len(data.research_concept_note.split()) if data.research_concept_note else 0
                }
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error saving essay: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to save essay: {str(e)}"
        }

# Add these schemas with your other schema definitions

class RefereeSchema(Schema):
    title: str
    first_name: str
    last_name: str
    gender: str
    email: str
    phone_number: str
    referee_type: str

class RefereeResponseSchema(Schema):
    id: int
    title: str
    first_name: str
    last_name: str
    gender: str
    email: str
    phone_number: str
    referee_type: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None




# ==================== DIRECT ESSAY ENDPOINTS (without applicant_id) ====================

@router.get("/essays", response={200: dict, 401: dict})
@router.get("/essays/", response={200: dict, 401: dict})
def get_essay_direct(request):
    """Get essay for the authenticated user"""
    try:
        user = get_user_from_token(request)
        
        from .models import Essay
        
        try:
            essay = Essay.objects.get(user=user)
            return {
                "success": True,
                "message": "Essay retrieved successfully",
                "data": {
                    "id": essay.id,
                    "motivation": essay.motivation,
                    "research_concept_note": essay.research_concept_note,
                    "created_at": essay.created_at.isoformat() if essay.created_at else None,
                    "updated_at": essay.updated_at.isoformat() if essay.updated_at else None
                }
            }
        except Essay.DoesNotExist:
            return {
                "success": True,
                "message": "No essay found",
                "data": None
            }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching essay: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to fetch essay: {str(e)}",
            "data": None
        }


@router.post("/essays", response={200: dict, 401: dict})
@router.post("/essays/", response={200: dict, 401: dict})
def save_essay_direct(request, data: EssaySchema):
    """Save or update essay for the authenticated user"""
    try:
        user = get_user_from_token(request)
        
        from .models import Essay
        
        # Validate word count for motivation (max 500 words)
        motivation_words = len(data.motivation.split()) if data.motivation else 0
        if motivation_words > 500:
            return {
                "success": False,
                "message": f"Motivation exceeds 500 words. Current word count: {motivation_words}"
            }
        
        # Validate word count for research concept note if provided (max 1000 words)
        if data.research_concept_note:
            research_words = len(data.research_concept_note.split())
            if research_words > 1000:
                return {
                    "success": False,
                    "message": f"Research concept note exceeds 1000 words. Current word count: {research_words}"
                }
        
        essay, created = Essay.objects.update_or_create(
            user=user,
            defaults={
                'motivation': data.motivation or "",
                'research_concept_note': data.research_concept_note,
            }
        )
        
        return {
            "success": True,
            "message": "Essay saved successfully" if not created else "Essay created successfully",
            "data": {
                "id": essay.id,
                "motivation": essay.motivation,
                "research_concept_note": essay.research_concept_note,
                "word_count": {
                    "motivation": motivation_words,
                    "research_concept_note": len(data.research_concept_note.split()) if data.research_concept_note else 0
                }
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error saving essay: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to save essay: {str(e)}"
        }


@router.put("/essays", response={200: dict, 401: dict})
@router.put("/essays/", response={200: dict, 401: dict})
def update_essay_direct(request, data: EssaySchema):
    """Update essay for the authenticated user (alias for POST)"""
    try:
        user = get_user_from_token(request)
        
        from .models import Essay
        
        # Validate word count
        motivation_words = len(data.motivation.split()) if data.motivation else 0
        if motivation_words > 500:
            return {
                "success": False,
                "message": f"Motivation exceeds 500 words. Current word count: {motivation_words}"
            }
        
        if data.research_concept_note:
            research_words = len(data.research_concept_note.split())
            if research_words > 1000:
                return {
                    "success": False,
                    "message": f"Research concept note exceeds 1000 words. Current word count: {research_words}"
                }
        
        essay, created = Essay.objects.update_or_create(
            user=user,
            defaults={
                'motivation': data.motivation or "",
                'research_concept_note': data.research_concept_note,
            }
        )
        
        return {
            "success": True,
            "message": "Essay updated successfully",
            "data": {
                "id": essay.id,
                "motivation": essay.motivation,
                "research_concept_note": essay.research_concept_note,
                "word_count": {
                    "motivation": motivation_words,
                    "research_concept_note": len(data.research_concept_note.split()) if data.research_concept_note else 0
                }
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error updating essay: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to update essay: {str(e)}"
        }


@router.delete("/essays", response={200: dict, 401: dict})
@router.delete("/essays/", response={200: dict, 401: dict})
def delete_essay_direct(request):
    """Delete essay for the authenticated user"""
    try:
        user = get_user_from_token(request)
        
        from .models import Essay
        
        try:
            essay = Essay.objects.get(user=user)
            essay.delete()
            return {
                "success": True,
                "message": "Essay deleted successfully"
            }
        except Essay.DoesNotExist:
            return {
                "success": True,
                "message": "No essay found to delete"
            }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error deleting essay: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to delete essay: {str(e)}"
        }



# ==================== REFEREE ENDPOINTS (Nested under applicants) ====================

# First, make sure the schema is defined
class RefereeSchema(Schema):
    title: str
    first_name: str
    last_name: str
    gender: str
    email: str
    phone_number: str
    referee_type: str

class RefereeResponseSchema(Schema):
    success: bool
    message: str
    data: Optional[dict] = None
    count: Optional[int] = None

@router.get("/applicants/{applicant_id}/referees")
@router.get("/applicants/{applicant_id}/referees/")
def get_referees(request, applicant_id: int):
    """Get all referees for an applicant"""
    try:
        user = get_user_from_token(request)
        
        from .models import Referee, Applicant
        
        # Verify the applicant belongs to the user
        try:
            applicant = Applicant.objects.get(id=applicant_id, user=user)
        except Applicant.DoesNotExist:
            return {
                "success": False,
                "message": "Applicant not found"
            }
        
        referees = Referee.objects.filter(user=user).order_by('-created_at')
        
        data = []
        for referee in referees:
            # Map gender from DB to frontend format
            gender_mapping = {
                'M': 'Male',
                'F': 'Female',
                'NB': 'Non-binary',
                'O': 'Prefer not to say',
                'OT': 'Other',
            }
            
            data.append({
                "id": referee.id,
                "title": referee.title,
                "first_name": referee.first_name,
                "last_name": referee.last_name,
                "gender": gender_mapping.get(referee.gender, 'Other'),
                "email": referee.email,
                "phone_number": referee.phone_number,
                "referee_type": referee.referee_type,
                "created_at": referee.created_at.isoformat() if referee.created_at else None,
                "updated_at": referee.updated_at.isoformat() if referee.updated_at else None
            })
        
        return {
            "success": True,
            "message": "Referees retrieved successfully",
            "data": data,
            "count": len(data)
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching referees: {str(e)}")
        return {
            "success": True,
            "message": "No referees found",
            "data": [],
            "count": 0
        }


@router.post("/applicants/{applicant_id}/referees")
@router.post("/applicants/{applicant_id}/referees/")
def create_referee(request, applicant_id: int, data: RefereeSchema):
    """Create a new referee for an applicant"""
    try:
        user = get_user_from_token(request)
        
        from .models import Referee, Applicant
        
        # Verify the applicant belongs to the user
        try:
            applicant = Applicant.objects.get(id=applicant_id, user=user)
        except Applicant.DoesNotExist:
            return {
                "success": False,
                "message": "Applicant not found"
            }
        
        # Validate required fields
        if not data.first_name or not data.first_name.strip():
            return {
                "success": False,
                "message": "First name is required"
            }
        
        if not data.last_name or not data.last_name.strip():
            return {
                "success": False,
                "message": "Last name is required"
            }
        
        # Validate email format
        if not data.email or '@' not in data.email or '.' not in data.email:
            return {
                "success": False,
                "message": "Invalid email format"
            }
        
        # Validate phone number (basic validation)
        if not data.phone_number or len(data.phone_number) < 10:
            return {
                "success": False,
                "message": "Phone number must be at least 10 digits"
            }
        
        # Validate title
        valid_titles = ['Dr.', 'Prof.', 'Mr.', 'Ms.', 'Mrs.', 'Mx.']
        if data.title not in valid_titles:
            return {
                "success": False,
                "message": f"Invalid title. Must be one of: {', '.join(valid_titles)}"
            }
        
        # Validate referee type
        valid_referee_types = ['Academic', 'Professional', 'Personal', 'Supervisor', 'Manager', 'Colleague']
        if data.referee_type not in valid_referee_types:
            return {
                "success": False,
                "message": f"Invalid referee type. Must be one of: {', '.join(valid_referee_types)}"
            }
        
        # Map gender from frontend values to database choices
        gender_mapping = {
            'Male': 'M',
            'Female': 'F',
            'Non-binary': 'NB',
            'Prefer not to say': 'O',
            'Other': 'OT',
        }
        
        db_gender = gender_mapping.get(data.gender, 'O')
        
        # Create referee
        referee = Referee.objects.create(
            user=user,
            title=data.title,
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            gender=db_gender,
            email=data.email.strip(),
            phone_number=data.phone_number.strip(),
            referee_type=data.referee_type,
        )
        
        # Create notification for the user
        try:
            from .models import Notification
            Notification.objects.create(
                user=user,
                title="Referee Added",
                message=f"Referee {referee.get_full_name()} has been added successfully.",
                notification_type="info",
                link="/dashboard/referees"
            )
        except Exception as notif_error:
            print(f"Could not create notification: {notif_error}")
        
        # Return with gender mapped back for frontend
        gender_reverse = {v: k for k, v in gender_mapping.items()}
        
        return {
            "success": True,
            "message": "Referee created successfully",
            "data": {
                "id": referee.id,
                "title": referee.title,
                "first_name": referee.first_name,
                "last_name": referee.last_name,
                "gender": gender_reverse.get(referee.gender, 'Other'),
                "email": referee.email,
                "phone_number": referee.phone_number,
                "referee_type": referee.referee_type,
                "created_at": referee.created_at.isoformat() if referee.created_at else None
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error creating referee: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Failed to create referee: {str(e)}"
        }


@router.put("/applicants/{applicant_id}/referees/{referee_id}")
@router.put("/applicants/{applicant_id}/referees/{referee_id}/")
def update_referee(request, applicant_id: int, referee_id: int, data: RefereeSchema):
    """Update an existing referee"""
    try:
        user = get_user_from_token(request)
        
        from .models import Referee, Applicant
        
        # Verify the applicant belongs to the user
        try:
            applicant = Applicant.objects.get(id=applicant_id, user=user)
        except Applicant.DoesNotExist:
            return {
                "success": False,
                "message": "Applicant not found"
            }
        
        try:
            referee = Referee.objects.get(id=referee_id, user=user)
        except Referee.DoesNotExist:
            return {
                "success": False,
                "message": "Referee not found"
            }
        
        # Validate required fields
        if not data.first_name or not data.first_name.strip():
            return {
                "success": False,
                "message": "First name is required"
            }
        
        if not data.last_name or not data.last_name.strip():
            return {
                "success": False,
                "message": "Last name is required"
            }
        
        # Validate email format
        if not data.email or '@' not in data.email or '.' not in data.email:
            return {
                "success": False,
                "message": "Invalid email format"
            }
        
        # Validate phone number
        if not data.phone_number or len(data.phone_number) < 10:
            return {
                "success": False,
                "message": "Phone number must be at least 10 digits"
            }
        
        # Map gender
        gender_mapping = {
            'Male': 'M',
            'Female': 'F',
            'Non-binary': 'NB',
            'Prefer not to say': 'O',
            'Other': 'OT',
        }
        
        db_gender = gender_mapping.get(data.gender, 'O')
        
        # Update referee
        referee.title = data.title
        referee.first_name = data.first_name.strip()
        referee.last_name = data.last_name.strip()
        referee.gender = db_gender
        referee.email = data.email.strip()
        referee.phone_number = data.phone_number.strip()
        referee.referee_type = data.referee_type
        referee.save()
        
        gender_reverse = {v: k for k, v in gender_mapping.items()}
        
        return {
            "success": True,
            "message": "Referee updated successfully",
            "data": {
                "id": referee.id,
                "title": referee.title,
                "first_name": referee.first_name,
                "last_name": referee.last_name,
                "gender": gender_reverse.get(referee.gender, 'Other'),
                "email": referee.email,
                "phone_number": referee.phone_number,
                "referee_type": referee.referee_type,
                "updated_at": referee.updated_at.isoformat() if referee.updated_at else None
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error updating referee: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to update referee: {str(e)}"
        }


@router.delete("/applicants/{applicant_id}/referees/{referee_id}")
@router.delete("/applicants/{applicant_id}/referees/{referee_id}/")
def delete_referee(request, applicant_id: int, referee_id: int):
    """Delete a referee"""
    try:
        user = get_user_from_token(request)
        
        from .models import Referee, Applicant
        
        # Verify the applicant belongs to the user
        try:
            applicant = Applicant.objects.get(id=applicant_id, user=user)
        except Applicant.DoesNotExist:
            return {
                "success": False,
                "message": "Applicant not found"
            }
        
        try:
            referee = Referee.objects.get(id=referee_id, user=user)
        except Referee.DoesNotExist:
            return {
                "success": False,
                "message": "Referee not found"
            }
        
        referee_name = referee.get_full_name()
        referee.delete()
        
        return {
            "success": True,
            "message": f"Referee '{referee_name}' deleted successfully",
            "data": None
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error deleting referee: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to delete referee: {str(e)}"
        }





# ==================== DIRECT REFEREE ENDPOINTS (without applicant_id) ====================

@router.get("/referees", response={200: dict, 401: dict})
@router.get("/referees/", response={200: dict, 401: dict})
def get_all_referees(request):
    """Get all referees for the authenticated user"""
    try:
        user = get_user_from_token(request)
        
        from .models import Referee
        
        referees = Referee.objects.filter(user=user).order_by('-created_at')
        
        # Gender mapping for display
        gender_mapping = {
            'M': 'Male',
            'F': 'Female',
            'NB': 'Non-binary',
            'O': 'Prefer not to say',
            'OT': 'Other',
        }
        
        data = []
        for referee in referees:
            data.append({
                "id": referee.id,
                "title": referee.title,
                "first_name": referee.first_name,
                "last_name": referee.last_name,
                "gender": gender_mapping.get(referee.gender, 'Other'),
                "email": referee.email,
                "phone_number": referee.phone_number,
                "referee_type": referee.referee_type,
                "created_at": referee.created_at.isoformat() if referee.created_at else None,
                "updated_at": referee.updated_at.isoformat() if referee.updated_at else None
            })
        
        return {
            "success": True,
            "message": "Referees retrieved successfully",
            "data": data,
            "count": len(data)
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching referees: {str(e)}")
        return {
            "success": True,
            "message": "No referees found",
            "data": [],
            "count": 0
        }


@router.post("/referees", response={200: dict, 401: dict})
@router.post("/referees/", response={200: dict, 401: dict})
def create_referee_direct(request, data: RefereeSchema):
    """Create a new referee for the authenticated user"""
    try:
        user = get_user_from_token(request)
        
        from .models import Referee
        
        # Validate required fields
        if not data.first_name or not data.first_name.strip():
            return {
                "success": False,
                "message": "First name is required"
            }
        
        if not data.last_name or not data.last_name.strip():
            return {
                "success": False,
                "message": "Last name is required"
            }
        
        # Validate email format
        if not data.email or '@' not in data.email or '.' not in data.email:
            return {
                "success": False,
                "message": "Invalid email format"
            }
        
        # Validate phone number (basic validation)
        if not data.phone_number or len(data.phone_number) < 10:
            return {
                "success": False,
                "message": "Phone number must be at least 10 digits"
            }
        
        # Validate title
        valid_titles = ['Mr', 'Mrs', 'Miss', 'Ms', 'Dr', 'Prof', 'Mx']
        if data.title not in valid_titles:
            return {
                "success": False,
                "message": f"Invalid title. Must be one of: {', '.join(valid_titles)}"
            }
        
        # Validate referee type
        valid_referee_types = ['Academic', 'Professional', 'Personal', 'Supervisor', 'Manager', 'Colleague']
        if data.referee_type not in valid_referee_types:
            return {
                "success": False,
                "message": f"Invalid referee type. Must be one of: {', '.join(valid_referee_types)}"
            }
        
        # Map gender from frontend values to database choices
        gender_mapping = {
            'Male': 'M',
            'Female': 'F',
            'Non-binary': 'NB',
            'Prefer not to say': 'O',
            'Other': 'OT',
        }
        
        db_gender = gender_mapping.get(data.gender, 'O')
        
        # Create referee
        referee = Referee.objects.create(
            user=user,
            title=data.title,
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            gender=db_gender,
            email=data.email.strip(),
            phone_number=data.phone_number.strip(),
            referee_type=data.referee_type,
        )
        
        # Create notification for the user
        try:
            from .models import Notification
            Notification.objects.create(
                user=user,
                title="Referee Added",
                message=f"Referee {referee.get_full_name()} has been added successfully.",
                notification_type="info",
                link="/dashboard/referees"
            )
        except Exception as notif_error:
            print(f"Could not create notification: {notif_error}")
        
        # Return with gender mapped back for frontend
        gender_reverse = {v: k for k, v in gender_mapping.items()}
        
        return {
            "success": True,
            "message": "Referee created successfully",
            "data": {
                "id": referee.id,
                "title": referee.title,
                "first_name": referee.first_name,
                "last_name": referee.last_name,
                "gender": gender_reverse.get(referee.gender, 'Other'),
                "email": referee.email,
                "phone_number": referee.phone_number,
                "referee_type": referee.referee_type,
                "created_at": referee.created_at.isoformat() if referee.created_at else None
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error creating referee: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Failed to create referee: {str(e)}"
        }


@router.put("/referees/{referee_id}", response={200: dict, 401: dict, 404: dict})
@router.put("/referees/{referee_id}/", response={200: dict, 401: dict, 404: dict})
def update_referee_direct(request, referee_id: int, data: RefereeSchema):
    """Update an existing referee for the authenticated user"""
    try:
        user = get_user_from_token(request)
        
        from .models import Referee
        
        try:
            referee = Referee.objects.get(id=referee_id, user=user)
        except Referee.DoesNotExist:
            return {
                "success": False,
                "message": "Referee not found"
            }
        
        # Validate required fields
        if not data.first_name or not data.first_name.strip():
            return {
                "success": False,
                "message": "First name is required"
            }
        
        if not data.last_name or not data.last_name.strip():
            return {
                "success": False,
                "message": "Last name is required"
            }
        
        # Validate email format
        if not data.email or '@' not in data.email or '.' not in data.email:
            return {
                "success": False,
                "message": "Invalid email format"
            }
        
        # Validate phone number
        if not data.phone_number or len(data.phone_number) < 10:
            return {
                "success": False,
                "message": "Phone number must be at least 10 digits"
            }
        
        # Map gender
        gender_mapping = {
            'Male': 'M',
            'Female': 'F',
            'Non-binary': 'NB',
            'Prefer not to say': 'O',
            'Other': 'OT',
        }
        
        db_gender = gender_mapping.get(data.gender, 'O')
        
        # Update referee
        referee.title = data.title
        referee.first_name = data.first_name.strip()
        referee.last_name = data.last_name.strip()
        referee.gender = db_gender
        referee.email = data.email.strip()
        referee.phone_number = data.phone_number.strip()
        referee.referee_type = data.referee_type
        referee.save()
        
        gender_reverse = {v: k for k, v in gender_mapping.items()}
        
        return {
            "success": True,
            "message": "Referee updated successfully",
            "data": {
                "id": referee.id,
                "title": referee.title,
                "first_name": referee.first_name,
                "last_name": referee.last_name,
                "gender": gender_reverse.get(referee.gender, 'Other'),
                "email": referee.email,
                "phone_number": referee.phone_number,
                "referee_type": referee.referee_type,
                "updated_at": referee.updated_at.isoformat() if referee.updated_at else None
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error updating referee: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to update referee: {str(e)}"
        }


@router.delete("/referees/{referee_id}", response={200: dict, 401: dict, 404: dict})
@router.delete("/referees/{referee_id}/", response={200: dict, 401: dict, 404: dict})
def delete_referee_direct(request, referee_id: int):
    """Delete a referee for the authenticated user"""
    try:
        user = get_user_from_token(request)
        
        from .models import Referee
        
        try:
            referee = Referee.objects.get(id=referee_id, user=user)
        except Referee.DoesNotExist:
            return {
                "success": False,
                "message": "Referee not found"
            }
        
        referee_name = referee.get_full_name()
        referee.delete()
        
        return {
            "success": True,
            "message": f"Referee '{referee_name}' deleted successfully",
            "data": None
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error deleting referee: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to delete referee: {str(e)}"
        }


# ==================== ADMIN FEES ENDPOINTS ====================

@router.get("/admin/fees", response={200: dict, 401: dict})
@router.get("/admin/fees/", response={200: dict, 401: dict})
def get_all_fees(request):
    """Get all fee submissions for admin"""
    try:
        user = get_user_from_token(request)
        
        # Check if user is admin (you can add admin check here)
        # For now, allow all authenticated users
        
        fees_list = []
        
        # Get all fee payments from the database
        from .models import FeePayment
        
        fee_payments = FeePayment.objects.select_related('user').all().order_by('-uploaded_at')
        
        for fee_payment in fee_payments:
            user_obj = fee_payment.user
            
            # Get applicant name
            try:
                applicant = Applicant.objects.get(user=user_obj)
                applicant_name = f"{applicant.first_name} {applicant.last_name}".strip() or user_obj.username
                programme = applicant.selected_programme_name or applicant.program or "Not specified"
            except Applicant.DoesNotExist:
                applicant_name = user_obj.username
                programme = "Not specified"
            
            # Get fee status
            status = fee_payment.status
            
            # Construct deposit slip URL
            deposit_slip_url = None
            if fee_payment.deposit_slip_path:
                deposit_slip_url = f"/media/{fee_payment.deposit_slip_path}"
            
            fees_list.append({
                "id": fee_payment.id,
                "user_id": user_obj.id,
                "applicant_name": applicant_name,
                "programme": programme,
                "amount": float(fee_payment.amount),
                "status": status,
                "deposit_slip": deposit_slip_url,
                "paid_at": fee_payment.uploaded_at.isoformat() if fee_payment.uploaded_at else None,
                "email": user_obj.email,
            })
        
        return {
            "success": True,
            "message": f"Found {len(fees_list)} fee submissions",
            "data": fees_list,
            "count": len(fees_list)
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error fetching fees: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": str(e),
            "data": []
        }, 400

from django.views.decorators.csrf import csrf_exempt
from ninja.security import django_auth

# For the specific endpoint, you can disable CSRF by using @csrf_exempt
# Or better, use the correct URL pattern

@router.patch("/application-fees/{fee_id}/status", auth=None)  # Disable auth for this endpoint or use your JWT auth
@router.patch("/application-fees/{fee_id}/status/", auth=None)
def update_fee_status(request, fee_id: int):
    """Update fee payment status"""
    try:
        # Get user from token instead of session
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return {"success": False, "message": "No authorization token"}, 401
        
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return {"success": False, "message": "Invalid authorization header"}, 401
        
        token = parts[1]
        payload = decode_jwt_token(token)
        if not payload:
            return {"success": False, "message": "Invalid or expired token"}, 401
        
        try:
            user = User.objects.get(id=payload['user_id'])
        except User.DoesNotExist:
            return {"success": False, "message": "User not found"}, 401
        
        import json
        body = json.loads(request.body) if request.body else {}
        new_status = body.get('status')
        
        if not new_status:
            return {"success": False, "message": "Status is required"}, 400
        
        valid_statuses = ['pending', 'accepted', 'rejected', 'approved', 'processing', 'verified']
        if new_status not in valid_statuses:
            return {"success": False, "message": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}, 400
        
        from .models import FeePayment
        
        try:
            fee_payment = FeePayment.objects.get(id=fee_id)
        except FeePayment.DoesNotExist:
            return {"success": False, "message": f"Fee payment with ID {fee_id} not found"}, 404
        
        fee_payment.status = new_status
        fee_payment.save()
        
        # Create notification for the user
        try:
            from .models import Notification
            
            status_messages = {
                'accepted': 'Your fee payment has been accepted!',
                'approved': 'Your fee payment has been approved!',
                'rejected': 'Your fee payment was rejected. Please contact admissions.',
                'verified': 'Your fee payment has been verified!',
                'processing': 'Your fee payment is being processed.',
            }
            
            message = status_messages.get(new_status, f'Your fee payment status has been updated to {new_status}')
            
            Notification.objects.create(
                user=fee_payment.user,
                title="Fee Payment Status Update",
                message=message,
                notification_type="payment",
                is_read=False,
                link="/dashboard/fees"
            )
            print(f"✅ Notification created for user {fee_payment.user.username}")
        except Exception as notif_error:
            print(f"⚠️ Could not create notification: {notif_error}")
        
        return {
            "success": True,
            "message": f"Fee status updated to {new_status}",
            "data": {
                "id": fee_payment.id,
                "user_id": fee_payment.user.id,
                "status": fee_payment.status
            }
        }
        
    except Exception as e:
        print(f"Error updating fee status: {str(e)}")
        return {"success": False, "message": str(e)}, 400        



# ==================== NOTIFICATION PREFERENCES ENDPOINTS ====================

class NotificationPreferencesSchema(Schema):
    email_notifications: bool
    application_updates: bool
    deadline_reminders: bool
    promotional_emails: bool

@router.get("/notification-preferences", response={200: dict, 401: dict})
@router.get("/notification-preferences/", response={200: dict, 401: dict})
def get_notification_preferences(request):
    """Get user's notification preferences"""
    try:
        user = get_user_from_token(request)
        
        from .models import NotificationPreference
        
        try:
            prefs = NotificationPreference.objects.get(user=user)
            return {
                "success": True,
                "message": "Preferences retrieved",
                "data": {
                    "email_notifications": prefs.email_notifications,
                    "application_updates": prefs.application_updates,
                    "deadline_reminders": prefs.deadline_reminders,
                    "promotional_emails": prefs.promotional_emails
                }
            }
        except NotificationPreference.DoesNotExist:
            # Return default preferences
            return {
                "success": True,
                "message": "Using default preferences",
                "data": {
                    "email_notifications": True,
                    "application_updates": True,
                    "deadline_reminders": True,
                    "promotional_emails": False
                }
            }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error getting preferences: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

@router.put("/notification-preferences", response={200: dict, 401: dict})
@router.put("/notification-preferences/", response={200: dict, 401: dict})
def update_notification_preferences(request, data: NotificationPreferencesSchema):
    """Update user's notification preferences"""
    try:
        user = get_user_from_token(request)
        
        from .models import NotificationPreference
        
        prefs, created = NotificationPreference.objects.update_or_create(
            user=user,
            defaults={
                'email_notifications': data.email_notifications,
                'application_updates': data.application_updates,
                'deadline_reminders': data.deadline_reminders,
                'promotional_emails': data.promotional_emails
            }
        )
        
        return {
            "success": True,
            "message": "Preferences updated successfully",
            "data": {
                "email_notifications": prefs.email_notifications,
                "application_updates": prefs.application_updates,
                "deadline_reminders": prefs.deadline_reminders,
                "promotional_emails": prefs.promotional_emails
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error updating preferences: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to update preferences: {str(e)}"
        }

# ==================== CHANGE PASSWORD ENDPOINT ====================

class ChangePasswordSchema(Schema):
    current_password: str
    new_password: str

@router.post("/change-password", response={200: dict, 400: dict, 401: dict})
@router.post("/change-password/", response={200: dict, 400: dict, 401: dict})
def change_password(request, data: ChangePasswordSchema):
    """Change user's password"""
    try:
        user = get_user_from_token(request)
        
        # Check current password
        if not user.check_password(data.current_password):
            return {
                "success": False,
                "message": "Current password is incorrect"
            }
        
        # Validate new password length
        if len(data.new_password) < 8:
            return {
                "success": False,
                "message": "New password must be at least 8 characters"
            }
        
        # Change password
        user.set_password(data.new_password)
        user.save()
        
        # Log the password change
        from .models import UserActivityLog, AuditLog
        UserActivityLog.objects.create(
            user=user,
            action="password_changed",
            details="Password changed successfully",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        AuditLog.objects.create(
            user=user,
            action="password_change",
            resource_type="User",
            resource_id=user.id,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return {
            "success": True,
            "message": "Password changed successfully"
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error changing password: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to change password: {str(e)}"
        }


# ==================== USER PROFILE SETTINGS ENDPOINTS ====================

class ProfileSettingsSchema(Schema):
    theme: str
    font_size: str
    language: Optional[str] = 'en'
    timezone: Optional[str] = 'UTC'

@router.get("/profile-settings", response={200: dict, 401: dict})
@router.get("/profile-settings/", response={200: dict, 401: dict})
def get_profile_settings(request):
    """Get user's profile settings (theme, font size, etc.)"""
    try:
        user = get_user_from_token(request)
        
        from .models import UserProfileSettings
        
        try:
            settings = UserProfileSettings.objects.get(user=user)
            return {
                "success": True,
                "message": "Settings retrieved",
                "data": {
                    "theme": settings.theme,
                    "font_size": settings.font_size,
                    "language": settings.language,
                    "timezone": settings.timezone
                }
            }
        except UserProfileSettings.DoesNotExist:
            # Return default settings
            return {
                "success": True,
                "message": "Using default settings",
                "data": {
                    "theme": "light",
                    "font_size": "medium",
                    "language": "en",
                    "timezone": "UTC"
                }
            }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error getting profile settings: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

@router.put("/profile-settings", response={200: dict, 401: dict})
@router.put("/profile-settings/", response={200: dict, 401: dict})
def update_profile_settings(request, data: ProfileSettingsSchema):
    """Update user's profile settings"""
    try:
        user = get_user_from_token(request)
        
        from .models import UserProfileSettings
        
        settings, created = UserProfileSettings.objects.update_or_create(
            user=user,
            defaults={
                'theme': data.theme,
                'font_size': data.font_size,
                'language': data.language,
                'timezone': data.timezone
            }
        )
        
        return {
            "success": True,
            "message": "Settings updated successfully",
            "data": {
                "theme": settings.theme,
                "font_size": settings.font_size,
                "language": settings.language,
                "timezone": settings.timezone
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error updating profile settings: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to update settings: {str(e)}"
        }


# ==================== SESSION MANAGEMENT ENDPOINTS ====================

@router.get("/sessions", response={200: dict, 401: dict})
@router.get("/sessions/", response={200: dict, 401: dict})
def get_user_sessions(request):
    """Get all active sessions for the user"""
    try:
        user = get_user_from_token(request)
        
        from .models import UserSession
        
        sessions = UserSession.objects.filter(user=user, is_active=True).order_by('-last_activity')
        
        sessions_data = []
        for session in sessions:
            sessions_data.append({
                "id": session.id,
                "session_key": session.session_key[:20] + "...",
                "device_info": session.device_info,
                "last_activity": session.last_activity.isoformat(),
                "created_at": session.created_at.isoformat(),
                "is_current": False  # You'll need to track current session
            })
        
        return {
            "success": True,
            "message": "Sessions retrieved",
            "data": sessions_data,
            "count": len(sessions_data)
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error getting sessions: {str(e)}")
        return {
            "success": True,
            "message": "No active sessions",
            "data": [],
            "count": 0
        }

@router.post("/sessions/logout-others", response={200: dict, 401: dict})
@router.post("/sessions/logout-others/", response={200: dict, 401: dict})
def logout_other_sessions(request):
    """Logout all other sessions for the user"""
    try:
        user = get_user_from_token(request)
        
        from .models import UserSession
        
        # Get current session key from request
        auth_header = request.headers.get('Authorization')
        current_session_key = auth_header[-32:] if auth_header else None
        
        # Deactivate all other sessions
        updated_count = UserSession.objects.filter(
            user=user, 
            is_active=True
        ).exclude(
            session_key=current_session_key
        ).update(is_active=False)
        
        # Log the action
        from .models import UserActivityLog
        UserActivityLog.objects.create(
            user=user,
            action="logged_out_other_sessions",
            details=f"Logged out {updated_count} other sessions",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return {
            "success": True,
            "message": f"Logged out {updated_count} other sessions",
            "data": {
                "logged_out_count": updated_count
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error logging out other sessions: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to logout other sessions: {str(e)}"
        }


# ==================== DELETE ACCOUNT ENDPOINT ====================

class DeleteAccountSchema(Schema):
    confirmation: bool
    password: Optional[str] = None

@router.post("/delete-account", response={200: dict, 400: dict, 401: dict})
@router.post("/delete-account/", response={200: dict, 400: dict, 401: dict})
def delete_account(request, data: DeleteAccountSchema):
    """Permanently delete user account"""
    try:
        user = get_user_from_token(request)
        
        if not data.confirmation:
            return {
                "success": False,
                "message": "You must confirm account deletion"
            }
        
        # Verify password if provided
        if data.password and not user.check_password(data.password):
            return {
                "success": False,
                "message": "Incorrect password"
            }
        
        # Log the deletion before deleting
        from .models import AuditLog, UserActivityLog
        AuditLog.objects.create(
            user=user,
            action="account_deletion",
            resource_type="User",
            resource_id=user.id,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        UserActivityLog.objects.create(
            user=user,
            action="account_deleted",
            details="Account permanently deleted",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Store user email for response
        user_email = user.email
        username = user.username
        
        # Delete user (this will cascade delete related models if on_delete=CASCADE is set)
        user.delete()
        
        return {
            "success": True,
            "message": "Your account has been permanently deleted",
            "data": {
                "email": user_email,
                "username": username
            }
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error deleting account: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Failed to delete account: {str(e)}"
        }


# ==================== USER ACTIVITY LOGS ENDPOINT ====================

@router.get("/activity-logs", response={200: dict, 401: dict})
@router.get("/activity-logs/", response={200: dict, 401: dict})
def get_user_activity_logs(request):
    """Get user's activity logs"""
    try:
        user = get_user_from_token(request)
        
        from .models import UserActivityLog
        
        logs = UserActivityLog.objects.filter(user=user).order_by('-created_at')[:50]
        
        logs_data = []
        for log in logs:
            logs_data.append({
                "id": log.id,
                "action": log.action,
                "details": log.details,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat(),
                "time_ago": get_time_ago(log.created_at) if hasattr(log.created_at, 'strftime') else "recent"
            })
        
        return {
            "success": True,
            "message": "Activity logs retrieved",
            "data": logs_data,
            "count": len(logs_data)
        }
        
    except HttpError:
        raise
    except Exception as e:
        print(f"Error getting activity logs: {str(e)}")
        return {
            "success": True,
            "message": "No activity logs found",
            "data": [],
            "count": 0
        }



api.add_router("/ml", ml_router)
api.add_router("/", router)