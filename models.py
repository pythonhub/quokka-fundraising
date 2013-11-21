# coding: utf-8

import datetime
from quokka.core.db import db
from quokka.utils import get_current_user
from quokka.core.models import Publishable
from quokka.modules.cart.models import BaseProduct, BaseProductReference, Cart


class Donations(db.EmbeddedDocument):
    donation = db.ReferenceField('Donation')
    status = db.StringField(default="pending", max_length=255)
    value = db.FloatField(default=0)
    donor = db.StringField(max_length=255)
    show_donor = db.BooleanField(default=True)


class Campaign(BaseProduct):
    description = db.StringField(required=True)
    start_date = db.DateTimeField(default=datetime.datetime.now)
    end_date = db.DateTimeField()
    min_value = db.FloatField(default=0)
    max_value = db.FloatField()
    goal = db.FloatField()
    balance = db.FloatField(default=0)
    open_for_donations = db.BooleanField(default=True)
    donations = db.ListField(db.EmbeddedDocumentField(Donations))

    def __unicode__(self):
        return self.title

    def update_donation(self, donation, value):
        don = self.donations.get(donation=donation)
        if don:
            don.status = donation.status
            don.value = value
            don.donor = donation.donor.name if donation.donor else None
            don.show_donor = donation.published
        else:
            don = Donations(
                donation=donation,
                status=donation.status,
                value=value,
                donor=donation.donor.name if donation.donor else None,
                show_donor=donation.published
            )
            self.donations.append(don)
        self.save()

    def get_donor_list(self):
        return [
            donation.donor
            for donation in
            self.donations.filter(show_donor=True, status="confirmed")
        ]

    def save(self, *args, **kwargs):
        self.balance = sum(
            [item.value for item in self.donations.filter(status="confirmed")]
        )
        super(Campaign, self).save(*args, **kwargs)


class Values(db.EmbeddedDocument):
    campaign = db.ReferenceField(Campaign)
    value = db.FloatField(default=0)

    def __unicode__(self):
        return u"{s.campaign} - {s.value}".format(s=self)


class Donation(BaseProductReference, Publishable, db.DynamicDocument):
    status = db.StringField(default="pending", max_length=255)
    values = db.ListField(db.EmbeddedDocumentField(Values))
    total = db.FloatField(default=0)
    tax = db.FloatField(default=0)
    donor = db.ReferenceField('User', default=get_current_user, required=False)

    cart = db.ReferenceField(Cart, reverse_delete_rule=db.NULLIFY)
    confirmed_date = db.DateTimeField()

    def __unicode__(self):
        return u"{s.donor} - {s.total}".format(s=self)

    def set_status(self, status, *args, **kwargs):
        self.status = status
        if status == "confirmed":
            now = datetime.datetime.now()
            self.confirmed_date = kwargs.get('date', now)
        self.save()

    def clean(self):
        unique_values = {
            unique: 0
            for unique in set([item.campaign for item in self.values])
        }
        for item in self.values:
            unique_values[item.campaign] += item.value

        self.values = [
            Values(campaign=campaign, value=value)
            for campaign, value in unique_values.items()
        ]

        if self.values:
            self.total = sum([item.value for item in self.values])

    def save(self, *args, **kwargs):
        super(Donation, self).save(*args, **kwargs)

        for item in self.values:
            item.campaign.update_donation(self, item.value)
