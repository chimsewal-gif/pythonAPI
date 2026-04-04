from django.contrib import admin
from django.urls import path
from .api import api  # Import from the same directory

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api.urls),
]

print("✅ URLs loaded with api from:", api)