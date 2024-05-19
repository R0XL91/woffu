from datetime import timedelta

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from api.models import CalendarEvent, Company, UserRequest, WoffuUser
from api.utils import get_company_users, get_user_request

admin.site.register(CalendarEvent)


@admin.action(description="Sync user requests")
def sync_user_requests(modeladmin, request, queryset):
    for woffu_user in queryset:
        get_user_request(woffu_user=woffu_user)


class WoffuUserAdmin(admin.ModelAdmin):
    list_display = [
        "email", "company", "active", "sync_user_request_display"
    ]
    actions = [sync_user_requests,]

    def sync_user_request_display(self, obj):
        action_url = reverse("sync_user_request", args=[obj.pk, ])
        return format_html(f"<a href='{action_url}'>Click here to sync user requests</a>")
    sync_user_request_display.short_description = "Actions"

admin.site.register(WoffuUser, WoffuUserAdmin)


@admin.action(description="Sync company users")
def sync_company(modeladmin, request, queryset):
    for company in queryset:
        get_company_users(company=company)


class CompanyAdmin(admin.ModelAdmin):
    list_display = [
        "name", "sync_company_users_display"
    ]
    actions = [sync_company,]

    def sync_company_users_display(self, obj):
        action_url = reverse("sync_company_users", args=[obj.pk, ])
        return format_html(
            f"<a href='{action_url}'>Click here to get users company and calendar events for the company</a>"
        )
    sync_company_users_display.short_description = "Actions"

admin.site.register(Company, CompanyAdmin)


class UserRequestAdmin(admin.ModelAdmin):
    list_display = [
        "woffu_user", "days_display", "init_date", "end_date"
    ]

    def days_display(self, obj):
        dates = [obj.init_date + timedelta(x + 1) for x in range((obj.end_date - obj.init_date).days)]
        days = 0 if obj.init_date.weekday() >= 5 else 1
        days += sum(1 for day in dates if day.weekday() < 5)
        return days
    days_display.short_description = "Number of days"

admin.site.register(UserRequest, UserRequestAdmin)
