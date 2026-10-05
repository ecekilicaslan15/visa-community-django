from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Avg, Count, Max, Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import CommentForm, OpeningReportForm, ReplyForm
from .models import Comment, Country, Reply
from .predictions import predict_next_window

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


def comments_for_cards(qs=None):
    """Comments ready for comment_card: author, country, likes, and reply stats."""
    if qs is None:
        qs = Comment.objects.all()
    return qs.select_related("user", "country").annotate(
        like_count=Count("likes", distinct=True),
        reply_count=Count("replies", distinct=True),
        last_reply_at=Max("replies__created_at"),
    )


def _question_answer_percent():
    """Share of questions that have at least one reply. Separate queries avoid join inflation."""
    questions = Comment.objects.filter(kind=Comment.KIND_QUESTION)
    question_count = questions.count()
    answered = questions.filter(replies__isnull=False).distinct().count()
    return _percent(answered, question_count)


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
        questions=Count("id", filter=Q(kind=Comment.KIND_QUESTION)),
    )
    totals["countries"] = Country.objects.filter(is_active=True).count()
    totals["answered_percent"] = _question_answer_percent()

    recent = comments_for_cards(
        Comment.objects.filter(country__is_active=True)
    ).order_by("-created_at")[:3]

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

    return _render_country(request, country, form)


def report_opening(request, slug):
    """POST-only. A traveler reports the day appointment slots opened."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())

    country = get_object_or_404(Country, slug=slug, is_active=True)
    opening_form = OpeningReportForm(request.POST, user=request.user, country=country)
    if opening_form.is_valid():
        report = opening_form.save(commit=False)
        report.user = request.user
        report.country = country
        try:
            report.save()
        except IntegrityError:
            opening_form.add_error(
                "opened_on",
                "You already reported this opening date for this country.",
            )
        else:
            messages.success(
                request,
                "Thanks — that opening is now part of the community outlook.",
            )
            return redirect("country_detail", slug=slug)

    return _render_country(
        request,
        country,
        CommentForm(initial={"kind": Comment.KIND_QUESTION}),
        opening_form=opening_form,
    )


def _render_country(request, country, comment_form, opening_form=None):
    comment_list = comments_for_cards(country.comments.all()).order_by("-created_at")
    comments = Paginator(comment_list, 10).get_page(request.GET.get("page"))

    liked_ids = set()
    if request.user.is_authenticated:
        liked_ids = set(
            request.user.liked_comments.filter(country=country).values_list("id", flat=True)
        )
        if opening_form is None:
            opening_form = OpeningReportForm(user=request.user, country=country)

    # Newest report first. Duplicate dates still count as separate reports.
    opened_on = list(
        country.opening_reports.order_by("-created_at", "-id").values_list(
            "opened_on", flat=True
        )
    )

    return render(
        request,
        "core/country_detail.html",
        {
            "country": country,
            "comments": comments,
            "form": comment_form,
            "stats": country_stats(country),
            "liked_ids": liked_ids,
            "opening_form": opening_form,
            "opening_count": len(opened_on),
            "last_opening": opened_on[0] if opened_on else None,
            "prediction": predict_next_window(opened_on),
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
    comments = list(
        comments_for_cards(Comment.objects.filter(user=request.user)).order_by("-created_at")
    )
    replies = list(
        Reply.objects.filter(user=request.user)
        .select_related("user", "comment", "comment__country")
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

    contributions = len(comments) + len(replies)
    question_replies = sum(1 for reply in replies if reply.comment.is_question)
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
            "replies": replies,
            "experience_count": experience_count,
            "question_count": question_count,
            "country_count": len(countries),
            "stamps": list(stamps.values()),
            "contributions": contributions,
            "level": level,
            "progress": progress,
            "is_community_helper": question_replies >= 10,
            "liked_reply_ids": set(),
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


def comment_thread(request, comment_id):
    """Public thread: the original post, replies oldest-first, then a reply box."""
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    comment = get_object_or_404(
        comments_for_cards(),
        id=comment_id,
        country__is_active=True,
    )
    return _render_thread(request, comment, ReplyForm())


def create_reply(request, comment_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())

    comment = get_object_or_404(
        comments_for_cards(),
        id=comment_id,
        country__is_active=True,
    )
    form = ReplyForm(request.POST)
    if form.is_valid():
        reply = form.save(commit=False)
        reply.comment = comment
        reply.user = request.user
        reply.save()
        messages.success(request, "Your reply is live.")
        return redirect("comment_thread", comment_id=comment.id)
    return _render_thread(request, comment, form)


def _render_thread(request, comment, form):
    replies = (
        comment.replies.select_related("user")
        .annotate(like_count=Count("likes", distinct=True))
        .order_by("created_at")
    )
    liked_ids = set()
    liked_reply_ids = set()
    if request.user.is_authenticated:
        if comment.likes.filter(id=request.user.id).exists():
            liked_ids.add(comment.id)
        liked_reply_ids = set(
            request.user.liked_replies.filter(comment=comment).values_list("id", flat=True)
        )
    return render(
        request,
        "core/thread.html",
        {
            "comment": comment,
            "replies": replies,
            "form": form,
            "liked_ids": liked_ids,
            "liked_reply_ids": liked_reply_ids,
        },
    )


@login_required
def edit_reply(request, reply_id):
    reply = get_object_or_404(
        Reply.objects.select_related("comment__country"),
        id=reply_id,
        user=request.user,
    )
    if request.method == "POST":
        form = ReplyForm(request.POST, instance=reply)
        if form.is_valid():
            form.save()
            messages.success(request, "Your reply was updated.")
            return redirect("comment_thread", comment_id=reply.comment_id)
    else:
        form = ReplyForm(instance=reply)
    return render(request, "core/edit_reply.html", {"form": form, "reply": reply})


def delete_reply(request, reply_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())

    if request.user.is_staff:
        reply = get_object_or_404(Reply, id=reply_id)
    else:
        reply = get_object_or_404(Reply, id=reply_id, user=request.user)
    comment_id = reply.comment_id
    reply.delete()
    messages.success(request, "The reply was deleted.")
    return redirect(_next_url(request) or f"/comments/{comment_id}/")


def toggle_reply_like(request, reply_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())

    reply = get_object_or_404(Reply, id=reply_id)
    if reply.user_id != request.user.id:
        if reply.likes.filter(id=request.user.id).exists():
            reply.likes.remove(request.user)
        else:
            reply.likes.add(request.user)
    return redirect(_next_url(request) or f"/comments/{reply.comment_id}/")


def _next_url(request):
    """Safe redirect target from ?next= / form field, so actions return to the same page."""
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return None
