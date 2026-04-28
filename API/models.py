from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Item model - Keep only one instance
class Item(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

# Department model - Keep only one instance
class Department(models.Model):
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True, null=True)
    head_of_department = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    established_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    class Meta:
        db_table = 'departments'
        ordering = ['name']

# Applicant model - Keep only one instance with updated fields including document fields and ML fields
class Applicant(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('submitted', 'Submitted'),
    ]
    
    PROGRAM_CHOICES = [
        ('odl', 'ODL Student Application'),
        ('postgraduate', 'Postgraduate Application'),
        ('diploma', 'Diploma/Certificate Programs'),
        ('international', 'International Student Application'),
        ('weekend', 'Weekend Program'),
        ('masters', 'Masters Program'),
    ]
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='applicant_profile')
    first_name = models.CharField(max_length=100, blank=True)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    national_id = models.CharField(max_length=50, blank=True)
    home_district = models.CharField(max_length=100, blank=True)
    physical_address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    program = models.CharField(max_length=50, choices=PROGRAM_CHOICES, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    application_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reference_number = models.CharField(max_length=100, blank=True, null=True, unique=True)
    
    # Document fields
    msce = models.CharField(max_length=500, blank=True, null=True)
    msce_size = models.IntegerField(blank=True, null=True)
    msce_name = models.CharField(max_length=255, blank=True, null=True)
    
    id_card = models.CharField(max_length=500, blank=True, null=True)
    id_card_size = models.IntegerField(blank=True, null=True)
    id_card_name = models.CharField(max_length=255, blank=True, null=True)
    
    payment_proof = models.CharField(max_length=500, blank=True, null=True)
    payment_proof_size = models.IntegerField(blank=True, null=True)
    payment_proof_name = models.CharField(max_length=255, blank=True, null=True)
    
    # Programme selection fields
    selected_programme = models.ForeignKey(
        'Programme', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='selected_by_applicants'
    )
    selected_programme_name = models.CharField(max_length=255, blank=True, null=True)
    selected_programme_department = models.CharField(max_length=255, blank=True, null=True)
    selected_programme_duration = models.CharField(max_length=100, blank=True, null=True)
    selected_programme_category = models.CharField(max_length=100, blank=True, null=True)
    selected_programme_code = models.CharField(max_length=50, blank=True, null=True)
    selection_date = models.DateTimeField(default=timezone.now, null=True)
    
    # ========== ML PREDICTION FIELDS ==========
    ml_decision = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        help_text="ML decision: 'approve', 'reject', or 'review'"
    )
    ml_confidence = models.FloatField(
        blank=True, 
        null=True,
        help_text="ML confidence score (0.0 to 1.0)"
    )
    ml_probability = models.FloatField(
        blank=True, 
        null=True,
        help_text="Success probability (0.0 to 1.0)"
    )
    ml_priority = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        help_text="Priority level: 'High', 'Medium', or 'Low'"
    )
    ml_factors = models.JSONField(
        blank=True, 
        null=True,
        help_text="JSON object storing reasons and risk factors"
    )
    ml_recommendation = models.TextField(
        blank=True, 
        null=True,
        help_text="ML recommendation text"
    )
    ml_processed_at = models.DateTimeField(
        blank=True, 
        null=True,
        help_text="Timestamp when ML analysis was performed"
    )
    ml_raw_response = models.JSONField(
        blank=True, 
        null=True,
        help_text="Complete raw ML response JSON"
    )
    # ========================================
    
    def save(self, *args, **kwargs):
        # Ensure selection_date is timezone-aware when saving
        if self.selection_date and timezone.is_naive(self.selection_date):
            self.selection_date = timezone.make_aware(self.selection_date, timezone.get_current_timezone())
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    class Meta:
        db_table = 'applicants'

# Next of Kin Model
class NextOfKin(models.Model):
    TITLE_CHOICES = [
        ('Mr', 'Mr'),
        ('Mrs', 'Mrs'),
        ('Miss', 'Miss'),
        ('Dr', 'Dr'),
        ('Prof', 'Prof'),
    ]
    
    RELATIONSHIP_CHOICES = [
        ('Parent', 'Parent'),
        ('Sibling', 'Sibling'),
        ('Spouse', 'Spouse'),
        ('Guardian', 'Guardian'),
        ('Uncle', 'Uncle'),
        ('Aunt', 'Aunt'),
        ('Grandparent', 'Grandparent'),
        ('Other', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='next_of_kin')
    title = models.CharField(max_length=10, choices=TITLE_CHOICES)
    relationship = models.CharField(max_length=50, choices=RELATIONSHIP_CHOICES)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    mobile1 = models.CharField(max_length=20)
    mobile2 = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} {self.first_name} {self.last_name} ({self.relationship})"
    
    class Meta:
        db_table = 'next_of_kin'
        verbose_name = "Next of Kin"
        verbose_name_plural = "Next of Kin"
        ordering = ['-created_at']

# Programme model - Updated with study_mode and programme_type fields
class Programme(models.Model):
    CATEGORY_CHOICES = [
        ('undergraduate', 'Undergraduate'),
        ('postgraduate', 'Postgraduate'),
        ('diploma', 'Diploma'),
        ('certificate', 'Certificate'),
    ]
    
    STUDY_MODE_CHOICES = [
        ('full time', 'Full Time'),
        ('weekend', 'Weekend'),
        ('evening', 'Evening'),
        ('online', 'Online'),
        ('odel', 'ODeL'),
    ]
    
    PROGRAMME_TYPE_CHOICES = [
        ('upgrading', 'Upgrading'),
        ('non-generic', 'Non-Generic'),
        ('generic', 'Generic'),
    ]
    
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='programmes')
    school = models.CharField(max_length=200, blank=True, null=True, help_text="School/Faculty offering the programme")
    duration = models.CharField(max_length=50, blank=True, null=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='undergraduate')
    
    # Fields for type column display
    study_mode = models.CharField(
        max_length=20, 
        choices=STUDY_MODE_CHOICES, 
        blank=True, 
        null=True,
        help_text="Study mode: full time, weekend, evening, online, or odel"
    )
    programme_type = models.CharField(
        max_length=20, 
        choices=PROGRAMME_TYPE_CHOICES, 
        blank=True, 
        null=True,
        help_text="Type of programme: upgrading, non-generic, or generic"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.code} - {self.name}" if self.code else self.name
    
    class Meta:
        db_table = 'programmes'
        ordering = ['name']

# Application model for tracking program applications
class Application(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applications')
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name='applications')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.programme.name}"
    
    class Meta:
        db_table = 'applications'
        ordering = ['-created_at']
        unique_together = ['user', 'programme']

# FeeStatus model for tracking payment status (OneToOne with User)
class FeeStatus(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('accepted', 'Accepted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='fee_status')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.status}"
    
    class Meta:
        db_table = 'fee_statuses'
        verbose_name = "Fee Status"
        verbose_name_plural = "Fee Statuses"

# FeePayment model for tracking deposit slips (OneToOne with User)
class FeePayment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
        ('approved', 'Approved'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='fee_payment')
    deposit_slip_path = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=25000)
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.status} - {self.amount} MWK"
    
    class Meta:
        db_table = 'fee_payments'
        ordering = ['-uploaded_at']

# Subject Record model for high school academic records
class SubjectRecord(models.Model):
    QUALIFICATION_CHOICES = [
        ('MSCE', 'MSCE (Malawi School Certificate of Education)'),
        ('JCE', 'JCE (Junior Certificate of Education)'),
        ('O-Level', 'O-Level'),
        ('A-Level', 'A-Level'),
        ('IGCSE', 'IGCSE'),
        ('Other', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subject_records')
    qualification = models.CharField(max_length=100, choices=QUALIFICATION_CHOICES)
    centre_number = models.CharField(max_length=50)
    exam_number = models.CharField(max_length=50)
    subject = models.CharField(max_length=100)
    grade = models.CharField(max_length=10)
    year = models.CharField(max_length=4)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.subject} - {self.grade} ({self.year})"
    
    class Meta:
        db_table = 'subject_records'
        ordering = ['-year', 'subject']

class CommitteeMember(models.Model):
    name = models.CharField(max_length=200)
    role = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, null=True)
    department = models.CharField(max_length=200, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    profile_image = models.ImageField(upload_to='committee/', blank=True, null=True)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} - {self.role}"
    
    class Meta:
        db_table = 'committee_members'
        ordering = ['order', 'name']

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('application', 'Application Update'),
        ('payment', 'Payment Update'),
        ('system', 'System Notification'),
        ('reminder', 'Reminder'),
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='info')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    link = models.CharField(max_length=500, blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        db_table = 'notifications'
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"

class ProgrammeChoice(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='programme_choices')
    choice_number = models.IntegerField()
    programme_id = models.IntegerField()
    programme_name = models.CharField(max_length=500)
    department = models.CharField(max_length=200, blank=True)
    duration = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['choice_number']
        db_table = 'programme_choices'
        unique_together = ['user', 'choice_number']
    
    def __str__(self):
        return f"{self.user.username} - Choice {self.choice_number}: {self.programme_name}"

class Document(models.Model):
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE)
    document_name = models.CharField(max_length=255)
    document_type = models.CharField(max_length=100)
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    # Add missing fields that might be used
    title = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.document_name

class Education(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='education_records')
    qualification_type = models.CharField(max_length=100)
    institution = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    currently_studying = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.qualification_type} - {self.institution} ({self.user.username})"
    
    class Meta:
        db_table = 'education'
        ordering = ['-start_date']

class WorkHistory(models.Model):
    EMPLOYMENT_TYPE_CHOICES = [
        ('Full-time', 'Full-time'),
        ('Part-time', 'Part-time'),
        ('Contract', 'Contract'),
        ('Internship', 'Internship'),
        ('Temporary', 'Temporary'),
        ('Freelance', 'Freelance'),
        ('Self-employed', 'Self-employed'),
        ('Volunteer', 'Volunteer'),
    ]
    
    LOCATION_TYPE_CHOICES = [
        ('On-site', 'On-site'),
        ('Remote', 'Remote'),
        ('Hybrid', 'Hybrid'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='work_history')
    organization = models.CharField(max_length=255)
    job_title = models.CharField(max_length=255)
    employment_type = models.CharField(max_length=50, choices=EMPLOYMENT_TYPE_CHOICES, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    location_type = models.CharField(max_length=50, choices=LOCATION_TYPE_CHOICES, blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    currently_working = models.BooleanField(default=False)
    responsibilities = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.job_title} at {self.organization} ({self.user.username})"
    
    class Meta:
        db_table = 'work_history'
        ordering = ['-start_date']
        verbose_name = 'Work History'
        verbose_name_plural = 'Work History'

class Publication(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='publications')
    title = models.CharField(max_length=500)
    journal = models.CharField(max_length=500)
    year = models.CharField(max_length=4)
    link = models.URLField(blank=True, null=True)
    authors = models.TextField(blank=True, null=True)
    doi = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} ({self.year})"
    
    class Meta:
        db_table = 'publications'
        ordering = ['-year']
        verbose_name = 'Publication'
        verbose_name_plural = 'Publications'

class Essay(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='essays')
    motivation = models.TextField(help_text="Motivation for applying to the programme (Max 500 words)")
    research_concept_note = models.TextField(blank=True, null=True, help_text="Research concept note for PhD and Research Masters students (Max 1000 words)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Essay for {self.user.username}"
    
    class Meta:
        db_table = 'essays'
        verbose_name = 'Essay'
        verbose_name_plural = 'Essays'

class Referee(models.Model):
    TITLE_CHOICES = [
        ('Mr', 'Mr'),
        ('Mrs', 'Mrs'),
        ('Miss', 'Miss'),
        ('Ms', 'Ms'),
        ('Dr', 'Dr'),
        ('Prof', 'Prof'),
        ('Mx', 'Mx'),
    ]
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('NB', 'Non-binary'),
        ('O', 'Prefer not to say'),
        ('OT', 'Other'),
    ]
    
    REFEREE_TYPE_CHOICES = [
        ('Academic', 'Academic'),
        ('Professional', 'Professional'),
        ('Personal', 'Personal'),
        ('Supervisor', 'Supervisor'),
        ('Manager', 'Manager'),
        ('Colleague', 'Colleague'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referees')
    title = models.CharField(max_length=10, choices=TITLE_CHOICES)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    referee_type = models.CharField(max_length=50, choices=REFEREE_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} {self.first_name} {self.last_name} ({self.referee_type})"
    
    def get_full_name(self):
        return f"{self.title} {self.first_name} {self.last_name}"
    
    class Meta:
        db_table = 'referees'
        ordering = ['-created_at']
        verbose_name = 'Referee'
        verbose_name_plural = 'Referees'


# ==================== SETTINGS MODELS ====================

class NotificationPreference(models.Model):
    """Store user notification preferences"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    email_notifications = models.BooleanField(default=True)
    application_updates = models.BooleanField(default=True)
    deadline_reminders = models.BooleanField(default=True)
    promotional_emails = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_preferences'
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
    
    def __str__(self):
        return f"{self.user.username}'s preferences"


class UserSession(models.Model):
    """Track user sessions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=255)
    device_info = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    last_activity = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'user_sessions'
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
        ordering = ['-last_activity']
    
    def __str__(self):
        return f"{self.user.username} - {self.session_key[:20]}"


class PasswordResetToken(models.Model):
    """Store password reset tokens"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reset_tokens')
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'password_reset_tokens'
    
    def __str__(self):
        return f"Reset token for {self.user.username}"
    
    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()


class UserActivityLog(models.Model):
    """Log user activities for security"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    action = models.CharField(max_length=100)
    details = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'user_activity_logs'
        verbose_name = 'User Activity Log'
        verbose_name_plural = 'User Activity Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.created_at}"


class UserProfileSettings(models.Model):
    """Store user profile settings (theme, font size, etc.)"""
    THEME_CHOICES = [
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('system', 'System'),
    ]
    
    FONT_SIZE_CHOICES = [
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large', 'Large'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile_settings')
    theme = models.CharField(max_length=20, choices=THEME_CHOICES, default='light')
    font_size = models.CharField(max_length=20, choices=FONT_SIZE_CHOICES, default='medium')
    language = models.CharField(max_length=10, default='en')
    timezone = models.CharField(max_length=50, default='UTC')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_profile_settings'
        verbose_name = 'User Profile Setting'
        verbose_name_plural = 'User Profile Settings'
    
    def __str__(self):
        return f"{self.user.username}'s settings"


class AuditLog(models.Model):
    """Audit log for sensitive actions"""
    ACTION_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('password_change', 'Password Change'),
        ('profile_update', 'Profile Update'),
        ('account_deletion', 'Account Deletion'),
        ('session_logout', 'Session Logout'),
        ('settings_update', 'Settings Update'),
        ('data_export', 'Data Export'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=100, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=100, blank=True, null=True)
    resource_id = models.IntegerField(blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'audit_logs'
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username if self.user else 'Anonymous'} - {self.action} - {self.created_at}"


# ==================== TEACHING SUBJECTS MODEL ====================
class TeachingSubject(models.Model):
    TEACHING_LEVEL_CHOICES = [
        ('junior', 'Junior Secondary (Form 1-2)'),
        ('senior', 'Senior Secondary (Form 3-4)'),
        ('both', 'Both Junior & Senior'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='teaching_subjects')
    subject_name = models.CharField(max_length=100)
    subject_code = models.CharField(max_length=10, blank=True, null=True)
    teaching_level = models.CharField(max_length=10, choices=TEACHING_LEVEL_CHOICES, default='both')
    is_major = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'teaching_subjects'
        ordering = ['subject_name']
        verbose_name = 'Teaching Subject'
        verbose_name_plural = 'Teaching Subjects'
    
    def __str__(self):
        return f"{self.subject_name} ({self.get_teaching_level_display()})"