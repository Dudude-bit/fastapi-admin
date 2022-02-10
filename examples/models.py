import datetime

from mongoengine import Document, fields

from examples.enums import ProductType, Status
from fastapi_admin.models import AbstractAdmin


class Admin(AbstractAdmin):
    last_login = fields.DateTimeField(description="Last Login", default=datetime.datetime.now)
    email = fields.StringField(max_length=200, default="")
    avatar = fields.StringField(max_length=200, default="")
    intro = fields.StringField(default="")
    created_at = fields.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.pk}#{self.username}"


class Category(Document):
    slug = fields.StringField(max_length=200)
    name = fields.StringField(max_length=200)
    created_at = fields.DateTimeField(auto_now_add=True)


class Product(Document):
    name = fields.StringField(max_length=50)
    view_num = fields.IntField(description="View Num")
    sort = fields.IntField()
    is_reviewed = fields.BooleanField(description="Is Reviewed")
    image = fields.StringField(max_length=200)
    body = fields.StringField()
