from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from api.models import CalendarEvent, Company, UserRequest, WoffuUser
from api.utils import (
    get_calendar_events,
    get_company_users,
    get_user_request,
    get_users_requests,
)

admin.site.register(CalendarEvent)
admin.site.register(UserRequest)


@admin.action(description="Sync user requests")
def sync_user_requests(modeladmin, request, queryset):
    for woffu_user in queryset:
        get_user_request(woffu_user=woffu_user)


class WoffuUserClass(admin.ModelAdmin):
    list_display = [
        "email", "company", "active", "sync_user_request"
    ]
    actions = [sync_user_requests,]

    def sync_user_request(self, obj):
        action_url = reverse("sync_user_request", args=[obj.pk, ])
        return format_html(f"<a href='{action_url}'>Click here to sync user requests</a>")
    sync_user_request.short_description = "Actions"

admin.site.register(WoffuUser, WoffuUserClass)


@admin.action(description="Sync company users")
def sync_company(modeladmin, request, queryset):
    for company in queryset:
        get_company_users(company=company)


class CompanyClass(admin.ModelAdmin):
    list_display = [
        "name", "sync_company_users"
    ]
    actions = [sync_company,]

    def sync_company_users(self, obj):
        action_url = reverse("sync_company_users", args=[obj.pk, ])
        return format_html(f"<a href='{action_url}'>Click here to get users company and calendar events for the company</a>")
    sync_company_users.short_description = "Actions"

admin.site.register(Company, CompanyClass)
