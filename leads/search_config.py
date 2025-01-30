from django.db.models import Q
from .models import Lead, Biometric, Notification

class SearchConfiguration:
    """
    Advanced search configuration for complex, multi-model searches
    """
    @staticmethod
    def get_search_fields():
        """
        Define searchable fields for each model
        """
        return {
            'lead': [
                {'field': 'name', 'label': 'Name', 'type': 'text'},
                {'field': 'email', 'label': 'Email', 'type': 'text'},
                {'field': 'phone', 'label': 'Phone', 'type': 'text'},
                {'field': 'location', 'label': 'Location', 'type': 'text'},
                {'field': 'status', 'label': 'Status', 'type': 'choice', 'choices': dict(Lead.STATUS_CHOICES)},
                {'field': 'created_at', 'label': 'Created Date', 'type': 'date'}
            ],
            'biometric': [
                {'field': 'name', 'label': 'Name', 'type': 'text'},
                {'field': 'location', 'label': 'Location', 'type': 'text'},
                {'field': 'status', 'label': 'Status', 'type': 'choice', 'choices': dict(Biometric.STATUS_CHOICES)},
                {'field': 'created_at', 'label': 'Created Date', 'type': 'date'}
            ],
            'notification': [
                {'field': 'type', 'label': 'Notification Type', 'type': 'choice', 'choices': dict(Notification.NOTIFICATION_TYPES)},
                {'field': 'message', 'label': 'Message', 'type': 'text'},
                {'field': 'is_read', 'label': 'Read Status', 'type': 'boolean'}
            ]
        }

    @staticmethod
    def advanced_search(query=None, model=None, filters=None):
        """
        Perform an advanced, configurable search across multiple models
        
        :param query: Global search term
        :param model: Specific model to search ('lead', 'biometric', 'notification')
        :param filters: Dictionary of specific field filters
        :return: Queryset of search results
        """
        results = []
        
        # Default to searching all models if not specified
        if not model:
            model = ['lead', 'biometric', 'notification']
        elif isinstance(model, str):
            model = [model]
        
        # Normalize filters
        filters = filters or {}
        
        # Search Leads
        if 'lead' in model:
            lead_query = Lead.objects.all()
            
            # Global text search
            if query:
                lead_query = lead_query.filter(
                    Q(name__icontains=query) | 
                    Q(email__icontains=query) | 
                    Q(phone__icontains=query) | 
                    Q(location__icontains=query)
                )
            
            # Apply specific filters
            for field, value in filters.items():
                if field in ['name', 'email', 'phone', 'location', 'status']:
                    lead_query = lead_query.filter(**{f'{field}__iexact': value})
            
            results.extend([
                {
                    'type': 'Lead',
                    'id': lead.id,
                    'name': lead.name,
                    'email': lead.email,
                    'phone': lead.phone,
                    'location': lead.location,
                    'status': lead.get_status_display(),
                    'created_at': lead.created_at,
                    'detail_url': f'/lead/{lead.id}/'
                } for lead in lead_query
            ])
        
        # Search Biometrics
        if 'biometric' in model:
            biometric_query = Biometric.objects.all()
            
            # Global text search
            if query:
                biometric_query = biometric_query.filter(
                    Q(name__icontains=query) | 
                    Q(location__icontains=query)
                )
            
            # Apply specific filters
            for field, value in filters.items():
                if field in ['name', 'location', 'status']:
                    biometric_query = biometric_query.filter(**{f'{field}__iexact': value})
            
            results.extend([
                {
                    'type': 'Biometric',
                    'id': biometric.id,
                    'name': biometric.name,
                    'location': biometric.location,
                    'status': biometric.get_status_display(),
                    'created_at': biometric.created_at,
                    'detail_url': f'/biometric/{biometric.id}/'
                } for biometric in biometric_query
            ])
        
        # Search Notifications
        if 'notification' in model:
            notification_query = Notification.objects.all()
            
            # Global text search
            if query:
                notification_query = notification_query.filter(
                    Q(message__icontains=query) | 
                    Q(type__icontains=query)
                )
            
            # Apply specific filters
            for field, value in filters.items():
                if field in ['type', 'is_read']:
                    notification_query = notification_query.filter(**{f'{field}__iexact': value})
            
            results.extend([
                {
                    'type': 'Notification',
                    'id': notification.id,
                    'message': notification.message,
                    'type': notification.get_type_display(),
                    'is_read': 'Read' if notification.is_read else 'Unread',
                    'created_at': notification.created_at,
                    'detail_url': '/notifications/'
                } for notification in notification_query
            ])
        
        # Sort results by created_at
        results.sort(key=lambda x: x.get('created_at', timezone.now()), reverse=True)
        
        return results

    @staticmethod
    def get_filter_suggestions(model=None):
        """
        Generate filter suggestions based on existing data
        
        :param model: Specific model to get suggestions for
        :return: Dictionary of filter suggestions
        """
        suggestions = {}
        
        if not model or model == 'lead':
            suggestions['lead'] = {
                'status_options': dict(Lead.STATUS_CHOICES),
                'locations': list(Lead.objects.values_list('location', flat=True).distinct()),
            }
        
        if not model or model == 'biometric':
            suggestions['biometric'] = {
                'status_options': dict(Biometric.STATUS_CHOICES),
                'locations': list(Biometric.objects.values_list('location', flat=True).distinct()),
            }
        
        if not model or model == 'notification':
            suggestions['notification'] = {
                'type_options': dict(Notification.NOTIFICATION_TYPES),
            }
        
        return suggestions
