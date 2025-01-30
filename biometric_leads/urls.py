"""
URL configuration for biometric_leads project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from leads import views

urlpatterns = [
    # Admin URLs
    path('admin/', admin.site.urls),
    
    # Authentication URLs
    path('accounts/login/', views.LoginView.as_view(), name='login'),
    path('accounts/logout/', views.custom_logout, name='logout'),
    path('accounts/signup/', views.SignUpView.as_view(), name='signup'),
    
    # Core Application URLs
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    
    # Lead Management URLs
    path('lead/create/', views.create_lead, name='create_lead'),
    path('lead/update-status/<int:lead_id>/<str:new_status>/', 
         views.update_lead_status, name='update_lead_status'),
    path('lead/history/', views.lead_history, name='lead_history'),
    path('lead/<int:lead_id>/', views.lead_detail, name='lead_detail'),
    
    # Biometric Management URLs
    path('biometric/process/<int:biometric_id>/<str:action>/', 
         views.process_biometric, name='process_biometric'),
    path('biometrics/', views.approved_biometrics, name='biometric_list'),
    path('biometrics/rejected/', views.rejected_biometrics, name='rejected_biometrics'),
    path('biometric/<int:biometric_id>/', views.biometric_detail, name='biometric_detail'),
    
    # Notification URLs
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/unread-count/', views.get_unread_notifications_count, name='unread_notifications_count'),
    
    # User Profile URLs
    path('user_details/', views.user_details, name='user_details'),
    
    # Search and Utility URLs
    path('search/', views.global_search, name='global_search'),
    
    # Password Reset URLs
    path('password_reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset.html'
         ), 
         name='password_reset'),
    path('password_reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html'
         ), 
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html'
         ), 
         name='password_reset_confirm'),
    path('reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
]

# Error Handling
handler400 = 'leads.views.bad_request'
handler403 = 'leads.views.permission_denied'
handler404 = 'leads.views.page_not_found'
handler500 = 'leads.views.server_error'
