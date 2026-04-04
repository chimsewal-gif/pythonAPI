from rest_framework import serializers
from django.core.validators import EmailValidator, RegexValidator
from .models import Department

class DepartmentSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=False, 
        allow_blank=True,
        validators=[EmailValidator(message="Enter a valid email address")]
    )
    phone = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^[\+]?[265]?[-\s\.]?\(?[\d]{1,4}\)?[-\s\.]?[\d]{1,4}[-\s\.]?[\d]{1,9}$',
                message="Enter a valid phone number"
            )
        ]
    )
    
    class Meta:
        model = Department
        fields = [
            'id', 'name', 'code', 'description', 'head_of_department',
            'email', 'phone', 'established_year', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_code(self, value):
        if len(value) > 10:
            raise serializers.ValidationError("Department code must be 10 characters or less")
        return value.upper()
    
    def validate_established_year(self, value):
        from django.utils import timezone
        current_year = timezone.now().year
        if value and (value < 1900 or value > current_year):
            raise serializers.ValidationError(f"Establishment year must be between 1900 and {current_year}")
        return value