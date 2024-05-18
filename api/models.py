from __future__ import unicode_literals

import logging
from datetime import datetime

import requests
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from api import BASE_URL

log = logging.getLogger(__name__)


class Company(models.Model):
    name = models.CharField(max_length=200, verbose_name="Name")
    company_id = models.PositiveIntegerField(verbose_name="Company ID")
    woffu_key = models.CharField(max_length=200, verbose_name="Woffu Key")
    token = models.CharField(
        max_length=200, verbose_name="Token", blank=True, null=True
    )
    token_expiration = models.DateTimeField(
        verbose_name="Token Expiration", blank=True, null=True
    )
    updated_at = models.DateField(verbose_name="Updated At", null=True, blank=True)

    def is_valid_token(self):
        """Check if the token is still valid.

        Returns:
            bool: True if the token is still valid, False otherwise.
        """
        return self.token and self.token_expiration and self.token_expiration > timezone.now()

    def get_company_token(self) -> str | None:
        """
        Retrieves the access token for the given company.

        Args:
            company: The company object for which to retrieve the access token.

        Returns:
            The access token for the company, or None if an error occurred.

        Raises:
            String with the company token or None if an error occurred.
        """
        if self.is_valid_token():
            return self.token
        # If the token is expired, we request a new one
        url = f"{BASE_URL}/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.company_id,
            "client_secret": self.woffu_key,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = requests.post(url, data=data, headers=headers, timeout=5)
        if response.status_code == 200:
            header_data = response.json()
            if "access_token" not in header_data and "expires_in" not in header_data:
                log.error("Error getting access token: %s", response.text)
                return None
            # Reload the token in the db for all the users of the same company
            self.token = header_data["access_token"]
            self.token_expiration = datetime.datetime.now() + \
                datetime.timedelta(seconds=header_data["expires_in"])
            self.save()
            return self.token
        log.error("Error getting access token: %s", response.text)
        return None

    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"

    def __str__(self):
        return f"{self.name}"


class WoffuUser(models.Model):
    woffu_id = models.PositiveIntegerField(
        verbose_name="Woffu ID", unique=True
    )
    email = models.EmailField(verbose_name="Email")
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, verbose_name="Company"
    )
    calendar_id = models.PositiveIntegerField(
        verbose_name="Calendar ID"
    )
    active = models.BooleanField(verbose_name="Active", default=True)
    updated_at = models.DateField(verbose_name="Updated At", null=True, blank=True)

    class Meta:
        verbose_name = "Woffu User"
        verbose_name_plural = "Woffu Users"
        unique_together = ("email", "company")

    def __str__(self):
        return f"{self.company}: {self.email}{'' if self.active else ' (Inactive)'}"


class CalendarEvent(models.Model):
    name = models.CharField(max_length=200, verbose_name="Name")
    calendar_id = models.PositiveIntegerField(verbose_name="Calendar ID")
    date = models.DateField(verbose_name="Date")

    class Meta:
        verbose_name = "Calendar Event"
        verbose_name_plural = "Calendar Events"

    def __str__(self):
        return f"{self.calendar_id}: {self.name} ({self.date})"


class UserRequest(models.Model):
    id = models.PositiveIntegerField(primary_key=True, unique=True, verbose_name="ID", db_index=True)
    woffu_user = models.ForeignKey(
        WoffuUser, on_delete=models.CASCADE, verbose_name="Woffu User"
    )
    init_date = models.DateField(verbose_name="Init Date")
    end_date = models.DateField(verbose_name="End Date")

    class Meta:
        verbose_name = "Request"
        verbose_name_plural = "Requests"
        ordering = ["woffu_user", "-init_date"]

    def __str__(self):
        return f"{self.woffu_user} - {self.init_date}/{self.end_date}"


@receiver(post_save, sender=Company)
def process_company_users(sender, instance, created, **kwargs):
    from api.utils import get_calendar_events, get_company_users, get_users_requests
    if created:
        get_company_users(company=instance)
        get_calendar_events(company=instance)
        get_users_requests(company=instance)
