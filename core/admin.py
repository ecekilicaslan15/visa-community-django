from django.contrib import admin
from .models import Country, Comment


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "slug", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "country",
        "kind",
        "outcome",
        "short_text",
        "created_at",
    )
    list_filter = ("kind", "outcome", "country", "created_at")
    search_fields = ("text", "user__username", "country__name")
    ordering = ("-created_at",)

    def short_text(self, obj):
        return obj.text[:40]

    short_text.short_description = "Comment"
