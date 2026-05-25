from django.db import migrations

def create_initial_plans(apps, schema_editor):
    Plan = apps.get_model('subscriptions', 'Plan')
    
    # Data: ID, Name, Price, Msg Limit, Doc Limit, Image Limit
    plans = [
        {
            "id": 1,
            "name": "FREE",
            "price": 0,
            "daily_message_limit": 20,
            "daily_document_limit": 10,
            "daily_image_limit": 30
        },
        {
            "id": 2,
            "name": "PRO",
            "price": 10000000,
            "daily_message_limit": 50,
            "daily_document_limit": 50,
            "daily_image_limit": 10
        },
    ]

    for plan_data in plans:
        Plan.objects.update_or_create(id=plan_data['id'], defaults=plan_data)

def remove_initial_plans(apps, schema_editor):
    Plan = apps.get_model('subscriptions', 'Plan')
    Plan.objects.filter(id__in=[1, 2]).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0005_userusage'), #
    ]

    operations = [
        migrations.RunPython(create_initial_plans, reverse_code=remove_initial_plans),
    ]
