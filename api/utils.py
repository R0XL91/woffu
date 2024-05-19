import datetime
import logging

import requests

from api import BASE_URL
from api.decorators import check_valid_token
from api.models import CalendarEvent, Company, UserRequest, WoffuUser

log = logging.getLogger(__name__)


@check_valid_token
def get_company_users(company: Company, show_hidden_users: bool = False) -> bool:
    """
    Retrieves the users associated with a company from the Woffu API.

    Args:
        company (Company): The company object representing the company.
        show_hidden_users (bool, optional): Whether to include hidden users. Defaults to False.

    Returns:
        bool: True if the users were successfully retrieved and stored in the database, False otherwise.
    """
    url = f"{BASE_URL}/api/v1/users"
    headers = {
        "Authorization": "Bearer " + company.token,
        "Content-Type": "application/json",
    }
    data = {
        "CompanyId": company.company_id,
        "showHidden": show_hidden_users,
    }
    data = requests.get(url=url, headers=headers, timeout=10, data=data)
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
    else:
        log.error(f"Unknown error in user requests changes: {data.status_code} - {data.text}")
    return False


@check_valid_token
def get_calendar_events(company: Company, calendar_id: int = None) -> None:
    """
    Retrieves calendar events from the Woffu API for the specified company and calendar.

    Args:
        company (Company): The company object for which to retrieve calendar events.
        calendar_id (int, optional): The ID of the specific calendar to retrieve events from. If not provided,
            events will be retrieved for all active calendars associated with the company.

    Returns:
        None
    """
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
        elif data.status_code == 400:
            log.error("Bad request getting calendar events: %s", data.text)
        elif data.status_code == 404:
            log.error("Calendar not found")
        elif data.status_code == 500:
            log.error("Internal server error: %s", data.text)
        else:
            log.error(f"Unknown error in calendar events: {data.status_code} - {data.text}")


@check_valid_token
def get_users_requests(company: Company) -> bool:
    """
    Retrieves user requests from the Woffu API for a given company.

    Args:
        company (Company): The company object for which to retrieve user requests.

    Returns:
        None
    """
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
            if not UserRequest.objects.filter(id=request["RequestId"], woffu_user=woffu_user).exists():
                UserRequest.objects.create(
                    id=request["RequestId"],
                    woffu_user=woffu_user,
                    init_date=init_date,
                    end_date=end_date,
                )
        return True
    elif data.status_code == 400:
        log.error("Bad request getting user requests: %s", data.text)
    elif data.status_code == 500:
        log.error("Internal server error: %s", data.text)
    else:
        log.error(f"Unknown error in user requests: {data.status_code} - {data.text}")
    return False


@check_valid_token
def get_user_request(woffu_user: WoffuUser, to_date: datetime.date = None) -> None:
    """
    Retrieves user requests from the Woffu API and updates the database accordingly.

    Args:
        woffu_user (WoffuUser): The WoffuUser object representing the user.
        to_date (datetime.date, optional): The end date for filtering requests. Defaults to None.

    Returns:
        None
    """
    init_date = woffu_user.updated_at
    if init_date and to_date and to_date < init_date:
        return
    url = f"{BASE_URL}/api/v1/users/{woffu_user.woffu_id}/requests"
    headers = {
        "Authorization": "Bearer " + woffu_user.company.token,
        "Content-Type": "application/json",
    }
    data = {}
    if init_date:
        data["fromDate"] = init_date.isoformat()
    if to_date:
        data["toDate"] = to_date.isoformat()
    data = requests.get(url=url, headers=headers, timeout=10)
    if data.status_code == 200:
        # Deleted = True -> Deleted
        # UpdatedOn and Deleted = False -> Updated
        # UpdatedOn = False and Deleted = False -> Created
        for user_request in data.json()["Views"]:
            deleted = user_request.get("Deleted", None)
            updated_on = user_request.get("UpdatedOn", None)
            init_date = datetime.datetime.strptime(user_request["StartDate"], "%Y-%m-%dT%H:%M:%S.000").date()
            end_date = datetime.datetime.strptime(user_request["EndDate"], "%Y-%m-%dT%H:%M:%S.000").date()
            if deleted:
                UserRequest.objects.get(id=user_request["RequestId"]).delete()
            elif not deleted and updated_on:
                UserRequest.objects.filter(
                    id=user_request["RequestId"]
                ).update(
                    init_date=init_date, end_date=end_date,
                )
            else:
                if not UserRequest.objects.filter(id=user_request["RequestId"]).exists():
                    UserRequest.objects.create(
                        id=user_request["RequestId"], woffu_user=woffu_user,
                        init_date=init_date, end_date=end_date,
                    )
        woffu_user.updated_at = datetime.datetime.now().date()
    elif data.status_code == 500:
        log.error("Internal server error: %s", data.text)
    else:
        log.error(f"Unknown error in user requests: {data.status_code} - {data.text}")


# TODO: CHECK THIS UTILS
@check_valid_token
def get_requests_changes(company: Company, to_date: datetime.date = None) -> None:
    """
    Retrieves and processes the changes in user requests from the Woffu API.

    Args:
        company (Company): The company object.
        to_date (datetime.date, optional): The end date to filter the changes. Defaults to None.

    Returns:
        None
    """
    from_date = company.updated_on
    if to_date and to_date < from_date:
        return
    url = f"{BASE_URL}/api/v1/requests/changes"
    headers = {
        "Authorization": "Bearer " + company.token,
        "Content-Type": "application/json",
    }
    data = {"fromDate": company.updated_on.isoformat()}
    if to_date:
        data["toDate"] = to_date.isoformat()
    data = requests.get(url=url, headers=headers, data=data, timeout=10)
    if data.status_code == 200:
        # Deleted = True -> Deleted
        # UpdatedOn and Deleted = False -> Updated
        # UpdatedOn = False and Deleted = False -> Created
        for user_request in data.json()["Views"]:
            deleted = user_request.get("Deleted", None)
            updated_on = user_request.get("UpdatedOn", None)
            if deleted:
                UserRequest.objects.get(id=user_request["RequestId"]).delete()
            elif not deleted and updated_on:
                UserRequest.objects.filter(
                    id=user_request["RequestId"]
                ).update(
                    init_date=user_request["StartDate"],
                    end_date=user_request["EndDate"],
                )
            else:
                woffu_user = WoffuUser.objects.get(woffu_id=user_request["UserId"])
                UserRequest.objects.create(
                    id=user_request["RequestId"],
                    woffu_user=woffu_user,
                    init_date=user_request["StartDate"],
                    end_date=user_request["EndDate"],
                )
        company.updated_at = datetime.datetime.now().date()
        company.save()
    elif data.status_code == 400:
        log.error("Error getting requests changes: %s", data.text)
    elif data.status_code == 500:
        log.error("Error getting requests changes: %s", data.text)


@check_valid_token
def sign(woffu_user: WoffuUser, date: datetime.date, sign_in: bool) -> bool:
    """
    Signs in or signs out a Woffu user for a given date.

    Args:
        woffu_user (WoffuUser): The Woffu user to sign in or sign out.
        date (datetime.date): The date for which the user needs to be signed in or signed out.
        sign_in (bool): A boolean indicating whether the user needs to be signed in (True) or signed out (False).

    Returns:
        bool: True if the sign-in/sign-out request was successful, False otherwise.
    """
    if date.weekday() in [5, 6]:
        # Don't sign on weekends
        return None
    if CalendarEvent.objects.filter(calendar_id=woffu_user.calendar_id, date=date).exists():
        # Don't sign on calendar events
        return None
    if UserRequest.objects.filter(woffu_user=woffu_user, init_date__gte=date, end_date__lte=date).exists():
        # Don't sign on user holidays
        return None
    url = f"{BASE_URL}/api/v1/signs"
    data = {
        "Date": date.isoformat() + ".00",
        "UserID": woffu_user.woffu_id,
        "CompanyId": woffu_user.company_id,
        "SignIn": sign_in,
    }
    headers = {
        "Authorization": "Bearer " + woffu_user.company.token,
        "Content-Type": "application/json",
    }
    data = requests.post(
        url=url, json=data, headers=headers, timeout=10
    )
    return data.ok
