#!/usr/bin/env bash
set -o errexit

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Running migrations..."
python run_migrations.py

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Build completed!"