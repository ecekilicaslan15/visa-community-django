from django.shortcuts import render


def guides(request):
    return render(request, "core/guides/index.html")


def motivation_letter(request):
    return render(request, "core/guides/motivation.html")


def sponsorship_letter(request):
    return render(request, "core/guides/sponsorship.html")
