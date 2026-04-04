from ninja import NinjaAPI, Router, Schema
from ninja.errors import HttpError
from typing import Optional, List
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.conf import settings
import jwt
from datetime import datetime, timedelta, timezone
from .models import Applicant, NextOfKin, SubjectRecord, Department

api = NinjaAPI()
router = Router()

# ==================== SCHEMAS ====================

class SubjectRecordSchema(Schema):
    qualification: str
    centre_number: str
    exam_number: str
    subject: str
    grade: str
    year: str

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
        
        return 201, {
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
        
        # Update User model
        user.first_name = data.first_name
        user.last_name = data.last_name
        user.email = data.email
        user.save()
        print("User model updated")
        
        # Get or create Applicant profile
        applicant, created = Applicant.objects.get_or_create(user=user)
        print(f"Applicant {'created' if created else 'retrieved'}")
        
        # Update applicant fields
        applicant.first_name = data.first_name
        applicant.middle_name = data.middle_name or ""
        applicant.last_name = data.last_name
        applicant.email = data.email
        applicant.phone = data.phone or ""
        
        # Convert gender from string to model choice
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
        
        # Handle date of birth
        if data.date_of_birth:
            applicant.date_of_birth = data.date_of_birth
        
        # Update other fields
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
        
        # Return success response with converted gender back for frontend
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
        }, 500



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
        }, 500







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

# Test endpoint
@router.get("/test", response={200: dict})
@router.get("/test/", response={200: dict})
def test_endpoint(request):
    return {
        "status": "success",
        "message": "API is working!",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }



    # Add this with your other schemas (around line 50)
class VerifyTokenResponse(Schema):
    success: bool
    message: str
    user: Optional[dict] = None

# Add these endpoints after your test endpoint (around line 500)
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
        }, 401
    except Exception as e:
        return {
            "valid": False,
            "success": False,
            "message": f"Error: {str(e)}"
        }, 401



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
        
        # Validate year
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
        
        # Validate year
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





# ==================== APPLICANT MANAGEMENT ENDPOINTS ====================

@router.get("/applicants", response={200: dict, 401: dict})
@router.get("/applicants/", response={200: dict, 401: dict})
def get_applicants(request):
    """Get all applicants (admin only)"""
    try:
        # Check if user is authenticated
        user = get_user_from_token(request)
        
        # Optional: Check if user is admin/staff
        # if not user.is_staff and not user.is_superuser:
        #     raise HttpError(403, "Admin access required")
        
        # Get all users with their applicant profiles
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
                # User exists but no applicant profile
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
        }, 500


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
        }, 500


@router.put("/applicants/{applicant_id}", response={200: dict, 404: dict, 401: dict})
@router.put("/applicants/{applicant_id}/", response={200: dict, 404: dict, 401: dict})
def update_applicant_status(request, applicant_id: int, status: str):
    """Update applicant status"""
    try:
        user = get_user_from_token(request)
        
        # Check if user is admin
        # if not user.is_staff and not user.is_superuser:
        #     raise HttpError(403, "Admin access required")
        
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
        }, 500










        # ==================== DEPARTMENT SCHEMAS ====================

class DepartmentSchema(Schema):
    name: str
    code: str
    description: Optional[str] = None
    head_of_department: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    established_date: Optional[str] = None
    is_active: bool = True

class DepartmentResponse(Schema):
    id: int
    name: str
    code: str
    description: Optional[str] = None
    head_of_department: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    established_date: Optional[str] = None
    is_active: bool
    created_at: str
    updated_at: str

# ==================== DEPARTMENT ENDPOINTS ====================

@router.get("/departments", response={200: dict, 401: dict})
@router.get("/departments/", response={200: dict, 401: dict})
def get_departments(request):
    """Get all departments"""
    try:
        # Check authentication
        user = get_user_from_token(request)
        
        # Optional: Check if user is admin/staff
        # if not user.is_staff and not user.is_superuser:
        #     raise HttpError(403, "Admin access required")
        
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
        }, 500

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
        }, 500

@router.post("/departments", response={201: dict, 400: dict, 401: dict})
@router.post("/departments/", response={201: dict, 400: dict, 401: dict})
def create_department(request, data: DepartmentSchema):
    """Create a new department"""
    try:
        user = get_user_from_token(request)
        
        # Check if department with same name or code exists
        if Department.objects.filter(name=data.name).exists():
            raise HttpError(400, f"Department with name '{data.name}' already exists")
        
        if Department.objects.filter(code=data.code).exists():
            raise HttpError(400, f"Department with code '{data.code}' already exists")
        
        # Parse established date if provided
        established_date = None
        if data.established_date:
            try:
                established_date = datetime.strptime(data.established_date, "%Y-%m-%d").date()
            except ValueError:
                raise HttpError(400, "Invalid date format. Use YYYY-MM-DD")
        
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
        
        return 201, {
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
        }, 500

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
        
        # Check if name is taken by another department
        if Department.objects.filter(name=data.name).exclude(id=department_id).exists():
            raise HttpError(400, f"Department with name '{data.name}' already exists")
        
        # Check if code is taken by another department
        if Department.objects.filter(code=data.code).exclude(id=department_id).exists():
            raise HttpError(400, f"Department with code '{data.code}' already exists")
        
        # Parse established date if provided
        established_date = None
        if data.established_date:
            try:
                established_date = datetime.strptime(data.established_date, "%Y-%m-%d").date()
            except ValueError:
                raise HttpError(400, "Invalid date format. Use YYYY-MM-DD")
        
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
        }, 500

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
        
        # Check if department has any programmes
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
        }, 500



# Add router to API
api.add_router("/", router)