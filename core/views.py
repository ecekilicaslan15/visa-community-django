from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Max, Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import CommentForm
from .models import Comment, Country

EXPERIENCE = Comment.KIND_EXPERIENCE
APPROVED = Comment.OUTCOME_APPROVED

# Traveler levels on the profile page: (minimum contributions, label)
LEVELS = [
    (0, "🧳 New Traveler"),
    (5, "✈️ Frequent Traveler"),
    (20, "🛂 Visa Expert"),
]


def _percent(part, whole):
    return round(100 * part / whole) if whole else None


def _countries_with_stats():
    """Active countries annotated with the numbers the cards and Insights table show."""
    countries = (
        Country.objects.filter(is_active=True)
        .annotate(
            comment_count=Count("comments", distinct=True),
            experience_count=Count("comments", filter=Q(comments__kind=EXPERIENCE), distinct=True),
            approved_count=Count(
                "comments",
                filter=Q(comments__kind=EXPERIENCE, comments__outcome=APPROVED),
                distinct=True,
            ),
            rejected_count=Count(
                "comments",
                filter=Q(comments__kind=EXPERIENCE, comments__outcome=Comment.OUTCOME_REJECTED),
                distinct=True,
            ),
            avg_wait=Avg("comments__wait_days", filter=Q(comments__kind=EXPERIENCE)),
            last_appointment=Max("comments__appointment_date"),
        )
        .order_by("name")
    )
    return countries


def home(request):
    query = request.GET.get("q", "").strip()
    countries = _countries_with_stats()
    if query:
        countries = countries.filter(name__icontains=query)
    countries = list(countries)
    for c in countries:
        c.approval_rate = _percent(c.approved_count, c.experience_count)

    totals = Comment.objects.aggregate(
        experiences=Count("id", filter=Q(kind=EXPERIENCE)),
        questions=Count("id", filter=~Q(kind=EXPERIENCE)),
    )
    totals["countries"] = Country.objects.filter(is_active=True).count()

    recent = (
        Comment.objects.filter(country__is_active=True)
        .select_related("user", "country")
        .annotate(like_count=Count("likes", distinct=True))
        .order_by("-created_at")[:3]
    )

    liked_ids = set()
    if request.user.is_authenticated:
        liked_ids = set(request.user.liked_comments.values_list("id", flat=True))

    return render(
        request,
        "core/home.html",
        {
            "countries": countries,
            "totals": totals,
            "query": query,
            "recent": recent,
            "liked_ids": liked_ids,
            "first_country": Country.objects.filter(is_active=True).order_by("name").first(),
        },
    )


def insights(request):
    countries = list(_countries_with_stats())
    for c in countries:
        c.approval_rate = _percent(c.approved_count, c.experience_count)
        c.avg_wait = round(c.avg_wait) if c.avg_wait is not None else None
    return render(request, "core/insights.html", {"countries": countries})


def design_system(request):
    return render(request, "core/design_system.html")


def country_stats(country):
    """Numbers for the chips and side panel, computed from real comments."""
    experiences = country.comments.filter(kind=EXPERIENCE)
    agg = experiences.aggregate(
        total=Count("id"),
        approved=Count("id", filter=Q(outcome=APPROVED)),
        avg_wait=Avg("wait_days"),
        last_appointment=Max("appointment_date"),
    )
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return {
        "experiences": agg["total"],
        "approval_rate": _percent(agg["approved"], agg["total"]),
        "avg_wait": round(agg["avg_wait"]) if agg["avg_wait"] is not None else None,
        "last_appointment": agg["last_appointment"],
        "this_month": country.comments.filter(created_at__gte=month_start).count(),
        "dated_appointments": experiences.exclude(appointment_date=None).count(),
    }


def country_detail(request, slug):
    # Reading is public; posting needs an account.
    country = get_object_or_404(Country, slug=slug, is_active=True)

    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        form = CommentForm(request.POST)
        if form.is_valid():
            new_comment = form.save(commit=False)
            new_comment.country = country
            new_comment.user = request.user
            new_comment.save()
            messages.success(request, "Thanks — your post is live.")
            return redirect("country_detail", slug=slug)
    else:
        form = CommentForm(initial={"kind": Comment.KIND_QUESTION})

    comment_list = (
        country.comments.select_related("user")
        .annotate(like_count=Count("likes", distinct=True))
        .order_by("-created_at")
    )
    comments = Paginator(comment_list, 10).get_page(request.GET.get("page"))

    liked_ids = set()
    if request.user.is_authenticated:
        liked_ids = set(
            request.user.liked_comments.filter(country=country).values_list("id", flat=True)
        )

    return render(
        request,
        "core/country_detail.html",
        {
            "country": country,
            "comments": comments,
            "form": form,
            "stats": country_stats(country),
            "liked_ids": liked_ids,
        },
    )


@login_required
def delete_comment(request, comment_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    comment = get_object_or_404(Comment, id=comment_id, user=request.user)
    slug = comment.country.slug
    comment.delete()
    messages.success(request, "Your post was deleted.")
    return redirect(_next_url(request) or f"/countries/{slug}/")


@login_required
def edit_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, user=request.user)

    if request.method == "POST":
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            form.save()
            messages.success(request, "Your post was updated.")
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
        Comment.objects.filter(user=request.user)
        .select_related("country")
        .annotate(like_count=Count("likes", distinct=True))
        .order_by("-created_at")
    )

    experience_count = sum(1 for c in comments if c.is_experience)
    question_count = len(comments) - experience_count
    countries = {c.country_id for c in comments}

    # One "stamp" per country: the outcome of the most recent experience,
    # or "in progress" if the user only asked questions there so far.
    stamps = {}
    for c in comments:  # newest first
        stamp = stamps.get(c.country_id)
        if stamp is None:
            stamps[c.country_id] = {"country": c.country, "outcome": c.outcome if c.is_experience else ""}
        elif not stamp["outcome"] and c.is_experience:
            stamp["outcome"] = c.outcome

    contributions = len(comments)
    level = next_level = None
    for i, (minimum, label) in enumerate(LEVELS):
        if contributions >= minimum:
            level = label
            next_level = LEVELS[i + 1] if i + 1 < len(LEVELS) else None
    progress = None
    if next_level:
        current_min = max(m for m, _ in LEVELS if contributions >= m)
        progress = {
            "label": next_level[1],
            "remaining": next_level[0] - contributions,
            "percent": round(100 * (contributions - current_min) / (next_level[0] - current_min)),
        }

    return render(
        request,
        "core/profile.html",
        {
            "comments": comments,
            "experience_count": experience_count,
            "question_count": question_count,
            "country_count": len(countries),
            "stamps": list(stamps.values()),
            "contributions": contributions,
            "level": level,
            "progress": progress,
        },
    )


@login_required
def toggle_like(request, comment_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    comment = get_object_or_404(Comment, id=comment_id)

    if comment.user != request.user:  # kullanici kendi yorumunu likelamasin
        if comment.likes.filter(id=request.user.id).exists():
            comment.likes.remove(request.user)
        else:
            comment.likes.add(request.user)

    return redirect(_next_url(request) or f"/countries/{comment.country.slug}/")


def _next_url(request):
    """Safe redirect target from ?next= / form field, so actions return to the same page."""
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return None
