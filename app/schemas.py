from datetime import date
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class UserCreate(BaseModel):

    username: str = Field(
        min_length=3,
        max_length=100,
    )

    password: str = Field(
        min_length=8,
        max_length=128,
    )

    @field_validator("username")
    @classmethod
    def validate_username(
        cls,
        value: str,
    ) -> str:

        value = value.strip().lower()

        if not value:
            raise ValueError(
                "Username cannot be empty"
            )

        return value


class TokenResponse(BaseModel):

    access_token: str

    token_type: str


class ExpenseCreate(BaseModel):

    amount: Decimal = Field(
        gt=0,
        max_digits=12,
        decimal_places=2,
    )

    category: str = Field(
        min_length=1,
        max_length=100,
    )

    note: str | None = Field(
        default=None,
        max_length=500,
    )

    date: date

    @field_validator("category")
    @classmethod
    def validate_category(
        cls,
        value: str,
    ) -> str:

        value = value.strip()

        if not value:
            raise ValueError(
                "Category cannot be empty"
            )

        return value

    @field_validator("note")
    @classmethod
    def normalize_note(
        cls,
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        value = value.strip()

        return value or None


class ExpenseResponse(BaseModel):

    model_config = ConfigDict(
        from_attributes=True
    )

    id: int
    amount: Decimal
    category: str
    note: str | None
    date: date


class CategorySummary(BaseModel):

    category: str
    total: Decimal


class SummaryResponse(BaseModel):

    total_spend: Decimal

    spend_by_category: list[
        CategorySummary
    ]

    current_month: str

    previous_month: str

    month_over_month_change_percent: (
        Decimal | None
    )