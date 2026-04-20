from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from .api import api as ninja_api
from .views import predict_admission_view
import os

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', ninja_api.urls),
    path('predict-admission/', predict_admission_view),
]

# Serve media files in development - THIS IS CRITICAL
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Alternative method - more explicit
    urlpatterns += [
        path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
    ]

print(f"✅ Media URL: {settings.MEDIA_URL}")
print(f"✅ Media Root: {settings.MEDIA_ROOT}")
print(f"✅ Media directory exists: {os.path.exists(settings.MEDIA_ROOT)}")