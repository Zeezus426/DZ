from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('commodities/', views.commodities, name='commodities'),
    path('about/', views.about, name='about'),
    path('blog/', views.blog, name='blog'),
    path('contact/', views.contact_submit, name='contact'),
    path('certification/', views.certification, name='certification'),
]
