from django.shortcuts import render
from .services import run_scraper_search

def index(request):
    query = request.GET.get('q', '').strip()
    diagnostics = []
    products = []

    if query:
        diagnostics, products = run_scraper_search(query)

    return render(request, 'core/index.html', {
        'query': query,
        'diagnostics': diagnostics,
        'products': products,
    })