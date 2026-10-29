# Generated manually for AnalyticsEvent model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('chatkada', '0005_populate_items'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnalyticsEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(
                    choices=[
                        ('signup', 'User Signup'),
                        ('login', 'User Login'),
                        ('stranger_search_started', 'Stranger Search Started'),
                        ('stranger_match_made', 'Stranger Match Made'),
                        ('message_sent', 'Message Sent'),
                        ('bench_created', 'Bench Created'),
                        ('bench_joined', 'Bench Joined'),
                        ('theatre_created', 'Theatre Created'),
                        ('theatre_joined', 'Theatre Joined'),
                        ('item_bought', 'Item Bought'),
                        ('item_shared', 'Item Shared'),
                        ('challenge_claimed', 'Challenge Claimed'),
                    ],
                    db_index=True,
                    max_length=30
                )),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('metadata_text', models.TextField(blank=True, null=True)),
                ('metadata_int', models.IntegerField(blank=True, null=True)),
                ('related_room', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='chatkada.chatroom'
                )),
                ('related_user', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='related_analytics_events',
                    to=settings.AUTH_USER_MODEL
                )),
                ('user', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='analytics_events',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='analyticsevent',
            index=models.Index(fields=['event_type', 'timestamp'], name='chatkada_an_event_t_idx'),
        ),
        migrations.AddIndex(
            model_name='analyticsevent',
            index=models.Index(fields=['user', 'timestamp'], name='chatkada_an_user_id_idx'),
        ),
    ]
