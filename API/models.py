from django.db import models
from django.contrib.auth.models import User

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

# Applicant model - Keep only one instance with updated fields
class Applicant(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
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
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    class Meta:
        db_table = 'applicants'

# NEXT OF KIN MODEL
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
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.title} {self.first_name} {self.last_name} ({self.relationship})"
    
    class Meta:
        db_table = 'next_of_kin'
        verbose_name = "Next of Kin"
        verbose_name_plural = "Next of Kin"
        ordering = ['-created_at']

# Programme model - Keep only one instance
class Programme(models.Model):
    CATEGORY_CHOICES = [
        ('undergraduate', 'Undergraduate'),
        ('postgraduate', 'Postgraduate'),
        ('diploma', 'Diploma'),
        ('certificate', 'Certificate'),
    ]
    
    name = models.CharField(max_length=200)
    # Make it nullable first
    code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='programmes')
    duration = models.CharField(max_length=50, blank=True, null=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='undergraduate')
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

# FeePayment model for tracking payments
class FeePayment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fee_payments')
    application = models.ForeignKey(Application, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='MWK')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reference = models.CharField(max_length=100, unique=True)
    payment_date = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    
    def __str__(self):
        return f"Payment {self.reference} - {self.amount} {self.currency}"
    
    class Meta:
        db_table = 'fee_payments'
        ordering = ['-payment_date']