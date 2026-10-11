"""Import every table so SQLModel.metadata is complete for Alembic and tests."""
from app.db.models.account import Account
from app.db.models.ai_insight import AIInsight
from app.db.models.audit_log import AuditLog
from app.db.models.budget import Budget
from app.db.models.category import Category
from app.db.models.conversation import Conversation, ConversationMessage
from app.db.models.document import Document
from app.db.models.document_chunk import DocumentChunk
from app.db.models.financial_goal import FinancialGoal
from app.db.models.import_job import ImportJob
from app.db.models.recurring_transaction import RecurringTransaction
from app.db.models.refresh_token import RefreshToken
from app.db.models.transaction import Transaction
from app.db.models.user import User

__all__ = [
    "Account", "AIInsight", "AuditLog", "Budget", "Category", "Conversation", "ConversationMessage",
    "Document", "DocumentChunk", "FinancialGoal", "ImportJob", "RecurringTransaction",
    "RefreshToken", "Transaction", "User",
]
