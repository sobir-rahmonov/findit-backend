from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "FindIt: Boshqaruv paneli"
admin.site.site_title = "FindIt"
admin.site.index_title = "Xush kelibsiz!"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('accounts.urls')),
    path('api/', include('posts.urls')), 
    path('api/', include('claims.urls')), 
    path('api/', include('notifications.urls')),
    path('api/', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)