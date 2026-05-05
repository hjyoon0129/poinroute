from django.urls import path

from . import views


app_name = "support"

urlpatterns = [
    path("", views.support_home, name="home"),
    path("terms/", views.terms, name="terms"),
    path("privacy/", views.privacy, name="privacy"),
    path("location/", views.location_terms, name="location"),
    path("points/", views.points_policy, name="points"),
    path("company/", views.company, name="company"),
    path("contact/", views.contact, name="contact"),
]