"""Seabay V1.5 — All frozen enumerations (30 types)."""

from __future__ import annotations

import enum


class AgentType(str, enum.Enum):
    SERVICE = "service"
    PERSONAL = "personal"
    PROXY = "proxy"
    WORKER = "worker"
    ORG = "org"


class OwnerType(str, enum.Enum):
    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"


class AgentStatus(str, enum.Enum):
    ONLINE = "online"
    BUSY = "busy"
    AWAY = "away"
    OFFLINE = "offline"
    SUSPENDED = "suspended"
    BANNED = "banned"


class VisibilityScope(str, enum.Enum):
    PUBLIC = "public"
    NETWORK_ONLY = "network_only"
    CIRCLE_ONLY = "circle_only"
    PRIVATE = "private"


class ContactPolicy(str, enum.Enum):
    PUBLIC_SERVICE_ONLY = "public_service_only"
    KNOWN_DIRECT = "known_direct"
    INTRO_ONLY = "intro_only"
    CIRCLE_REQUEST = "circle_request"
    CLOSED = "closed"


class IntroductionPolicy(str, enum.Enum):
    OPEN = "open"
    CONFIRM_REQUIRED = "confirm_required"
    CLOSED = "closed"


class VerificationLevel(str, enum.Enum):
    NONE = "none"
    EMAIL = "email"
    GITHUB = "github"
    DOMAIN = "domain"
    WORKSPACE = "workspace"
    MANUAL_REVIEW = "manual_review"


VERIFICATION_WEIGHTS: dict[VerificationLevel, int] = {
    VerificationLevel.NONE: 0,
    VerificationLevel.EMAIL: 1,
    VerificationLevel.GITHUB: 2,
    VerificationLevel.DOMAIN: 2,
    VerificationLevel.WORKSPACE: 3,
    VerificationLevel.MANUAL_REVIEW: 4,
}


class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"
    REVOKED = "revoked"


class RelationshipStrength(str, enum.Enum):
    NEW = "new"
    ACQUAINTANCE = "acquaintance"
    TRUSTED = "trusted"
    FREQUENT = "frequent"


class OriginType(str, enum.Enum):
    PUBLIC_SERVICE = "public_service"
    IMPORTED_CONTACT = "imported_contact"
    CLAIMED_HANDLE = "claimed_handle"
    SAME_CIRCLE = "same_circle"
    INTRODUCED = "introduced"
    PLATFORM_VOUCHED = "platform_vouched"
    COLLABORATED = "collaborated"
    NONE = "none"


class OriginStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class CircleJoinMode(str, enum.Enum):
    INVITE_ONLY = "invite_only"
    REQUEST_APPROVE = "request_approve"
    OPEN_LINK = "open_link"


class CircleContactMode(str, enum.Enum):
    DIRECTORY_ONLY = "directory_only"
    REQUEST_ONLY = "request_only"
    DIRECT_ALLOWED = "direct_allowed"


class CircleRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class CircleJoinRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class IntentCategory(str, enum.Enum):
    SERVICE_REQUEST = "service_request"
    COLLABORATION = "collaboration"
    INTRODUCTION = "introduction"
    PEOPLE_REQUEST = "people_request"
    PUBLICATION_REQUEST = "publication_request"


class IntentStatus(str, enum.Enum):
    ACTIVE = "active"
    MATCHED = "matched"
    FULFILLED = "fulfilled"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class AudienceScope(str, enum.Enum):
    PUBLIC = "public"
    NETWORK = "network"
    # circle:{circle_id} is handled as a string pattern, not enum


class TaskType(str, enum.Enum):
    SERVICE_REQUEST = "service_request"
    COLLABORATION = "collaboration"
    INTRODUCTION = "introduction"


class TaskStatus(str, enum.Enum):
    DRAFT = "draft"                              # reserved, not implemented
    PENDING_DELIVERY = "pending_delivery"
    DELIVERED = "delivered"
    PENDING_ACCEPT = "pending_accept"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    WAITING_HUMAN_CONFIRM = "waiting_human_confirm"
    COMPLETED = "completed"
    DECLINED = "declined"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    FAILED = "failed"


# Valid task state transitions
TASK_TRANSITIONS: dict[TaskStatus, list[TaskStatus]] = {
    TaskStatus.PENDING_DELIVERY: [
        TaskStatus.DELIVERED,
        TaskStatus.FAILED,
        TaskStatus.EXPIRED,
        TaskStatus.CANCELLED,
    ],
    TaskStatus.DELIVERED: [
        TaskStatus.PENDING_ACCEPT,
        TaskStatus.EXPIRED,
        TaskStatus.CANCELLED,
    ],
    TaskStatus.PENDING_ACCEPT: [
        TaskStatus.ACCEPTED,
        TaskStatus.DECLINED,
        TaskStatus.EXPIRED,
        TaskStatus.CANCELLED,
    ],
    TaskStatus.ACCEPTED: [
        TaskStatus.IN_PROGRESS,
        TaskStatus.CANCELLED,
    ],
    TaskStatus.IN_PROGRESS: [
        TaskStatus.COMPLETED,
        TaskStatus.WAITING_HUMAN_CONFIRM,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    ],
    TaskStatus.WAITING_HUMAN_CONFIRM: [
        TaskStatus.COMPLETED,
        TaskStatus.CANCELLED,
        TaskStatus.EXPIRED,
    ],
}


class RiskLevel(str, enum.Enum):
    R0 = "R0"   # Pure info / search — auto
    R1 = "R1"   # Low-risk coordination — preferred auto
    R2 = "R2"   # Must confirm (4h timeout)
    R3 = "R3"   # Strong confirm (12h timeout)


def requires_human_confirm(risk: RiskLevel) -> bool:
    return risk in (RiskLevel.R2, RiskLevel.R3)


# High-risk intent keyword → risk level mapping
HIGH_RISK_KEYWORDS: dict[str, RiskLevel] = {
    "payment": RiskLevel.R3,
    "pay": RiskLevel.R3,
    "purchase": RiskLevel.R3,
    "buy": RiskLevel.R3,
    "order": RiskLevel.R3,
    "place_order": RiskLevel.R3,
    "checkout": RiskLevel.R3,
    "transfer": RiskLevel.R3,
    "withdraw": RiskLevel.R3,
    "meet_offline": RiskLevel.R3,
    "in_person": RiskLevel.R3,
    "read_private": RiskLevel.R3,
    "connect_mcp": RiskLevel.R3,
    "grant_access": RiskLevel.R3,
    "booking": RiskLevel.R2,
    "reservation": RiskLevel.R2,
    "appointment": RiskLevel.R2,
    "email_send": RiskLevel.R2,
    "send_email": RiskLevel.R2,
    "contact_person": RiskLevel.R2,
    "dm_send": RiskLevel.R2,
    "message_human": RiskLevel.R2,
    "share_contact": RiskLevel.R2,
    "share_info": RiskLevel.R2,
    "confirm_on_behalf": RiskLevel.R2,
    "sign": RiskLevel.R2,
    "agree": RiskLevel.R2,
    "access_private": RiskLevel.R3,
    "delete": RiskLevel.R2,
    "cancel_subscription": RiskLevel.R2,
}


class HumanConfirmChannel(str, enum.Enum):
    HOSTED_WEB = "hosted_web"
    MAGIC_LINK = "magic_link"
    EMBEDDED_LAUNCH_URL = "embedded_launch_url"


class InteractionOutcome(str, enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    ERROR = "error"


class ReportReasonCode(str, enum.Enum):
    SPAM = "spam"
    IMPERSONATION = "impersonation"
    UNSAFE_REQUEST = "unsafe_request"
    POLICY_VIOLATION = "policy_violation"
    HARASSMENT = "harassment"
    OTHER = "other"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    ACTIONED = "actioned"
    DISMISSED = "dismissed"


class IntroductionStatus(str, enum.Enum):
    PENDING = "pending"
    A_ACCEPTED = "a_accepted"
    B_ACCEPTED = "b_accepted"
    BOTH_ACCEPTED = "both_accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class DLPPattern(str, enum.Enum):
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    API_KEY = "api_key"
    SECRET = "secret"
    ADDRESS = "address"


class DLPAction(str, enum.Enum):
    WARNING = "warning"
    BLOCKED = "blocked"
    CONFIRMED_OVERRIDE = "confirmed_override"


class DirectorySort(str, enum.Enum):
    RECENT_ACTIVE = "recent_active"
    TRUST_FIRST = "trust_first"
    NEWEST = "newest"


# Risk capabilities a service agent can declare
class RiskCapability(str, enum.Enum):
    PAYMENT = "payment"
    EMAIL_SEND = "email_send"
    BOOKING = "booking"
    DM_SEND = "dm_send"
    PRIVATE_DATA_ACCESS = "private_data_access"
    MCP_CONNECT = "mcp_connect"
    IRREVERSIBLE_ACTION = "irreversible_action"


# ── Phase B enums ──

class PublicationType(str, enum.Enum):
    SERVICE = "service"
    PRODUCT = "product"
    PROJECT_OPENING = "project_opening"
    EVENT = "event"
    EXCHANGE = "exchange"
    REQUEST = "request"


class PublicationStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    EXPIRED = "expired"


class TaskMessageType(str, enum.Enum):
    TEXT = "text"
    PROPOSAL = "proposal"
    COUNTER = "counter"
    ACCEPT = "accept"
    REJECT = "reject"
    INFO = "info"


class PeopleRequestStatus(str, enum.Enum):
    PENDING = "pending"
    MUTUAL = "mutual"
    DECLINED = "declined"
    EXPIRED = "expired"


# ── Phase C enums ──

class OrgRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class PolicyType(str, enum.Enum):
    CONTACT = "contact"
    VISIBILITY = "visibility"
    TASK_APPROVAL = "task_approval"
    RATE_LIMIT = "rate_limit"
    AGENT_TYPE = "agent_type"
