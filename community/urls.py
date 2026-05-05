from django.urls import path
from . import views

app_name = "community"

urlpatterns = [
    path("", views.community_list, name="list"),
    path("write/", views.community_create, name="create"),
    path("<int:pk>/", views.community_detail, name="detail"),
    path("<int:pk>/edit/", views.community_update, name="update"),
    path("<int:pk>/delete/", views.community_delete, name="delete"),

    path("<int:pk>/like/", views.community_like_toggle, name="like_toggle"),
    path("<int:pk>/bump/", views.community_bump_post, name="bump"),
    path("<int:pk>/hotline/", views.community_hotline_post, name="hotline"),

    path("<int:pk>/comments/", views.comment_create, name="comment_create"),
    path("comments/<int:pk>/delete/", views.comment_delete, name="comment_delete"),
]