"""Built-in message templates. Callers name a template and pass variables; they never send free text.

Why: free text through a gateway is a phishing/spam cannon. A closed template set also lets us check that
the variables are exactly what the template needs. Adding a template = adding an entry below (+ a test).
"""

import re
from dataclasses import dataclass

from notifications_contracts import Channel
from notifications_service.domain.errors import TemplateVariablesMismatch, UnknownTemplate

_PLACEHOLDER = re.compile(r"{(\w+)}")
_MAX_VALUE_LENGTH = 200


@dataclass(frozen=True)
class Template:
    name: str
    subject: str  # used by the email channel only
    body: str

    @property
    def variables(self) -> frozenset[str]:
        return frozenset(_PLACEHOLDER.findall(self.subject + " " + self.body))


@dataclass(frozen=True)
class RenderedMessage:
    subject: str | None
    body: str


TEMPLATES: dict[str, Template] = {
    t.name: t
    for t in (
        Template(
            "otp",
            subject="Your verification code",
            body="Your verification code is {code}. It expires in {ttl_minutes} minutes. Never share it with anyone.",
        ),
        Template("welcome", subject="Welcome, {name}!", body="Hi {name}, your account is ready."),
        Template(
            "password_changed",
            subject="Your password was changed",
            body="Your password was just changed. If this was not you, reset it now.",
        ),
    )
}


def render(template_name: str, channel: Channel, variables: dict[str, str]) -> RenderedMessage:
    template = TEMPLATES.get(template_name)
    if template is None:
        raise UnknownTemplate(details={"template": template_name, "known": sorted(TEMPLATES)})
    needed = template.variables
    missing, extra = needed - variables.keys(), variables.keys() - needed
    if missing or extra:
        raise TemplateVariablesMismatch(
            details={
                "template": template_name,
                "missing": sorted(missing),
                "unexpected": sorted(extra),
            }
        )
    if any(len(v) > _MAX_VALUE_LENGTH for v in variables.values()):
        raise TemplateVariablesMismatch(
            details={"template": template_name, "reason": "value too long"}
        )
    body = template.body.format_map(variables)
    subject = template.subject.format_map(variables) if channel is Channel.EMAIL else None
    return RenderedMessage(subject=subject, body=body)
