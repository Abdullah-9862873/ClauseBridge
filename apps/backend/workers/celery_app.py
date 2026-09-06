from celery import Celery

from core.config import settings

celery_app = Celery(
    "clausebridge",
    broker=settings.redis_url,
    include=["workers.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)