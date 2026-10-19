"""Domain errors: plain Python, service-prefixed codes (rule X-3). No framework imports (rule L-2).

They are *input* problems; the application layer translates them to the contract's NotificationsInvalidRequest.
"""

from platform_core.errors import InvalidInputError


class NotificationsDomainError(InvalidInputError):
    default_code = "NOTIFICATIONS_ERROR"


class InvalidRecipient(NotificationsDomainError):
    default_code = "NOTIFICATIONS_INVALID_RECIPIENT"
    default_message = "The recipient is not a valid phone number (E.164) or email address."


class UnknownTemplate(NotificationsDomainError):
    default_code = "NOTIFICATIONS_UNKNOWN_TEMPLATE"
    default_message = "There is no such message template."


class TemplateVariablesMismatch(NotificationsDomainError):
    default_code = "NOTIFICATIONS_TEMPLATE_VARIABLES"
    default_message = "The template variables do not match what the template needs."
