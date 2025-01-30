from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import views as auth_views, logout
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from .models import Lead, Biometric, User, Notification
from django.core.mail import send_mail
from django.contrib import messages
from django.db.models import (
    Count, Q, Sum, 
    F, ExpressionWrapper, DurationField
)
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
import json
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from .forms import LeadForm
from dateutil.relativedelta import relativedelta

# Create your views here.

class SignUpView(CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy('login')
    template_name = 'registration/signup.html'

class LoginView(auth_views.LoginView):
    template_name = 'registration/login.html'
    form_class = AuthenticationForm
    redirect_authenticated_user = True
    
    def get_success_url(self):
        return reverse_lazy('home')

# Using Django's built-in LogoutView for logout
LogoutView = auth_views.LogoutView.as_view()

def custom_logout(request):
    messages.success(request, 'You have been successfully logged out.')
    logout(request)
    return redirect('login')

@login_required
def home(request):
    """
    Comprehensive home page view with advanced lead insights and analytics
    """
    # Base queryset with optional filtering
    leads = Lead.objects.all()

    # Lead Status Breakdown
    total_leads = leads.count()
    status_counts = {
        'new': leads.filter(status='new').count(),
        'in_progress': leads.filter(status='in_progress').count(),
        'approved': leads.filter(status='approved').count(),
        'rejected': leads.filter(status='rejected').count()
    }

    # Performance Metrics
    conversion_rate = (status_counts['approved'] / total_leads * 100) if total_leads > 0 else 0
    rejection_rate = (status_counts['rejected'] / total_leads * 100) if total_leads > 0 else 0

    # Location-based Analysis
    location_analysis = leads.values('location').annotate(
        total_count=Count('id'),
        new_count=Count('id', filter=Q(status='new')),
        approved_count=Count('id', filter=Q(status='approved')),
        rejected_count=Count('id', filter=Q(status='rejected'))
    ).order_by('-total_count')

    # Monthly Trend Analysis
    monthly_trend = leads.annotate(
        month=TruncMonth('created_at')
    ).values('month', 'status').annotate(
        count=Count('id')
    ).order_by('month', 'status')

    # Prepare Monthly Trend Data
    monthly_leads_data = {}
    for entry in monthly_trend:
        month_str = entry['month'].strftime('%B %Y')
        if month_str not in monthly_leads_data:
            monthly_leads_data[month_str] = {
                'new': 0,
                'in_progress': 0,
                'approved': 0,
                'rejected': 0
            }
        monthly_leads_data[month_str][entry['status']] = entry['count']

    # Lead Conversion Funnel
    conversion_funnel = [
        {'stage': 'Total Leads', 'count': total_leads},
        {'stage': 'New Leads', 'count': status_counts['new']},
        {'stage': 'In Progress', 'count': status_counts['in_progress']},
        {'stage': 'Approved', 'count': status_counts['approved']},
        {'stage': 'Rejected', 'count': status_counts['rejected']}
    ]

    # Time to Conversion Analysis
    time_to_conversion = {
        'avg_conversion_time': 'N/A',
        'min_conversion_time': 'N/A',
        'max_conversion_time': 'N/A'
    }

    # Simplified time to conversion for approved leads
    approved_leads = leads.filter(status='approved')
    if approved_leads.exists():
        # Calculate days since creation for approved leads
        days_list = []
        for lead in approved_leads:
            days = (timezone.now().date() - lead.created_at.date()).days
            days_list.append(days)
        
        # Calculate statistics
        if days_list:
            time_to_conversion = {
                'avg_conversion_time': f"{int(sum(days_list) / len(days_list))} days",
                'min_conversion_time': f"{min(days_list)} days",
                'max_conversion_time': f"{max(days_list)} days"
            }

    # Lead Age Distribution
    today = timezone.now().date()
    lead_age_distribution = {
        '0-7 days': leads.filter(created_at__date__gte=today - timedelta(days=7)).count(),
        '8-30 days': leads.filter(
            created_at__date__gte=today - timedelta(days=30),
            created_at__date__lt=today - timedelta(days=7)
        ).count(),
        '31-90 days': leads.filter(
            created_at__date__gte=today - timedelta(days=90),
            created_at__date__lt=today - timedelta(days=30)
        ).count(),
        '90+ days': leads.filter(created_at__date__lt=today - timedelta(days=90)).count()
    }

    # Recent Lead Details
    recent_leads = leads.order_by('-created_at')[:10]

    context = {
        # Lead Status Metrics
        'total_leads': total_leads,
        'status_counts': status_counts,
        'conversion_rate': round(conversion_rate, 2),
        'rejection_rate': round(rejection_rate, 2),

        # Detailed Analyses
        'location_analysis': list(location_analysis),
        'monthly_leads_data': monthly_leads_data,
        'conversion_funnel': conversion_funnel,
        'time_to_conversion': time_to_conversion,
        'lead_age_distribution': lead_age_distribution,

        # Recent Leads
        'recent_leads': recent_leads
    }
    
    return render(request, 'home.html', context)

@login_required
def update_lead_status(request, lead_id, new_status):
    """
    Comprehensive lead status update with cross-model interactions
    """
    try:
        lead = get_object_or_404(Lead, id=lead_id)
        
        # Track the original status for comparison
        original_status = lead.status
        
        # Update lead status
        lead.status = new_status
        lead.save()
        
        # Create a detailed notification
        # Notification.objects.create(
        #     user=request.user,
        #     lead=lead,
        #     message=f"Lead status changed from {original_status} to {new_status}",
        #     notification_type='lead'
        # )
        
        # Automatic biometric creation or update for approved leads
        if new_status == 'approved':
            # Create or update biometric
            biometric, created = Biometric.objects.get_or_create(
                lead=lead,
                defaults={
                    'user': request.user,
                    'name': lead.name,
                    'location': lead.location,
                    'status': 'pending'
                }
            )
            
            if not created:
                biometric.status = 'pending'
                biometric.save()
        
        # Optional: Add logging or additional processing
        messages.success(request, f"Lead status updated to {new_status}")
        
        return redirect('home')
    
    except Exception as e:
        # Comprehensive error handling
        messages.error(request, f"Error updating lead status: {str(e)}")
        return redirect('home')

@login_required
def create_lead(request):
    """
    Comprehensive lead creation with automatic user assignment
    """
    if request.method == 'POST':
        form = LeadForm(request.POST)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.user = request.user
            lead.save()
            
            # Create notification
            # Notification.objects.create(
            #     user=request.user,
            #     lead=lead,
            #     message=f"New lead created: {lead.name}",
            #     notification_type='lead'
            # )
            
            messages.success(request, "Lead created successfully")
            return redirect('home')
    else:
        form = LeadForm()
    
    return render(request, 'create_lead.html', {'form': form})

@login_required
def process_biometric(request, biometric_id, action):
    """
    Comprehensive biometric processing with status updates and notifications
    """
    try:
        biometric = get_object_or_404(Biometric, id=biometric_id, user=request.user)
        
        # Track original status
        original_status = biometric.status
        
        # Update status based on action
        if action == 'approve':
            biometric.status = 'approved'
        elif action == 'reject':
            biometric.status = 'rejected'
            biometric.rejection_reason = request.POST.get('rejection_reason', '')
        
        biometric.save()
        
        # Create notification
        # Notification.objects.create(
        #     user=request.user,
        #     biometric=biometric,
        #     message=f"Biometric status changed from {original_status} to {biometric.status}",
        #     notification_type='biometric'
        # )
        
        # Update associated lead if exists
        if biometric.lead:
            biometric.lead.status = 'approved' if action == 'approve' else 'rejected'
            biometric.lead.save()
        
        messages.success(request, f"Biometric {action}d successfully")
        return redirect('biometric_list')
    
    except Exception as e:
        messages.error(request, f"Error processing biometric: {str(e)}")
        return redirect('biometric_list')

@login_required
def global_search(request):
    """
    Perform a global search across leads and biometrics
    """
    query = request.GET.get('q', '').strip()
    
    if not query:
        messages.warning(request, "Please enter a search term.")
        return render(request, 'global_search_results.html', {
            'query': query,
            'leads': [],
            'biometrics': [],
            'total_results': 0
        })
    
    # Search leads
    leads = Lead.objects.filter(
        Q(name__icontains=query) | 
        Q(email__icontains=query) | 
        Q(phone__icontains=query) | 
        Q(company__icontains=query)
    )
    
    # Search biometrics
    biometrics = Biometric.objects.filter(
        Q(name__icontains=query) | 
        Q(description__icontains=query)
    )
    
    # Prepare results for tabular display
    lead_results = []
    for lead in leads:
        lead_results.append({
            'id': lead.id,
            'name': lead.name,
            'email': lead.email,
            'phone': lead.phone,
            'company': lead.company,
            'status': lead.get_status_display(),
            'type': 'Lead',
            'detail_url': reverse('lead_detail', args=[lead.id])
        })
    
    biometric_results = []
    for biometric in biometrics:
        biometric_results.append({
            'id': biometric.id,
            'name': biometric.name,
            'description': biometric.description,
            'status': biometric.get_status_display(),
            'type': 'Biometric',
            'detail_url': reverse('biometric_detail', args=[biometric.id])
        })
    
    # Combine and sort results
    all_results = lead_results + biometric_results
    total_results = len(all_results)
    
    # Pagination
    paginator = Paginator(all_results, 10)  # 10 results per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'query': query,
        'results': page_obj,
        'total_results': total_results,
        'is_paginated': total_results > 10
    }
    
    return render(request, 'global_search_results.html', context)

@login_required
def about(request):
    return render(request, 'about.html')

@login_required
def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        try:
            # Send email
            send_mail(
                f'Contact Form Submission: {subject}',
                f'Name: {name}\nEmail: {email}\n\nMessage:\n{message}',
                email,  # From email
                ['support@biometricleads.com'],  # To email
                fail_silently=False,
            )
            messages.success(request, 'Your message has been sent successfully!')
        except Exception as e:
            messages.error(request, 'Failed to send message. Please try again later.')
        
        return redirect('contact')
    
    return render(request, 'contact.html')

@login_required
def user_details(request):
    """
    Comprehensive user details view with statistics and recent activities
    """
    # Biometric status count
    biometric_status_count = {
        'total': Biometric.objects.filter(user=request.user).count(),
        'pending': Biometric.objects.filter(user=request.user, status='pending').count(),
        'approved': Biometric.objects.filter(user=request.user, status='approved').count(),
        'rejected': Biometric.objects.filter(user=request.user, status='rejected').count()
    }

    # Recent biometrics (last 30 days)
    recent_biometrics = Biometric.objects.filter(
        user=request.user, 
        created_at__gte=timezone.now() - timedelta(days=30)
    ).order_by('-created_at')[:10]

    context = {
        'biometric_status_count': biometric_status_count,
        'recent_biometrics': recent_biometrics
    }

    return render(request, 'user_details.html', context)

@login_required
def approved_biometrics(request):
    """
    View to display only approved leads and biometrics
    Ensures data consistency and cross-table interactions
    """
    # Base queryset for approved leads and biometrics
    leads = Lead.objects.filter(status='approved')
    biometrics = Biometric.objects.filter(status='approved')
    
    # Filtering
    location_filter = request.GET.get('location')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if location_filter:
        leads = leads.filter(location=location_filter)
        biometrics = biometrics.filter(location=location_filter)
    
    if date_from:
        leads = leads.filter(created_at__date__gte=date_from)
        biometrics = biometrics.filter(approved_at__date__gte=date_from)
    
    if date_to:
        leads = leads.filter(created_at__date__lte=date_to)
        biometrics = biometrics.filter(approved_at__date__lte=date_to)
    
    # Sorting
    sort_by = request.GET.get('sort', '-created_at')
    leads = leads.order_by(sort_by)
    biometrics = biometrics.order_by(sort_by)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator_leads = Paginator(leads, 10)
    paginator_biometrics = Paginator(biometrics, 10)
    
    page_number = request.GET.get('page')
    leads_page = paginator_leads.get_page(page_number)
    biometrics_page = paginator_biometrics.get_page(page_number)
    
    # Prepare context with cross-table data
    context = {
        'leads': leads_page,
        'biometrics': biometrics_page,
        'total_leads': leads.count(),
        'total_biometrics': biometrics.count(),
        'unique_locations': set(list(leads.values_list('location', flat=True)) + 
                                list(biometrics.values_list('location', flat=True))),
        'approval_trend': leads.annotate(
            approval_month=TruncMonth('created_at')
        ).values('approval_month').annotate(
            lead_count=Count('id')
        ).order_by('approval_month')
    }
    
    return render(request, 'approved_biometrics.html', context)

@login_required
def rejected_biometrics(request):
    """
    View to display only rejected leads and biometrics
    Ensures data consistency and cross-table interactions
    """
    # Base queryset for rejected leads and biometrics
    leads = Lead.objects.filter(status='rejected')
    biometrics = Biometric.objects.filter(status='rejected')
    
    # Filtering
    location_filter = request.GET.get('location')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if location_filter:
        leads = leads.filter(location=location_filter)
        biometrics = biometrics.filter(location=location_filter)
    
    if date_from:
        leads = leads.filter(created_at__date__gte=date_from)
        biometrics = biometrics.filter(rejected_at__date__gte=date_from)
    
    if date_to:
        leads = leads.filter(created_at__date__lte=date_to)
        biometrics = biometrics.filter(rejected_at__date__lte=date_to)
    
    # Sorting
    sort_by = request.GET.get('sort', '-created_at')
    leads = leads.order_by(sort_by)
    biometrics = biometrics.order_by(sort_by)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator_leads = Paginator(leads, 10)
    paginator_biometrics = Paginator(biometrics, 10)
    
    page_number = request.GET.get('page')
    leads_page = paginator_leads.get_page(page_number)
    biometrics_page = paginator_biometrics.get_page(page_number)
    
    # Prepare context with cross-table data
    context = {
        'leads': leads_page,
        'biometrics': biometrics_page,
        'total_leads': leads.count(),
        'total_biometrics': biometrics.count(),
        'unique_locations': set(list(leads.values_list('location', flat=True)) + 
                                list(biometrics.values_list('location', flat=True))),
        'rejection_trend': leads.annotate(
            rejection_month=TruncMonth('created_at')
        ).values('rejection_month').annotate(
            lead_count=Count('id')
        ).order_by('rejection_month')
    }
    
    return render(request, 'rejected_biometrics.html', context)

@login_required
def lead_history(request):
    """
    Display lead history with filtering and pagination
    """
    # Base queryset
    leads = Lead.objects.filter(user=request.user).order_by('-created_at')

    # Filtering
    status = request.GET.get('status')
    location = request.GET.get('location')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if status:
        leads = leads.filter(status=status)
    if location:
        leads = leads.filter(location=location)
    if date_from:
        leads = leads.filter(created_at__date__gte=date_from)
    if date_to:
        leads = leads.filter(created_at__date__lte=date_to)

    # Pagination
    paginator = Paginator(leads, 10)  # 10 leads per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Pre-calculate counts and breakdowns
    total_leads = leads.count()
    approved_leads_count = leads.filter(status='approved').count()
    rejected_leads_count = leads.filter(status='rejected').count()

    # Status breakdown
    status_breakdown = leads.values('status').annotate(
        count=Count('id')
    ).order_by('-count')

    # Location breakdown
    location_breakdown = leads.values('location').annotate(
        count=Count('id')
    ).order_by('-count')

    # Unique filters for sidebar
    unique_statuses = Lead.STATUS_CHOICES
    unique_locations = Lead.objects.filter(user=request.user).values_list('location', flat=True).distinct()

    context = {
        'leads': page_obj,
        'total_leads': total_leads,
        'approved_leads_count': approved_leads_count,
        'rejected_leads_count': rejected_leads_count,
        'status_breakdown': status_breakdown,
        'location_breakdown': location_breakdown,
        'unique_statuses': unique_statuses,
        'unique_locations': unique_locations,
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj
    }

    return render(request, 'lead_history.html', context)

@login_required
def lead_detail(request, lead_id):
    """
    View to display details of a specific lead
    """
    lead = get_object_or_404(Lead, id=lead_id)
    return render(request, 'lead_detail.html', {'lead': lead})

@login_required
def biometric_detail(request, biometric_id):
    """
    View to display details of a specific biometric
    """
    biometric = get_object_or_404(Biometric, id=biometric_id)
    return render(request, 'biometric_detail.html', {'biometric': biometric})

@login_required
def notifications_list(request):
    """
    View to display user notifications with support for AJAX/JSON response
    """
    # Base queryset for all user notifications
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Check if it's an AJAX request for recent notifications
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('recent', 'false') == 'true':
        # Limit to last 5 notifications for dropdown
        notifications = notifications[:5]
        
        notification_data = [{
            'id': n.id,
            'type': n.type,
            'message': n.message,
            'is_read': n.is_read,
            'created_at': n.created_at.strftime('%b %d, %Y %I:%M %p'),
            'ref_id': n.lead_id or n.biometric_id
        } for n in notifications]
        
        return JsonResponse({
            'notifications': notification_data,
            'total_count': Notification.objects.filter(user=request.user).count(),
            'unread_count': Notification.objects.filter(user=request.user, is_read=False).count()
        })
    
    # Pagination
    paginator = Paginator(notifications, 20)  # 20 notifications per page
    page_number = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    context = {
        'notifications': page_obj,
        'total_notifications': notifications.count(),
        'unread_count': Notification.objects.filter(user=request.user, is_read=False).count(),
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj
    }
    return render(request, 'notifications/list.html', context)

@login_required
def mark_notification_read(request, notification_id):
    """
    Mark a specific notification as read
    """
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    
    # If it's an AJAX request, return JSON response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        notification.is_read = True
        notification.save()
        return JsonResponse({
            'status': 'success',
            'message': 'Notification marked as read',
            'unread_count': Notification.objects.filter(user=request.user, is_read=False).count()
        })
    
    # Regular request
    notification.is_read = True
    notification.save()
    
    # Redirect based on notification type
    if notification.lead:
        return redirect('lead_detail', lead_id=notification.lead.id)
    elif notification.biometric:
        return redirect('biometric_detail', biometric_id=notification.biometric.id)
    
    return redirect('notifications_list')

@login_required
def mark_all_notifications_read(request):
    """
    Mark all user notifications as read
    """
    # If it's an AJAX request, return JSON response
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({
            'status': 'success',
            'message': 'All notifications marked as read',
            'unread_count': 0
        })
    
    # Regular request
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('notifications_list')

@login_required
def get_unread_notifications_count(request):
    """
    API endpoint to get unread notifications count
    """
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'unread_count': unread_count})

# Error Handler Views
def bad_request(request, exception=None):
    """
    Custom 400 Bad Request error handler
    """
    return render(request, 'errors/400.html', status=400)

def permission_denied(request, exception=None):
    """
    Custom 403 Permission Denied error handler
    """
    return render(request, 'errors/403.html', status=403)

def page_not_found(request, exception=None):
    """
    Custom 404 Page Not Found error handler
    """
    return render(request, 'errors/404.html', status=404)

def server_error(request):
    """
    Custom 500 Internal Server Error handler
    """
    return render(request, 'errors/500.html', status=500)