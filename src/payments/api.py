"""HTTP for payments. Parses requests and shapes responses; the rules live in
services.py. No payment endpoints yet: paying a booking belongs to the booking
team, and this service will expose its own endpoints (e.g. refunds) here."""

from flask import Blueprint

bp = Blueprint("payments", __name__)
