from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("settings/", views.account_settings, name="settings"),
    path("delete/", views.delete_account, name="delete_account"),
    path("verify/<uidb64>/<token>/", views.verify_email, name="verify_email"),
    path("verification/resend/", views.resend_verification, name="resend_verification"),
    path("download/", views.download_data, name="download_data"),
]
