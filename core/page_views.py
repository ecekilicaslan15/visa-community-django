from django.shortcuts import render


def guidelines(request):
    return render(request, "core/guidelines.html")


def privacy(request):
    return render(request, "core/privacy.html")


def contact(request):
    return render(request, "core/contact.html")
