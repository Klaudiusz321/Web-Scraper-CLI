from django.shortcuts import render
from django.http import JsonResponse
import requests
from bs4 import BeautifulSoup

def home(request):
    return render(request, 'home.html')

def scrape(request):
    if request.method == 'POST':
        url = request.POST.get('url')
        r = requests.get(url)
        soup = BeautifulSoup(r.content, 'lxml')
        # Załóżmy, że chcemy wyciągnąć tytuł strony i wszystkie nagłówki h1-h6
        title = soup.title.string if soup.title else 'Brak tytułu'
        headings = [h.get_text().strip() for h in soup.find_all(['h1','h2','h3','h4','h5','h6'])]
        # Możemy wyniki przekazać do szablonu lub zwrócić jako JSON
        context = {'title': title, 'headings': headings}
        return render(request, 'results.html', context)
    else:
        return render(request, 'home.html')
