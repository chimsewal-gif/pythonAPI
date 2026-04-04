from ninja import ModelSchema, Schema
from django.contrib.auth.models import User
from pydantic import field_validator, Field, ValidationInfo
from typing import Optional, List
from datetime import datetime
from .models import Item 

# Programme Schema
class ProgrammeSchema(Schema):
    id: int
    name: str
    description: Optional[str] = None
    department: Optional[str] = None
    duration: Optional[str] = None
    category: Optional[str] = None

class ProgrammesResponse(Schema):
    success: bool
    data: List[ProgrammeSchema]
    message: Optional[str] = None
    count: Optional[int] = None

# Department Schema
class DepartmentSchema(Schema):
    id: int
    name: str
    code: str
    description: Optional[str] = None
    head_of_department: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    established_date: Optional[str] = None
    is_active: Optional[bool] = True

class DepartmentsResponse(Schema):
    success: bool
    data: List[DepartmentSchema]
    message: Optional[str] = None
    count: Optional[int] = None

# Item Schema
class ItemSchema(ModelSchema):
    class Meta:
        model = Item
        fields = ['id', 'name', 'description']

# NEXT OF KIN SCHEMAS - SIMPLIFIED VERSION
class NextOfKinSchema(Schema):
    title: str = Field(..., min_length=1, max_length=10)
    relationship: str = Field(..., min_length=1, max_length=50)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    mobile1: str = Field(..., min_length=1, max_length=20)
    mobile2: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    address: str = Field(..., min_length=1)

class NextOfKinResponseSchema(Schema):
    id: int
    title: str
    relationship: str
    first_name: str
    last_name: str
    mobile1: str
    mobile2: Optional[str]
    email: Optional[str]
    address: str
    user_id: int
    created_at: Optional[str]
    updated_at: Optional[str]

class NextOfKinsResponse(Schema):
    success: bool
    data: Optional[List[NextOfKinResponseSchema]]
    message: str
    count: Optional[int]

# Personal Details Schema
class PersonalDetailsSchema(Schema):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    gender: str
    date_of_birth: str
    nationality: str
    national_id: str
    home_district: str
    physical_address: str
    email: str
    phone: str
    
    @field_validator('gender')
    @classmethod
    def validate_gender(cls, v: str) -> str:
        valid_genders = ['Male', 'Female', 'Other']
        if v not in valid_genders:
            raise ValueError(f'Gender must be one of {valid_genders}')
        return v
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        if '@' not in v:
            raise ValueError('Invalid email address')
        return v

# Update Role Schema
class UpdateRoleSchema(Schema):
    role: str
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = ['odl', 'postgraduate', 'diploma', 'international', 'weekend', 'masters']
        if v not in valid_roles:
            raise ValueError(f'Role must be one of {valid_roles}')
        return v

# Auth Schemas
class UserRegistrationSchema(Schema):
    username: str = Field(..., min_length=4, max_length=150)
    email: str
    password: str = Field(..., min_length=8)
    password_confirm: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    @field_validator('username')
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace('_', '').replace('.', '').isalnum():
            raise ValueError('Username must be alphanumeric')
        return v

    @field_validator('password_confirm')
    @classmethod
    def passwords_match(cls, v: str, info: ValidationInfo) -> str:
        if 'password' in info.data and v != info.data['password']:
            raise ValueError('Passwords do not match')
        return v

class UserResponseSchema(Schema):
    id: int
    username: str
    email: str
    first_name: str
    last_name: str

class LoginSchema(Schema):
    username: str
    password: str

class AuthResponseSchema(Schema):
    success: bool
    message: str
    user: Optional[UserResponseSchema] = None

# Current User Response Schema
class CurrentUserResponseSchema(Schema):
    id: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_authenticated: bool

class ApplicantSchema(Schema):
    id: int
    firstname: str
    lastname: str
    email: str
    phone: Optional[str] = None
    program: str
    status: str
    application_date: Optional[datetime] = None

class ApplicantsResponse(Schema):
    success: bool
    data: List[ApplicantSchema]
    message: Optional[str] = None
    count: Optional[int] = None

# Dashboard Statistics Schema
class DashboardStatsSchema(Schema):
    totalApplicants: int
    totalApplications: int
    totalFees: float
    totalProgrammes: int
    todayApplications: Optional[int] = 0
    pendingApplications: Optional[int] = 0
    recentApplicants: Optional[int] = 0
    totalPaidFees: Optional[float] = 0.0
    totalPendingFees: Optional[float] = 0.0
    currency: Optional[str] = "MWK"
    lastUpdated: Optional[str] = None
    isDemoData: Optional[bool] = False

class DashboardStatsResponse(Schema):
    success: bool
    data: Optional[DashboardStatsSchema] = None
    message: str