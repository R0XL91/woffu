from django.contrib import admin

from api.models import CalendarEvent, WoffuUser, Company, UserRequest


admin.site.register(Company)
admin.site.register(WoffuUser)
admin.site.register(CalendarEvent)
admin.site.register(UserRequest)
