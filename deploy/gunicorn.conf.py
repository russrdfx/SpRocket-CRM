import os
bind='0.0.0.0:'+os.environ.get('PORT','8000')
workers=1
worker_class='gthread'
threads=8
timeout=180
accesslog=None
errorlog='-'
# Exactly one process owns OAuth pending requests, sync continuation and the scheduler.
