from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("settings/", views.account_settings, name="settings"),
    path("delete/", views.delete_account, name="delete_account"),
]
