from django.urls import path

from . import views

app_name = "points"

urlpatterns = [
    path("", views.point_shop, name="shop"),
    path("history/", views.point_history, name="history"),
    path("redeem/<int:item_id>/", views.redeem_reward, name="redeem"),
    path("ad/<int:campaign_id>/claim/", views.claim_ad_reward, name="claim_ad"),
    path("notice/reward/<int:redemption_id>/read/", views.read_reward_notice, name="read_reward_notice"),
    path("notice/ad/<int:claim_id>/read/", views.read_ad_notice, name="read_ad_notice"),
]