from ninja import NinjaAPI, Router, Schema
from ninja.errors import HttpError
from typing import Optional, List
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.conf import settings
import jwt
from datetime import datetime, timedelta, timezone
from .models import Applicant, NextOfKin

api = NinjaAPI()
router = Router()

# ==================== SCHEMAS ====================

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

class PersonalDetailsSchema(Schema):
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    address: Optional[str] = None
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
        
        # Find user
        if '@' in data.email_or_username:
            try:
                user = User.objects.get(email=data.email_or_username)
            except User.DoesNotExist:
                print(f"❌ No user with email: {data.email_or_username}")
                raise HttpError(401, "Invalid credentials")
        else:
            try:
                user = User.objects.get(username=data.email_or_username)
            except User.DoesNotExist:
                print(f"❌ No user with username: {data.email_or_username}")
                raise HttpError(401, "Invalid credentials")
        
        # Authenticate
        if user.check_password(data.password):
            token = create_jwt_token(user)
            
            print(f"✅ Login successful for: {user.username}")
            
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
            print(f"❌ Authentication failed for: {user.username}")
            raise HttpError(401, "Invalid credentials")
            
    except HttpError:
        raise
    except Exception as e:
        print(f"💥 Login error: {str(e)}")
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

# ==================== PERSONAL DETAILS ENDPOINTS ====================

@router.post("/personal-details", response={200: dict, 401: dict})
@router.post("/personal-details/", response={200: dict, 401: dict})
def save_personal_details(request, data: PersonalDetailsSchema):
    try:
        user = get_user_from_token(request)
        
        user.first_name = data.first_name
        user.last_name = data.last_name
        user.email = data.email
        user.save()
        
        applicant, created = Applicant.objects.get_or_create(user=user)
        applicant.first_name = data.first_name
        applicant.last_name = data.last_name
        applicant.email = data.email
        applicant.phone = data.phone or ""
        applicant.date_of_birth = data.date_of_birth if data.date_of_birth else None
        applicant.gender = data.gender or ""
        applicant.nationality = data.nationality or ""
        applicant.national_id = data.national_id or ""
        applicant.home_district = data.home_district or ""
        applicant.physical_address = data.physical_address or data.address or ""
        applicant.save()
        
        return {
            "success": True,
            "message": "Personal details saved successfully",
            "data": {
                "first_name": applicant.first_name,
                "last_name": applicant.last_name,
                "email": applicant.email,
                "phone": applicant.phone
            }
        }
    except HttpError:
        raise
    except Exception as e:
        print(f"Error saving personal details: {str(e)}")
        raise HttpError(500, f"Failed to save: {str(e)}")

@router.get("/personal-details", response={200: dict, 401: dict})
@router.get("/personal-details/", response={200: dict, 401: dict})
def get_personal_details(request):
    try:
        user = get_user_from_token(request)
        
        try:
            applicant = Applicant.objects.get(user=user)
            data = {
                "first_name": applicant.first_name,
                "last_name": applicant.last_name,
                "email": applicant.email,
                "phone": applicant.phone,
                "date_of_birth": applicant.date_of_birth,
                "gender": applicant.gender,
                "nationality": applicant.nationality,
                "national_id": applicant.national_id,
                "home_district": applicant.home_district,
                "physical_address": applicant.physical_address
            }
        except Applicant.DoesNotExist:
            data = {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone": "",
                "date_of_birth": None,
                "gender": "",
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
        print(f"Error fetching personal details: {str(e)}")
        raise HttpError(500, f"Failed to fetch: {str(e)}")

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
        print(f"Error fetching next of kin: {str(e)}")
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

# Add router to API
api.add_router("/", router)