from django.shortcuts import render


def support_home(request):
    return render(request, "support/home.html")


def terms(request):
    return render(request, "support/terms.html")


def privacy(request):
    return render(request, "support/privacy.html")


def location_terms(request):
    return render(request, "support/location.html")


def points_policy(request):
    return render(request, "support/points.html")


def company(request):
    return render(request, "support/company.html")


def contact(request):
    return render(request, "support/contact.html")