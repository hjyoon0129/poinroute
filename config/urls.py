from django.contrib import admin
from django.urls import path, include
from django.contrib.sitemaps.views import sitemap

from config.sitemaps import StaticViewSitemap
from config.views import robots_txt


sitemaps = {
    "static": StaticViewSitemap,
}


urlpatterns = [
    path("robots.txt", robots_txt, name="robots_txt"),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),

    path("admin/", admin.site.urls),

    # 기존 include들 그대로
    path("", include("posts.urls")),
    path("community/", include("community.urls")),
    path("auctions/", include("auctions.urls")),
    path("points/", include("points.urls")),
    path("support/", include("support.urls")),
    path("accounts/", include("accounts.urls")),
]