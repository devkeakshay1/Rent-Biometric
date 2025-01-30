from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Lead, Biometric, Notification

@receiver(post_save, sender=Lead)
def create_lead_notification(sender, instance, created, **kwargs):
    """
    Create a notification when a lead is created or its status changes
    """
    if created:
        # Notification for lead assignment
        Notification.objects.create(
            user=instance.user or User.objects.first(),
            type='lead_assigned',
            message=f'New lead assigned: {instance.name}',
            lead=instance
        )
    elif hasattr(kwargs, 'update_fields') and 'status' in kwargs['update_fields']:
        # Notification for lead status change
        Notification.objects.create(
            user=instance.user or User.objects.first(),
            type='lead_status_change',
            message=f'Lead status changed to {instance.get_status_display()}',
            lead=instance
        )

@receiver(post_save, sender=Biometric)
def create_biometric_notification(sender, instance, created, **kwargs):
    """
    Create a notification when a biometric is created or its status changes
    """
    if created:
        # Notification for biometric creation
        Notification.objects.create(
            user=instance.user,
            type='biometric_status_change',
            message=f'New biometric record created for {instance.name}',
            biometric=instance
        )
    elif hasattr(kwargs, 'update_fields') and 'status' in kwargs['update_fields']:
        # Notification for biometric status change
        Notification.objects.create(
            user=instance.user,
            type='biometric_status_change',
            message=f'Biometric status changed to {instance.get_status_display()}',
            biometric=instance
        )
