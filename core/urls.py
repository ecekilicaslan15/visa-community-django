from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("countries/<slug:slug>/", views.country_detail, name="country_detail"),
    path(
        "comments/<int:comment_id>/delete/",
        views.delete_comment,
        name="delete_comment",
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

]
