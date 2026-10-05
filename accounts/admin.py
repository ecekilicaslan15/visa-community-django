from django.contrib import admin

from .models import PasswordResetRequest, Profile, VerificationResend


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "email_verified", "consent_at")
    list_filter = ("email_verified",)
    search_fields = ("user__username", "user__email")
    raw_id_fields = ("user",)


@admin.register(VerificationResend)
class VerificationResendAdmin(admin.ModelAdmin):
    list_display = ("user", "sent_at")
    raw_id_fields = ("user",)


@admin.register(PasswordResetRequest)
class PasswordResetRequestAdmin(admin.ModelAdmin):
    list_display = ("ip_address", "created_at")
