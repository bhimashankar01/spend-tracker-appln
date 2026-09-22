from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
)
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from .database import (
    Base,
    engine,
    get_db,
)
from .models import Expense, User
from .schemas import (
    CategorySummary,
    ExpenseCreate,
    ExpenseResponse,
    SummaryResponse,
    TokenResponse,
    UserCreate,
)


Base.metadata.create_all(
    bind=engine
)


app = FastAPI(
    title="Spend Tracker API",
    version="1.0.0",
)


app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)


MONEY_QUANT = Decimal("0.01")


def money(
    value: Decimal | float | int,
) -> Decimal:

    return Decimal(
        str(value)
    ).quantize(
        MONEY_QUANT,
        rounding=ROUND_HALF_UP,
    )


def month_bounds(
    year: int,
    month: int,
) -> tuple[date, date]:

    start = date(
        year,
        month,
        1,
    )

    if month == 12:
        end = date(
            year + 1,
            1,
            1,
        )
    else:
        end = date(
            year,
            month + 1,
            1,
        )

    return start, end


def previous_month(
    year: int,
    month: int,
) -> tuple[int, int]:

    if month == 1:
        return year - 1, 12

    return year, month - 1


# --------------------------------------------------
# AUTHENTICATION
# --------------------------------------------------


@app.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=201,
)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):

    username = user_data.username.strip().lower()

    existing_user = db.scalar(
        select(User).where(
            User.username == username
        )
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Username already exists",
        )

    user = User(
        username=username,
        password_hash=hash_password(
            user_data.password
        ),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        user.id
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
    )


@app.post(
    "/auth/login",
    response_model=TokenResponse,
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):

    username = (
        form_data.username
        .strip()
        .lower()
    )

    user = db.scalar(
        select(User).where(
            User.username == username
        )
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    if not verify_password(
        form_data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    token = create_access_token(
        user.id
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
    )


@app.get("/auth/me")
def get_me(
    current_user: User = Depends(
        get_current_user
    ),
):
    return {
        "id": current_user.id,
        "username": current_user.username,
    }


# --------------------------------------------------
# EXPENSES
# --------------------------------------------------


@app.post(
    "/expenses",
    response_model=ExpenseResponse,
    status_code=201,
)
def create_expense(
    expense: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):

    record = Expense(
        user_id=current_user.id,
        amount=expense.amount,
        category=expense.category,
        note=expense.note,
        date=expense.date,
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record


@app.get(
    "/expenses",
    response_model=list[ExpenseResponse],
)
def list_expenses(
    category: str | None = Query(
        default=None
    ),

    start_date: date | None = Query(
        default=None
    ),

    end_date: date | None = Query(
        default=None
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),
):

    if start_date and end_date:
        if start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail=(
                    "start_date cannot be "
                    "after end_date"
                ),
            )

    stmt = select(Expense).where(
        Expense.user_id
        == current_user.id
    )

    if category:
        stmt = stmt.where(
            Expense.category
            == category.strip()
        )

    if start_date:
        stmt = stmt.where(
            Expense.date >= start_date
        )

    if end_date:
        stmt = stmt.where(
            Expense.date <= end_date
        )

    stmt = stmt.order_by(
        Expense.date.desc(),
        Expense.id.desc(),
    )

    return db.scalars(stmt).all()


# --------------------------------------------------
# SUMMARY
# --------------------------------------------------


@app.get(
    "/summary",
    response_model=SummaryResponse,
)
def get_summary(
    year: int | None = Query(
        default=None,
        ge=2000,
        le=2100,
    ),

    month: int | None = Query(
        default=None,
        ge=1,
        le=12,
    ),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),
):

    today = date.today()

    target_year = (
        year
        if year is not None
        else today.year
    )

    target_month = (
        month
        if month is not None
        else today.month
    )

    current_start, current_end = (
        month_bounds(
            target_year,
            target_month,
        )
    )

    previous_year, previous_month_number = (
        previous_month(
            target_year,
            target_month,
        )
    )

    previous_start, previous_end = (
        month_bounds(
            previous_year,
            previous_month_number,
        )
    )

    # ------------------------------------------
    # Current month total
    # ------------------------------------------

    current_total = db.scalar(
        select(
            func.coalesce(
                func.sum(Expense.amount),
                0,
            )
        ).where(
            Expense.user_id
            == current_user.id,

            Expense.date >= current_start,

            Expense.date < current_end,
        )
    )

    # ------------------------------------------
    # Category totals
    # ------------------------------------------

    category_rows = db.execute(
        select(
            Expense.category,

            func.sum(
                Expense.amount
            ).label("total"),
        )
        .where(
            Expense.user_id
            == current_user.id,

            Expense.date >= current_start,

            Expense.date < current_end,
        )
        .group_by(
            Expense.category
        )
        .order_by(
            func.sum(
                Expense.amount
            ).desc()
        )
    ).all()

    # ------------------------------------------
    # Previous month total
    # ------------------------------------------

    previous_total = db.scalar(
        select(
            func.coalesce(
                func.sum(Expense.amount),
                0,
            )
        ).where(
            Expense.user_id
            == current_user.id,

            Expense.date >= previous_start,

            Expense.date < previous_end,
        )
    )

    current_total = money(
        current_total
    )

    previous_total = money(
        previous_total
    )

    # ------------------------------------------
    # Month-over-month percentage
    # ------------------------------------------

    if previous_total == 0:
        change = None
    else:
        change = money(
            (
                (
                    current_total
                    - previous_total
                )
                / previous_total
            )
            * 100
        )

    return SummaryResponse(
        total_spend=current_total,

        spend_by_category=[
            CategorySummary(
                category=category,
                total=money(total),
            )

            for category, total
            in category_rows
        ],

        current_month=(
            f"{target_year:04d}-"
            f"{target_month:02d}"
        ),

        previous_month=(
            f"{previous_year:04d}-"
            f"{previous_month_number:02d}"
        ),

        month_over_month_change_percent=change,
    )


# --------------------------------------------------
# FRONTEND
# --------------------------------------------------


@app.get(
    "/",
    include_in_schema=False,
)
def index():

    return FileResponse(
        "static/index.html"
    )