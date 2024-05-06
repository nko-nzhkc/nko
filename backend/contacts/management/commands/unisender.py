import os
from django.apps import apps
from django.core.management.base import BaseCommand, CommandParser
from dotenv import load_dotenv

from contacts.models import Contact
from donor_base.unisender_client import Client

load_dotenv()


cl = Client(
    api_key=os.getenv('UNISENDER_API_KEY'),
    platform="donor_base",
)
method = 'import_contacts'
data_unisender = {'field_names': ['email', 'Name', 'email_list_ids'],
                  'data': [], 
                  'overwrite_lists': 1}

cont = Contact.objects.all()
data = []
for x in cont:
    donor_contact = [x.email, x.username, 'Oldest_donors']
    data.append(donor_contact)
data_unisender['data'] = data

class Command(BaseCommand):
    def add_data(self, parser: CommandParser) -> None:
        parser.add_argument(data_unisender)
    def handle(self, *args, **options):
        pass
    cl._api_request(method, data_unisender)
