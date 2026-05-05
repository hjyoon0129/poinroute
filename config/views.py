from django.http import HttpResponse


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        "Disallow: /accounts/",
        "Disallow: /login/",
        "Disallow: /signup/",
        "",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]

    return HttpResponse("\n".join(lines), content_type="text/plain")