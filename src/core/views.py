from django.http import JsonResponse
from django.db import connection
from django.conf import settings
import redis


def health_check(request):
    """
    Health check endpoint for monitoring and load balancers.
    Returns 200 OK if all services are healthy.
    """
    health_status = {
        'status': 'healthy',
        'services': {}
    }
    status_code = 200

    # Check Database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health_status['services']['database'] = 'healthy'
    except Exception as e:
        health_status['services']['database'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
        status_code = 503

    # Check Redis
    try:
        broker_url = settings.CELERY_BROKER_URL
        # Parse Redis URL
        if broker_url.startswith('redis://'):
            # Extract password if present
            if '@' in broker_url:
                auth_part = broker_url.split('//')[1].split('@')[0]
                if ':' in auth_part:
                    password = auth_part.split(':')[1]
                else:
                    password = None
                host_part = broker_url.split('@')[1].split('/')[0].split(':')[0]
                port = int(broker_url.split('@')[1].split('/')[0].split(':')[1]) if ':' in broker_url.split('@')[1].split('/')[0] else 6379
            else:
                password = None
                host_part = broker_url.split('//')[1].split('/')[0].split(':')[0]
                port = int(broker_url.split('//')[1].split('/')[0].split(':')[1]) if ':' in broker_url.split('//')[1].split('/')[0] else 6379
            
            r = redis.Redis(host=host_part, port=port, password=password, socket_connect_timeout=5)
            r.ping()
            health_status['services']['redis'] = 'healthy'
    except Exception as e:
        health_status['services']['redis'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
        status_code = 503

    return JsonResponse(health_status, status=status_code)
