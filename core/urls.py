from django.urls import path
from . import guide_views, page_views, stats_views, views

urlpatterns = [
    path("", views.home, name="home"),
    path("insights/", views.insights, name="insights"),
    path("stats/", stats_views.stats_overview, name="stats_overview"),
    path("stats/refusals/", stats_views.stats_refusals, name="stats_refusals"),
    path("stats/cascade/", stats_views.stats_cascade, name="stats_cascade"),
    path("stats/appointments/", stats_views.stats_appointments, name="stats_appointments"),
    path("guides/", guide_views.guides, name="guides"),
    path("guides/motivation-letter/", guide_views.motivation_letter, name="motivation_letter"),
    path("guides/sponsorship-letter/", guide_views.sponsorship_letter, name="sponsorship_letter"),
    path("design-system/", views.design_system, name="design_system"),
    path("guidelines/", page_views.guidelines, name="guidelines"),
    path("privacy/", page_views.privacy, name="privacy"),
    path("contact/", page_views.contact, name="contact"),
    path("countries/<slug:slug>/", views.country_detail, name="country_detail"),
    path(
        "countries/<slug:slug>/openings/",
        views.report_opening,
        name="report_opening",
    ),
    path("comments/<int:comment_id>/", views.comment_thread, name="comment_thread"),
    path(
        "comments/<int:comment_id>/reply/",
        views.create_reply,
        name="create_reply",
    ),
    path(
        "comments/<int:comment_id>/delete/",
        views.delete_comment,
        name="delete_comment",
    ),
    path(
        "comments/<int:comment_id>/report/",
        views.report_comment,
        name="report_comment",
    ),
    path(
        "comments/<int:comment_id>/edit/",
        views.edit_comment,
        name="edit_comment",
    ),

    path("profile/", views.profile, name="profile"),

    path(
        "comments/<int:comment_id>/like/",
        views.toggle_like,
        name="toggle_like",
    ),
    path("replies/<int:reply_id>/edit/", views.edit_reply, name="edit_reply"),
    path("replies/<int:reply_id>/report/", views.report_reply, name="report_reply"),
    path("replies/<int:reply_id>/delete/", views.delete_reply, name="delete_reply"),
    path("replies/<int:reply_id>/like/", views.toggle_reply_like, name="toggle_reply_like"),

]
