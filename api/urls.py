from django.urls import path

from api import views

urlpatterns = (
    path('user/<int:woffu_user_id>/', views.sync_user_request, name='sync_user_request'),
    path('company/<int:company_id>/', views.sync_company_users, name='sync_company_users'),
)
