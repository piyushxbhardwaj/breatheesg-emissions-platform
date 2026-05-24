#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static assets for production
python manage.py collectstatic --no-input

# Apply database migrations
python manage.py migrate

# Seed database with default tenants and emission factors
python manage.py seed_data
