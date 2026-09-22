from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def client(tmp_path: Path):

    database_file = (
        tmp_path / "test.db"
    )

    engine = create_engine(
        f"sqlite:///{database_file}",
        connect_args={
            "check_same_thread": False
        },
    )

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    Base.metadata.create_all(
        bind=engine
    )

    def override_get_db():

        db = TestingSessionLocal()

        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[
        get_db
    ] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()

    engine.dispose()


def register(
    client,
    username="alice",
    password="password123",
):

    response = client.post(
        "/auth/register",
        json={
            "username": username,
            "password": password,
        },
    )

    assert response.status_code == 201

    return response.json()[
        "access_token"
    ]


def auth_headers(token):

    return {
        "Authorization":
            f"Bearer {token}"
    }


def create_expense(
    client,
    token,
    amount,
    category,
    expense_date,
    note=None,
):

    return client.post(
        "/expenses",
        json={
            "amount": amount,
            "category": category,
            "note": note,
            "date": expense_date,
        },
        headers=auth_headers(token),
    )


def test_register_and_login(client):

    token = register(client)

    assert token

    response = client.post(
        "/auth/login",
        data={
            "username": "alice",
            "password": "password123",
        },
    )

    assert response.status_code == 200

    assert (
        response.json()["token_type"]
        == "bearer"
    )


def test_protected_endpoint_requires_token(
    client,
):

    response = client.get(
        "/expenses"
    )

    assert response.status_code == 401


def test_create_and_list_expense(
    client,
):

    token = register(client)

    response = create_expense(
        client,
        token,
        "25.50",
        "Food",
        "2026-09-10",
        "Lunch",
    )

    assert response.status_code == 201

    response = client.get(
        "/expenses",
        headers=auth_headers(token),
    )

    assert response.status_code == 200

    expenses = response.json()

    assert len(expenses) == 1

    assert (
        expenses[0]["category"]
        == "Food"
    )


def test_invalid_long_password(
    client,
):

    long_password = "a" * 73

    response = client.post(
        "/auth/register",
        json={
            "username": "alice",
            "password": long_password,
        },
    )

    assert response.status_code == 422


def test_user_cannot_see_another_users_expenses(
    client,
):

    alice_token = register(
        client,
        "alice",
        "password123",
    )

    bob_token = register(
        client,
        "bob",
        "password123",
    )

    create_expense(
        client,
        alice_token,
        "100",
        "Food",
        "2026-09-10",
    )

    response = client.get(
        "/expenses",
        headers=auth_headers(
            bob_token
        ),
    )

    assert response.status_code == 200

    assert response.json() == []


def test_summary_is_user_specific(
    client,
):

    alice_token = register(
        client,
        "alice",
        "password123",
    )

    bob_token = register(
        client,
        "bob",
        "password123",
    )

    create_expense(
        client,
        alice_token,
        "100",
        "Food",
        "2026-09-10",
    )

    create_expense(
        client,
        bob_token,
        "500",
        "Travel",
        "2026-09-10",
    )

    response = client.get(
        "/summary?year=2026&month=9",
        headers=auth_headers(
            alice_token
        ),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_spend"] == "100.00"


def test_rejects_invalid_amount(
    client,
):

    token = register(client)

    response = create_expense(
        client,
        token,
        "0",
        "Food",
        "2026-09-10",
    )

    assert response.status_code == 422


def test_rejects_invalid_date_range(
    client,
):

    token = register(client)

    response = client.get(
        "/expenses",
        params={
            "start_date":
                "2026-09-20",
            "end_date":
                "2026-09-01",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 400


def test_filters_by_date_range(
    client,
):

    token = register(client)

    create_expense(
        client,
        token,
        "10",
        "Food",
        "2026-09-01",
    )

    create_expense(
        client,
        token,
        "20",
        "Travel",
        "2026-09-15",
    )

    create_expense(
        client,
        token,
        "30",
        "Food",
        "2026-10-01",
    )

    response = client.get(
        "/expenses",
        params={
            "start_date":
                "2026-09-01",
            "end_date":
                "2026-09-30",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 200

    assert len(
        response.json()
    ) == 2


def test_summary_and_month_over_month_change(
    client,
):

    token = register(client)

    # Previous month = 100
    create_expense(
        client,
        token,
        "100",
        "Food",
        "2026-08-10",
    )

    # Current month = 150
    create_expense(
        client,
        token,
        "100",
        "Food",
        "2026-09-10",
    )

    create_expense(
        client,
        token,
        "50",
        "Travel",
        "2026-09-15",
    )

    response = client.get(
        "/summary",
        params={
            "year": 2026,
            "month": 9,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 200

    data = response.json()

    assert (
        data["total_spend"]
        == "150.00"
    )

    assert (
        data[
            "month_over_month_change_percent"
        ]
        == "50.00"
    )

    categories = {
        item["category"]:
            item["total"]

        for item
        in data[
            "spend_by_category"
        ]
    }

    assert (
        categories["Food"]
        == "100.00"
    )

    assert (
        categories["Travel"]
        == "50.00"
    )


def test_summary_change_null_when_previous_month_zero(
    client,
):

    token = register(client)

    create_expense(
        client,
        token,
        "75",
        "Food",
        "2026-09-10",
    )

    response = client.get(
        "/summary",
        params={
            "year": 2026,
            "month": 9,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 200

    assert (
        response.json()[
            "month_over_month_change_percent"
        ]
        is None
    )