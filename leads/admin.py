from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.db.models import Count
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin
from import_export import resources

from .models import Lead, Biometric

# Resources for Import/Export functionality
class LeadResource(resources.ModelResource):
    class Meta:
        model = Lead
        fields = ('id', 'name', 'email', 'location', 'status', 'created_at')

class BiometricResource(resources.ModelResource):
    class Meta:
        model = Biometric
        fields = ('id', 'user__username', 'name', 'location', 'status', 'created_at')

# Custom Admin Classes
@admin.register(Lead)
class LeadAdmin(ImportExportModelAdmin):
    resource_class = LeadResource
    
    list_display = (
        'id', 'name', 'email', 'location', 
        'status', 'created_at', 'status_color'
    )
    list_filter = ('status', 'location', 'created_at')
    search_fields = ('name', 'email', 'location')
    list_editable = ('status',)
    list_per_page = 20
    date_hierarchy = 'created_at'
    
    def status_color(self, obj):
        color_map = {
            'new': 'blue',
            'in_progress': 'orange',
            'approved': 'green',
            'rejected': 'red'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color_map.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_color.short_description = 'Status'

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            total_biometrics=Count('biometric', distinct=True)
        )

    def total_biometrics_count(self, obj):
        return obj.total_biometrics
    total_biometrics_count.short_description = 'Total Biometrics'

@admin.register(Biometric)
class BiometricAdmin(ImportExportModelAdmin):
    resource_class = BiometricResource
    
    list_display = (
        'id', 'user', 'name', 'location', 
        'status', 'created_at', 'status_color'
    )
    list_filter = ('status', 'location', 'created_at')
    search_fields = ('name', 'location', 'user__username')
    list_editable = ('status',)
    list_per_page = 20
    date_hierarchy = 'created_at'
    
    def status_color(self, obj):
        color_map = {
            'pending': 'orange',
            'approved': 'green',
            'rejected': 'red'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color_map.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_color.short_description = 'Status'

# Custom User Admin to show related data
class UserProfileInline(admin.StackedInline):
    model = Biometric
    extra = 0
    readonly_fields = ('name', 'location', 'status', 'created_at')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

class CustomUserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = (
        'username', 'email', 'first_name', 'last_name', 
        'is_active', 'date_joined', 'biometric_count'
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            biometric_count=Count('biometric', distinct=True)
        )
    
    def biometric_count(self, obj):
        return obj.biometric_count
    biometric_count.short_description = 'Biometrics'

# Replace default User admin with custom admin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# Admin site configuration
admin.site.site_header = 'Bio-Lead Administration'
admin.site.site_title = 'Bio-Lead Admin Portal'
admin.site.index_title = 'Welcome to Bio-Lead Management System'
