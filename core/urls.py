from django.contrib import admin
from django.urls import path
from api.api import api
from api import views  # Make sure to import views


urlpatterns = [
    path('admin/', admin.site.urls),
 
    path('api/', api.urls),
    path('api/admin/departments/', views.create_department, name='create_department'),
]
