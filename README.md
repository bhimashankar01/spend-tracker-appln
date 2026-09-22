Spend Tracker

A small expense-tracking service built with Python, FastAPI, SQLite, SQLAlchemy, and a minimal vanilla JavaScript UI.

Features

Create expenses with amount, category, note, and date.
List expenses.
View monthly total spend.
View spend grouped by category.

Automated tests covering creation, validation, filtering, summary calculations, and edge cases.
Minimal browser UI for adding expenses and viewing the summary.

Requirements
Python 3.11+
pip
Run locally
Create and activate a virtual environment:
python -m venv .venv
source .venv/bin/activate

On Windows:
.venv\Scripts\activate
Install dependencies:
pip install -r requirements.txt

Start the API:
uvicorn app.main:app --reload

Test Runs:
python -m pytest

Open:
http://127.0.0.1:8000

Interactive API documentation is available at:
http://127.0.0.1:8000/docs
