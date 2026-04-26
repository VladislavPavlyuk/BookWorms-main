
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

# /media/ має бути ПЕРЕД include(mainApp): інакше деякі конфігурації/проксі ніколи не дійдуть до роздачі файлів.
_media_urlpatterns = []
if settings.DEBUG:
    _media_urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # У продакшені static() не додає маршрути; ImageField → /media/…
    _media_url = (settings.MEDIA_URL or "media/").lstrip("/")
    _media_urlpatterns += [
        re_path(
            rf"^{_media_url}(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]

urlpatterns = _media_urlpatterns + [
    path('', include('mainApp.urls')),
    path('admin/', admin.site.urls),
    path('profile/', include('profileApp.urls')),
]