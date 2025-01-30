from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import views as auth_views, logout
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
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
from .search_config import SearchConfiguration
from django.contrib.auth import update_session_auth_hash
import logging
logger = logging.getLogger(__name__)

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
    Home page view with paginated new leads (max 50)
    """
    # Get sorting parameters
    sort_by = request.GET.get('sort', 'created_at')
    order = request.GET.get('order', 'desc')
    page = request.GET.get('page', 1)

    # Define valid sorting fields
    valid_sort_fields = {
        'id': 'id',
        'name': 'name',
        'location': 'location',
        'created_at': 'created_at',
        'email': 'email'
    }

    # Validate sort field
    if sort_by not in valid_sort_fields:
        sort_by = 'created_at'

    # Construct the order
    order_prefix = '-' if order == 'desc' else ''
    
    # Get only new leads with sorting
    new_leads_queryset = Lead.objects.filter(status='new').order_by(f'{order_prefix}{valid_sort_fields[sort_by]}')

    # Paginate the results (limit to 50)
    paginator = Paginator(new_leads_queryset, 50)
    
    try:
        new_leads = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        new_leads = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page of results
        new_leads = paginator.page(paginator.num_pages)

    context = {
        'new_leads': new_leads,
        'current_sort': sort_by,
        'current_order': order,
        'is_paginated': paginator.num_pages > 1,
        'total_leads_count': new_leads_queryset.count()
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
    Create a new lead with default status set to 'new'
    """
    if request.method == 'POST':
        form = LeadForm(request.POST)
        if form.is_valid():
            # Save the lead with default status set to 'new'
            lead = form.save(commit=False)
            lead.user = request.user
            lead.status = 'new'  # Explicitly set default status
            lead.save()
            
            # Create a notification for the new lead
            Notification.objects.create(
                user=request.user,
                type='lead_assigned',
                message=f'New lead created: {lead.name}',
                lead=lead
            )
            
            messages.success(request, f'Lead for {lead.name} created successfully!')
            return redirect('leads_list')
    else:
        form = LeadForm()
    
    return render(request, 'leads/create_lead.html', {'form': form})

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
    Advanced global search with configurable filters and multi-model support
    """
    # Extract search parameters
    query = request.GET.get('query', '').strip()
    search_type = request.GET.get('type', '').strip()
    
    # Prepare advanced filters
    filters = {}
    
    # Lead-specific filters
    lead_status = request.GET.get('lead_status', '').strip()
    lead_location = request.GET.get('lead_location', '').strip()
    
    # Biometric-specific filters
    biometric_status = request.GET.get('biometric_status', '').strip()
    biometric_location = request.GET.get('biometric_location', '').strip()
    
    # Populate filters based on search type and parameters
    if search_type == 'lead' or not search_type:
        if lead_status:
            filters['lead_status'] = lead_status
        if lead_location:
            filters['lead_location'] = lead_location
    
    if search_type == 'biometric' or not search_type:
        if biometric_status:
            filters['biometric_status'] = biometric_status
        if biometric_location:
            filters['biometric_location'] = biometric_location
    
    # Determine search models based on type
    models = ['lead', 'biometric']
    if search_type == 'lead':
        models = ['lead']
    elif search_type == 'biometric':
        models = ['biometric']
    
    # Perform advanced search
    try:
        all_results = SearchConfiguration.advanced_search(
            query=query, 
            model=models, 
            filters=filters
        )
    except Exception as e:
        messages.error(request, f"Search error: {str(e)}")
        all_results = []
    
    # Get filter suggestions for the search form
    filter_suggestions = SearchConfiguration.get_filter_suggestions()
    
    # Pagination
    paginator = Paginator(all_results, 10)  # 10 results per page
    page_number = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
    # Prepare context
    context = {
        'query': query,
        'type': search_type,
        'lead_status': lead_status,
        'lead_location': lead_location,
        'biometric_status': biometric_status,
        'biometric_location': biometric_location,
        'results': page_obj,
        'total_results': len(all_results),
        'is_paginated': len(all_results) > 10,
        'search_fields': SearchConfiguration.get_search_fields(),
        'filter_suggestions': filter_suggestions
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
    
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    
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
    Display user notifications with fallback for empty notifications and error handling
    """
    try:
        # Fetch existing notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
        
        # If no notifications, create some dummy notifications
        if not notifications.exists():
            dummy_notifications = [
                {
                    'type': 'system_alert',
                    'message': 'Welcome to Biometric Leads! You have no active notifications yet.',
                    'created_at': timezone.now(),
                    'is_read': False
                },
                {
                    'type': 'weekly_report',
                    'message': 'Your weekly system overview will be available soon.',
                    'created_at': timezone.now() - timedelta(days=1),
                    'is_read': False
                }
            ]
            
            # Create dummy notifications for the current user
            for dummy in dummy_notifications:
                Notification.objects.create(
                    user=request.user,
                    type=dummy['type'],
                    message=dummy['message'],
                    is_read=dummy['is_read']
                )
            
            # Refetch notifications
            notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
        
        # Pagination
        paginator = Paginator(notifications, 10)  # Show 10 notifications per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'notifications': page_obj,
            'total_notifications': notifications.count(),
            'unread_notifications': notifications.filter(is_read=False).count(),
            'error': None
        }
    
    except Exception as e:
        # Log the error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error loading notifications: {str(e)}")
        
        # Create a system alert notification about the error
        Notification.objects.create(
            user=request.user,
            type='system_alert',
            message='Unable to load notifications. Please try again later.',
            is_read=False
        )
        
        # Prepare context with error notification
        context = {
            'notifications': [],
            'total_notifications': 0,
            'unread_notifications': 1,
            'error': 'Unable to load notifications. Please try again later.'
        }
    
    return render(request, 'notifications/notifications_list.html', context)

@login_required
def get_unread_notifications_count(request):
    """
    Get count of unread notifications with error handling
    """
    try:
        unread_count = Notification.objects.filter(
            user=request.user, 
            is_read=False
        ).count()
        
        logger.info(f"Unread notifications for {request.user.username}: {unread_count}")
        return JsonResponse({
            'status': 'success',
            'unread_count': unread_count
        })
    except Exception as e:
        logger.error(f"Notification count error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Could not retrieve notifications'
        }, status=500)

@login_required
def mark_all_notifications_read(request):
    """
    Mark all user notifications as read
    """
    try:
        unread_notifications = Notification.objects.filter(
            user=request.user, 
            is_read=False
        )
        count = unread_notifications.count()
        
        unread_notifications.update(is_read=True)
        
        logger.info(f"Marked {count} notifications as read for {request.user.username}")
        return JsonResponse({
            'status': 'success',
            'marked_count': count
        })
    except Exception as e:
        logger.error(f"Mark notifications error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Could not mark notifications'
        }, status=500)

@login_required
def get_current_location(request):
    """
    Handle current location retrieval for the user
    """
    try:
        if request.method == 'POST':
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            
            if latitude and longitude:
                logger.info(f"Location received for user {request.user.username}: {latitude}, {longitude}")
                return JsonResponse({
                    'status': 'success', 
                    'message': 'Location received',
                    'latitude': latitude,
                    'longitude': longitude
                })
        
        logger.warning("Location data not provided")
        return JsonResponse({
            'status': 'error', 
            'message': 'Location data missing'
        }, status=400)
    
    except Exception as e:
        logger.error(f"Location retrieval error: {str(e)}")
        return JsonResponse({
            'status': 'error', 
            'message': 'Internal server error'
        }, status=500)

def global_search(request):
    """
    Enhanced global search with comprehensive logging
    """
    try:
        query = request.GET.get('q', '')
        logger.info(f"Search query received: {query}")
        
        # Existing search logic from your current implementation
        search_config = SearchConfiguration()
        results = search_config.execute_search(query)
        
        logger.info(f"Search returned {len(results)} results")
        return JsonResponse({
            'status': 'success',
            'results': results
        })
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Search failed'
        }, status=500)

@login_required
def mark_notification_read(request, notification_id):
    """
    Mark a specific notification as read
    """
    try:
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
    
    except Exception as e:
        logger.error(f"Mark notification error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'Could not mark notification'
        }, status=500)

@login_required
def user_profile(request):
    """
    Display user profile information
    """
    context = {
        'user': request.user,
        'active_page': 'profile'
    }
    return render(request, 'accounts/user_profile.html', context)

@login_required
def change_password(request):
    """
    Allow user to change their password
    """
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, 'Your password was successfully updated!')
            return redirect('user_profile')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    
    context = {
        'form': form,
        'active_page': 'change_password'
    }
    return render(request, 'accounts/change_password.html', context)

@login_required
def interactive_dashboard(request):
    """
    Provide an interactive dashboard for users to track their leads, 
    biometrics, and overall engagement.
    """
    # Get user's leads
    leads = Lead.objects.filter(user=request.user)
    
    # Calculate lead engagement metrics
    total_leads = leads.count()
    high_engagement_leads = [lead for lead in leads if lead.get_interaction_status() == 'High Engagement']
    
    # Get user's biometrics
    biometrics = Biometric.objects.filter(user=request.user)
    
    # Biometric verification metrics
    total_biometrics = biometrics.count()
    high_confidence_biometrics = [bio for bio in biometrics if bio.get_verification_status() == 'High Confidence']
    
    # Notification tracking
    unread_notifications = Notification.get_unread_count(request.user)
    
    # Prepare context for template
    context = {
        'total_leads': total_leads,
        'high_engagement_leads': high_engagement_leads,
        'total_biometrics': total_biometrics,
        'high_confidence_biometrics': high_confidence_biometrics,
        'unread_notifications': unread_notifications,
        'leads': leads,
        'biometrics': biometrics,
    }
    
    return render(request, 'interactive_dashboard.html', context)

@login_required
def all_leads_status(request):
    """
    Display all leads with their current status
    Supports filtering and pagination
    """
    try:
        # Detailed logging for debugging
        logger.info(f"User {request.user.username} accessing All Leads Status page")
        
        # Get filter parameters
        status = request.GET.get('status', '')
        search_query = request.GET.get('q', '')
        
        logger.info(f"Filters - Status: {status}, Search Query: {search_query}")
        
        # Base queryset with all leads
        leads = Lead.objects.select_related('user', 'biometric').all()
        
        # Apply status filter if provided
        if status:
            leads = leads.filter(status=status)
            logger.info(f"Filtered leads with status: {status}")
        
        # Apply search query if provided
        if search_query:
            leads = leads.filter(
                Q(name__icontains=search_query) | 
                Q(phone__icontains=search_query) | 
                Q(email__icontains=search_query)
            )
            logger.info(f"Applied search filter: {search_query}")
        
        # Annotate leads with additional information
        leads = leads.annotate(
            days_since_creation=ExpressionWrapper(
                timezone.now() - F('created_at'), 
                output_field=DurationField()
            )
        )
        
        # Pagination
        paginator = Paginator(leads, 20)  # 20 leads per page
        page_number = request.GET.get('page')
        
        try:
            page_obj = paginator.page(page_number)
            logger.info(f"Pagination - Page {page_obj.number} of {paginator.num_pages}")
        except PageNotAnInteger:
            page_obj = paginator.page(1)
            logger.warning("Invalid page number, defaulting to first page")
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)
            logger.warning("Page number out of range, showing last page")
        
        # Prepare status choices for filtering
        status_choices = dict(Lead.STATUS_CHOICES)
        
        # Count leads for each status
        status_counts = {
            status: leads.filter(status=status).count() 
            for status, _ in Lead.STATUS_CHOICES
        }
        logger.info(f"Status Counts: {status_counts}")
        
        context = {
            'leads': page_obj,
            'status_choices': status_choices,
            'current_status': status,
            'search_query': search_query,
            'total_leads': leads.count(),
            'status_counts': status_counts
        }
        
        logger.info(f"Rendering template with {len(page_obj)} leads")
        return render(request, 'leads/all_leads_status.html', context)
    
    except Exception as e:
        logger.error(f"Critical error in all_leads_status view: {str(e)}", exc_info=True)
        messages.error(request, f"An unexpected error occurred: {str(e)}")
        return render(request, 'leads/all_leads_status.html', {'error': str(e)})

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

@login_required
def user_dashboard(request):
    """
    Comprehensive user dashboard with detailed statistics and insights
    """
    try:
        # Basic user information
        user = request.user
        
        # Lead-related statistics
        total_leads = Lead.objects.filter(user=user).count()
        leads_by_status = {
            status: Lead.objects.filter(user=user, status=status).count()
            for status, _ in Lead.STATUS_CHOICES
        }
        
        # Biometric-related statistics
        total_biometrics = Biometric.objects.filter(user=user).count()
        biometrics_by_status = {
            status: Biometric.objects.filter(user=user, status=status).count()
            for status, _ in Biometric.STATUS_CHOICES
        }
        
        # Notification statistics
        total_notifications = Notification.objects.filter(user=user).count()
        unread_notifications = Notification.objects.filter(user=user, is_read=False).count()
        
        # Recent activity
        recent_leads = Lead.objects.filter(user=user).order_by('-created_at')[:5]
        recent_notifications = Notification.objects.filter(user=user).order_by('-created_at')[:5]
        
        # Performance metrics
        interaction_scores = [lead.interaction_score for lead in recent_leads]
        avg_interaction_score = sum(interaction_scores) / len(interaction_scores) if interaction_scores else 0
        
        context = {
            'user': user,
            'total_leads': total_leads,
            'leads_by_status': leads_by_status,
            'total_biometrics': total_biometrics,
            'biometrics_by_status': biometrics_by_status,
            'total_notifications': total_notifications,
            'unread_notifications': unread_notifications,
            'recent_leads': recent_leads,
            'recent_notifications': recent_notifications,
            'avg_interaction_score': round(avg_interaction_score, 2),
            'profile_completion_percentage': calculate_profile_completion(user)
        }
        
        logger.info(f"User Dashboard accessed by {user.username}")
        return render(request, 'leads/user_dashboard.html', context)
    
    except Exception as e:
        logger.error(f"Error in user_dashboard view: {str(e)}", exc_info=True)
        messages.error(request, f"An error occurred while loading your dashboard: {str(e)}")
        return render(request, 'leads/user_dashboard.html', {'error': str(e)})

def calculate_profile_completion(user):
    """
    Calculate user profile completion percentage
    """
    try:
        profile_fields = [
            'first_name', 'last_name', 'email', 
            'userprofile__phone', 'userprofile__location'
        ]
        
        total_fields = len(profile_fields)
        completed_fields = sum(
            1 for field in profile_fields 
            if getattr(user, field.split('__')[-1] if '__' in field else field)
        )
        
        completion_percentage = (completed_fields / total_fields) * 100
        return round(completion_percentage, 2)
    except Exception as e:
        logger.error(f"Profile completion calculation error: {str(e)}")
        return 0