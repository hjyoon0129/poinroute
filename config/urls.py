from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),

    path("", include("posts.urls")),

    path("auth/", include("accounts.urls")),

    # django-allauth social login
    path("accounts/", include("allauth.urls")),

    path("points/", include("points.urls")),
    path("community/", include("community.urls")),
    path("auctions/", include("auctions.urls")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)