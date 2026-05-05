from django.urls import path
from . import views
from .review_views import create_or_update_review

app_name = "posts"

urlpatterns = [
    path("", views.post_list, name="list"),
    path("create/", views.post_create, name="create"),
    path("<int:pk>/", views.post_detail, name="detail"),
    path("<int:pk>/update/", views.post_update, name="update"),
    path("<int:pk>/delete/", views.post_delete, name="delete"),
    path("<int:pk>/like/", views.post_like, name="like"),
    path("<int:pk>/review/", create_or_update_review, name="review"),
    path("<int:pk>/review-notice/read/", views.read_review_notice, name="read_review_notice"),
]