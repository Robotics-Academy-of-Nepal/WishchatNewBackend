# registration/migrations/0011_populate_verify_token.py
from django.db import migrations
import uuid

def populate_verify_tokens(apps, schema_editor):
    Chatbot = apps.get_model('registration', 'Chatbot')
    for chatbot in Chatbot.objects.all():
        chatbot.verify_token = str(uuid.uuid4())
        chatbot.save()

class Migration(migrations.Migration):
    dependencies = [
        ('registration', '0010_chatbot_verify_token'),
    ]
    operations = [
        migrations.RunPython(populate_verify_tokens),
    ]