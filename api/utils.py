import datetime
import logging
import requests

from django.utils import timezone

from api.models import CalendarEvent, WoffuUser, UserRequest

BASE_URL = "https://app.woffu.com"

log = logging.getLogger(__name__)


def get_company_token(company):
    if company.token_expiration and timezone.now() < company.token_expiration:
        # We store the token in db to avoid too many requests
        return company.token
    # If the token is expired, we request a new one
    url = f"{BASE_URL}/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": company.company_id,
        "client_secret": company.woffu_key,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(url, data=data, headers=headers, timeout=5)
    if response.status_code == 200:
        header_data = response.json()
        # Reload the token in the db for all the users of the same company
        company.token = header_data["access_token"]
        company.token_expiration = datetime.datetime.now() + datetime.timedelta(
            seconds=header_data["expires_in"]
        )
        company.save()
        return company.token
    log.error("Error getting access token: %s", response.text)
    return None


def get_company_users(company, show_hidden_users=False):
    if not company.token or not company.token_expiration or company.token_expiration < timezone.now():
        # We check if the token is expired
        get_company_token(company=company)
    url = f"{BASE_URL}/api/v1/users"
    headers = {
        "Authorization": "Bearer " + company.token,
        "Content-Type": "application/json",
    }
    data = {
        "CompanyId": company.company_id,
        "showHidden": show_hidden_users,
    }
    data = requests.get(url=url, headers=headers, timeout=5, data=data)
    if data.status_code == 200:
        users = data.json()
        for user in users:
            WoffuUser.objects.get_or_create(
                woffu_id=user["UserId"],
                email=user["Email"],
                company=company,
                calendar_id=user["CalendarId"],
            )
        return True
    elif data.status_code == 400:
        log.error("Error getting company users: %s", data.text)
    elif data.status_code == 500:
        log.error("Error getting company users: %s", data.text)
    return False


def get_calendar_events(company, calendar_id=None):
    """_summary_

    Args:
        company (_type_): _description_
    """
    if not company.token or not company.token_expiration or company.token_expiration < timezone.now():
        # We check if the token is expired
        get_company_token(company=company)

    if not calendar_id:
        calendar_ids = company.woffuuser_set.filter(active=True).values_list("calendar_id", flat=True).distinct()
    else:
        calendar_ids = [calendar_id]

    for calendar in calendar_ids:
        url = f"{BASE_URL}/api/v1/calendars/{calendar}/events"
        headers = {
            "Authorization": "Bearer " + company.token,
            "Content-Type": "application/json",
        }
        data = requests.get(url=url, headers=headers, timeout=5)
        if data.status_code == 200:
            dates = []
            events = CalendarEvent.objects.filter(calendar_id=calendar).values_list("date", flat=True)
            for event in data.json():
                event_date = datetime.datetime.strptime(event["Date"], "%Y-%m-%dT%H:%M:%S.000").date()
                dates.append(event_date)
                if event_date not in events:
                    CalendarEvent.objects.get_or_create(
                        name=event["Name"], calendar_id=calendar, date=event_date
                    )
            # Remove events that are not in the calendar anymore
            CalendarEvent.objects.filter(calendar_id=calendar).exclude(
                date__in=dates
            ).delete()


def get_user_requests(company):
    if not company.token_expiration or company.token_expiration < timezone.now():
        # We check if the token is expired
        get_company_token(company=company)
    url = f"{BASE_URL}/api/v1/requests"
    headers = {
        "Authorization": "Bearer " + company.token,
        "Content-Type": "application/json",
    }
    data = requests.get(url=url, headers=headers, timeout=10)
    if data.status_code == 200:
        for request in data.json()["Views"]:
            woffu_user = WoffuUser.objects.get(woffu_id=request["UserId"])
            init_date = datetime.datetime.strptime(request["StartDate"], "%Y-%m-%dT%H:%M:%S.000").date()
            end_date = datetime.datetime.strptime(request["EndDate"], "%Y-%m-%dT%H:%M:%S.000").date()
            if not UserRequest.objects.filter(woffu_user=woffu_user, init_date=init_date, end_date=end_date).exists():
                UserRequest.objects.create(
                    woffu_user=woffu_user,
                    init_date=init_date,
                    end_date=end_date,
                )


def sign(woffu_user, date, sign_in):
    """_summary_

    Args:
        woffu_user (_type_): _description_
        date (_type_): _description_
        sign_in (_type_): _description_

    Returns:
        _type_: _description_
    """
    if date.weekday() in [5, 6]:
        # Don't sign on weekends
        return None
    company = woffu_user.company
    if CalendarEvent.objects.filter(calendar_id=woffu_user.calendar_id, date=date).exists():
        # Don't sign on national holidays
        return None
    if UserRequest.objects.filter(woffu_user=woffu_user, init_date__gte=date, end_date__lte=date).exists():
        # Don't sign on user holidays
        return None
    if not company.token_expiration or company.token_expiration < timezone.now():
        # Check if the token is expired
        get_company_token(company=company)
    url = f"{BASE_URL}/api/v1/signs"
    data = {
        "Date": date.isoformat() + ".00",
        "UserID": woffu_user.woffu_id,
        "CompanyId": woffu_user.company_id,
        "SignIn": sign_in,
    }
    headers = {
        "Authorization": "Bearer " + woffu_user.token,
        "Content-Type": "application/json",
    }
    data = requests.post(
        url=url, json=data, headers=headers, timeout=10
    )
    return data.ok
