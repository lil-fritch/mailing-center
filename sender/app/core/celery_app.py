from celery import Celery

app = Celery(
    'worker',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/1'
)

@app.task(name='send_email_task')
def send_email_task(campaign_id, studio_id, email_data):
    print(f"Обробляю email для campaign_id={campaign_id}, studio_id={studio_id}")
    print(email_data)
    # Тут ваша логіка відправки email
    # send_actual_email(email_data)