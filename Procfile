web: cd NomoFlow && gunicorn NomoFlow.wsgi:application --bind 0.0.0.0:$PORT
release: cd NomoFlow && python manage.py migrate --noinput && python manage.py collectstatic --noinput
