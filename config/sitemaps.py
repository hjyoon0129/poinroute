from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8
    protocol = "https"

    def items(self):
        return [
            "posts:list",
            "community:list",
            "auctions:list",
            "points:shop",
            "support:terms",
            "support:privacy",
            "support:location",
            "support:points",
            "support:company",
            "support:contact",
        ]

    def location(self, item):
        return reverse(item)