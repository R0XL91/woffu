from __future__ import unicode_literals

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


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

    class Meta:
        verbose_name = "Woffu User"
        verbose_name_plural = "Woffu Users"
        unique_together = ("email", "company")

    def __str__(self):
        return f"{self.email}{'' if self.active else ' (Inactive)'}"


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
    from api.utils import get_company_users, get_calendar_events, get_user_requests
    if created:
        get_company_users(company=instance)
        get_calendar_events(company=instance)
        get_user_requests(company=instance)
