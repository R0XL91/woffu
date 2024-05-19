from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from api.models import Company, WoffuUser
from api.utils import get_calendar_events, get_company_users, get_user_request


def sync_user_request(request, woffu_user_id):
    woffu_user = get_object_or_404(WoffuUser, pk=woffu_user_id)
    get_user_request(woffu_user=woffu_user)
    return HttpResponse(status=204)

def sync_company_users(request, company_id):
    company = get_object_or_404(Company, pk=company_id)
    get_company_users(company=company)
    get_calendar_events(company=company)
    return HttpResponse(status=204)
