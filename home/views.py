from django.shortcuts import render


def home(request):
    """
    Home page view for AusTrade Commodities.
    Renders the main landing page with company information,
    commodities, trust badges, and global reach details.
    """
    context = {
        'company_name': 'AusTrade Commodities',
        'page_title': 'Premium Australian Commodities Exporter',
    }
    return render(request, 'home/home.html', context)
