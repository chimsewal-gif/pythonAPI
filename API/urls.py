from django.contrib import admin
from django.urls import path
from .api import api  # Import from the same directory
from django.urls import path
from .views import predict_admission_view

urlpatterns = [
    path('predict-admission/', predict_admission_view),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api.urls),
      path('predict-admission/', predict_admission_view),
]

print("✅ URLs loaded with api from:", api)