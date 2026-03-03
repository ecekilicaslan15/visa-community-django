from django.shortcuts import render, get_object_or_404, redirect
from .models import Country, Comment
from django.contrib.auth.decorators import login_required
from .forms import CommentForm
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator
from django.db.models import Count


def home(request):
    countries = Country.objects.filter(is_active=True).order_by("name")
    return render(request, "core/home.html", {"countries": countries})


@login_required
def country_detail(request, slug):
    country = get_object_or_404(Country, slug=slug, is_active=True)

    comment_list = country.comments.all().order_by("-created_at")

    paginator = Paginator(comment_list, 5)
    page_number = request.GET.get("page")
    comments = paginator.get_page(page_number)

    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            new_comment = form.save(commit=False)
            new_comment.country = country
            new_comment.user = request.user
            new_comment.save()
            return redirect("country_detail", slug=slug)
    else:
        form = CommentForm()

    return render(
        request,
        "core/country_detail.html",
        {
            "country": country,
            "comments": comments,
            "form": form,
        },
    )


@login_required
def delete_comment(request, comment_id):
    if request.method != "POST":
        return HttpResponseForbidden("Method not allowed.")

    comment = get_object_or_404(Comment, id=comment_id)

    if comment.user != request.user:
        return HttpResponseForbidden("You are not allowed to delete this comment.")

    slug = comment.country.slug
    comment.delete()
    return redirect("country_detail", slug=slug)


@login_required
def edit_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)

    if comment.user != request.user:
        return HttpResponseForbidden("You are not allowed to edit this comment.")

    if request.method == "POST":
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            form.save()
            return redirect("country_detail", slug=comment.country.slug)
    else:
        form = CommentForm(instance=comment)
    return render(
        request,
        "core/edit_comment.html",
        {"form": form, "comment": comment},

    )


@login_required
def profile(request):
    comments = (
        Comment.objects
        .filter(user=request.user)
        .select_related("country")
        .order_by("-created_at")
    )

    return render(
        request,
        "core/profile.html",
        {"comments": comments},
    )


@login_required
def toggle_like(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)

    if comment.user == request.user:  # kullanici kendi yorumunu likelamasin
        return redirect("country_detail", slug=comment.country.slug)

    if request.user in comment.likes.all():
        comment.likes.remove(request.user)
    else:
        comment.likes.add(request.user)

    return redirect("country_detail", slug=comment.country.slug)


def home(request):
    countries = (
        Country.objects
        .filter(is_active=True)
        .annotate(comment_count=Count("comments"))
        .order_by("name")

    )

    return render(
        request,
        "core/home.html",
        {"countries": countries},
    )
