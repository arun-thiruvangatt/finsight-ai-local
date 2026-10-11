from enum import StrEnum


class Role(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"


class AccountType(StrEnum):
    BANK = "BANK"
    CREDIT_CARD = "CREDIT_CARD"
    CASH = "CASH"
    WALLET = "WALLET"
    INVESTMENT = "INVESTMENT"
    LOAN = "LOAN"
    OTHER = "OTHER"


class CategoryType(StrEnum):
    EXPENSE = "EXPENSE"
    INCOME = "INCOME"
    TRANSFER = "TRANSFER"


class TransactionType(StrEnum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    TRANSFER = "TRANSFER"


class BudgetPeriod(StrEnum):
    MONTHLY = "MONTHLY"
    WEEKLY = "WEEKLY"
    CUSTOM = "CUSTOM"


class ImportStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class GoalStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"


class GoalPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class InsightType(StrEnum):
    SPENDING_INCREASE = "SPENDING_INCREASE"
    UNUSUAL_TRANSACTION = "UNUSUAL_TRANSACTION"
    BUDGET_WARNING = "BUDGET_WARNING"
    RECURRING_EXPENSE = "RECURRING_EXPENSE"
    SAVING_OPPORTUNITY = "SAVING_OPPORTUNITY"
    CATEGORY_TREND = "CATEGORY_TREND"
    MONTHLY_SUMMARY = "MONTHLY_SUMMARY"
    GOAL_PROGRESS = "GOAL_PROGRESS"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class Frequency(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class DocumentStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class DocumentType(StrEnum):
    NOTE = "NOTE"
    INSURANCE = "INSURANCE"
    LOAN = "LOAN"
    PLAN = "PLAN"
    STATEMENT = "STATEMENT"
    OTHER = "OTHER"


# Default per-user category tree: name -> (type, [children])
DEFAULT_CATEGORIES: dict[str, tuple[str, list[str]]] = {
    "Food": ("EXPENSE", ["Groceries", "Restaurants", "Food Delivery"]),
    "Transport": ("EXPENSE", ["Fuel", "Public Transport", "Cab"]),
    "Shopping": ("EXPENSE", []),
    "Bills": ("EXPENSE", ["Electricity", "Internet", "Mobile", "Rent"]),
    "Entertainment": ("EXPENSE", []),
    "Healthcare": ("EXPENSE", []),
    "Other": ("EXPENSE", []),
    "Salary": ("INCOME", []),
    "Other Income": ("INCOME", []),
    "Transfers": ("TRANSFER", []),
}

ALLOWED_UPLOAD_EXT_CSV = {".csv", ".txt"}
ALLOWED_UPLOAD_EXT_DOC = {".txt", ".md", ".pdf"}

AI_DISCLAIMER = (
    "Figures are calculated from your recorded data. Explanations are AI-generated and any "
    "projections are estimates, not guaranteed outcomes or financial advice."
)
