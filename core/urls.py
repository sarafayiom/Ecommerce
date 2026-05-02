from rest_framework.routers import DefaultRouter
from .views import register
from django.urls import path
from .views import ProductListCreateAPIView, ProductDetailAPIView , OrderDetailAPIView , OrderListCreateAPIView , PayOrderAPIView , CancelOrderAPIView ,CompleteOrderAPIView

urlpatterns = [
    path('products/', ProductListCreateAPIView.as_view()),
    path('products/<int:id>/', ProductDetailAPIView.as_view()),
    path('register/', register),
    path('orders/', OrderListCreateAPIView.as_view()),
    path('orders/<int:id>/', OrderDetailAPIView.as_view()),
    path('orders/<int:id>/pay/', PayOrderAPIView.as_view()),
    path('orders/<int:id>/complete/', CompleteOrderAPIView.as_view()),
    path('orders/<int:id>/cancel/', CancelOrderAPIView.as_view()),
]
    