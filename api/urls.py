from django.urls import path
from .views import ParseUrlView

urlpatterns = [
    path('parse-url/', ParseUrlView.as_view(), name='parse-url'),
] 