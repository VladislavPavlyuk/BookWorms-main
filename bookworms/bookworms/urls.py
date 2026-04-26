
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path('', include('mainApp.urls')),
    path('admin/', admin.site.urls),
    path('profile/', include('profileApp.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # У продакшені django.conf.urls.static.static не підключає /media/.
    # Без цього ImageField (аватари) дає 404; обкладинки з Open Library не з /media/ — тому вони «працюють».
    # Для кількох інстансів Azure краще django-storages + Blob Storage замість локальних файлів.
    _media_url = (settings.MEDIA_URL or "media/").lstrip("/")
    urlpatterns += [
        re_path(
            rf"^{_media_url}(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]