from django.urls import path
from . import views

app_name = "auctions"

urlpatterns = [
    path("", views.auction_list, name="list"),
    path("create/", views.auction_create, name="create"),
    path("<int:pk>/", views.auction_detail, name="detail"),
    path("<int:pk>/answer/", views.answer_create, name="answer_create"),
    path("<int:pk>/cancel/", views.cancel_request, name="cancel"),
    path("<int:pk>/answers/<int:answer_pk>/select/", views.select_answer, name="select_answer"),
]