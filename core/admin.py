from django.contrib import admin
from .models import (
    Comment,
    ConsulateVisaStat,
    Country,
    CountryVisaStat,
    OpeningReport,
    Reply,
    StatsDataset,
)


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


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "comment", "short_text", "created_at")
    list_filter = ("created_at",)
    search_fields = ("text", "user__username", "comment__text")
    ordering = ("-created_at",)
    raw_id_fields = ("comment", "user")

    def short_text(self, obj):
        return obj.text[:40]

    short_text.short_description = "Reply"


@admin.register(OpeningReport)
class OpeningReportAdmin(admin.ModelAdmin):
    list_display = ("id", "country", "user", "city", "opened_on", "created_at")
    list_filter = ("country", "opened_on")
    search_fields = ("city", "user__username", "country__name")
    ordering = ("-opened_on", "-created_at")
    list_select_related = ("country", "user")
    raw_id_fields = ("country", "user")


@admin.register(StatsDataset)
class StatsDatasetAdmin(admin.ModelAdmin):
    list_display = ("year", "title", "source_name", "published_on")


@admin.register(CountryVisaStat)
class CountryVisaStatAdmin(admin.ModelAdmin):
    list_display = ("country_name", "country_code", "applications", "issued", "refused", "dataset")
    list_filter = ("dataset",)
    search_fields = ("country_name", "country_code")


@admin.register(ConsulateVisaStat)
class ConsulateVisaStatAdmin(admin.ModelAdmin):
    list_display = ("country_name", "city", "applications", "refusal_rate", "dataset")
    list_filter = ("dataset", "city")
    search_fields = ("country_name", "city")
