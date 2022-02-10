from mongoengine import Document, fields


class AbstractAdmin(Document):
    username = fields.StringField(max_length=50, unique=True)
    password = fields.StringField(max_length=200)

    meta = {
        'abstract': True
    }
