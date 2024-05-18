from django.contrib import admin

from api.models import CalendarEvent, Company, UserRequest, WoffuUser

admin.site.register(Company)
admin.site.register(WoffuUser)
admin.site.register(CalendarEvent)
admin.site.register(UserRequest)
