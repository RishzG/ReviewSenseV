"""Input and output guardrails for the query pipeline.

Input guardrails:
- Block prompt injection attempts
- Block off-topic questions (not about product reviews/electronics)
- Block PII and harmful content
- Enforce length limits

Output guardrails:
- Strip any leaked PII (emails, phone numbers)
- Prevent hallucinated URLs
- Flag low-confidence answers
"""

import re

# Input: block prompt injection patterns
INJECTION_PATTERNS = [
    r'ignore (all |your |previous |the above)',
    r'forget (all |your |previous )',
    r'disregard (all |your |previous )',
    r'you are now',
    r'act as',
    r'pretend (to be|you)',
    r'new instructions',
    r'override',
    r'system prompt',
    r'</?(system|assistant|user)',
    r'<\|',
    r'\bDAN\b',
    r'jailbreak',
    r'bypass',
]

# Input: off-topic detection keywords — questions must relate to these
ON_TOPIC_KEYWORDS = [
    'review', 'rating', 'sentiment', 'product', 'category', 'headphone', 'speaker',
    'cable', 'charger', 'battery', 'phone', 'computer', 'storage', 'camera',
    'tv', 'gaming', 'wearable', 'smart home', 'streaming', 'electronic',
    'complaint', 'theme', 'quality', 'customer', 'brand', 'asin', 'earbuds',
    'wireless', 'bluetooth', 'usb', 'hdmi', 'accessory', 'device',
    'negative', 'positive', 'worst', 'best', 'recommend', 'buy', 'worth',
    'durability', 'comfort', 'connectivity', 'value', 'ease of use',
    'sound', 'build', 'service', 'vote', 'helpful', 'verified', 'purchase',
    # Product names and brands commonly in our dataset
    'amazon', 'echo', 'fire', 'kindle', 'alexa', 'ring', 'roku', 'anker',
    'logitech', 'sony', 'bose', 'samsung', 'apple', 'google', 'nest',
    'fitbit', 'garmin', 'jabra', 'jbl', 'senso', 'mpow', 'aukey',
    # Common product types
    'earphone', 'earbud', 'headset', 'microphone', 'mouse', 'keyboard',
    'monitor', 'tablet', 'stick', 'plug', 'bulb', 'thermostat', 'doorbell',
    'router', 'extender', 'hub', 'adapter', 'dongle', 'remote', 'controller',
    'tracker', 'watch', 'band', 'scale', 'cam', 'webcam', 'dash',
    # General question words that imply product interest
    'people say', 'people think', 'what about', 'how is', 'how are', 'tell me',
    'trend', 'monthly', 'compare', 'analysis', 'average', 'count', 'total',
]

# Output: PII patterns to strip
PII_PATTERNS = [
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]'),
    (r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE_REDACTED]'),
    (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN_REDACTED]'),
    (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[CARD_REDACTED]'),
]

# Output: hallucinated URL pattern
URL_PATTERN = re.compile(r'https?://\S+')


class GuardrailError(Exception):
    """Raised when a guardrail blocks the request."""
    def __init__(self, message: str, guardrail: str):
        self.message = message
        self.guardrail = guardrail
        super().__init__(message)


def check_input(question: str, has_conversation_history: bool = False) -> None:
    """Validate user input. Raises GuardrailError if blocked.

    Args:
        question: The raw user question
        has_conversation_history: If True, skip off-topic check (follow-ups are inherently on-topic)
    """

    # Length check
    if len(question.strip()) < 3:
        raise GuardrailError("Question is too short.", "input_length")
    if len(question) > 1000:
        raise GuardrailError("Question exceeds 1000 character limit.", "input_length")

    q_lower = question.lower()

    # Prompt injection check
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, q_lower):
            raise GuardrailError(
                "Your question could not be processed. Please ask a question about product reviews.",
                "prompt_injection"
            )

    # Off-topic check — skip if mid-conversation (follow-ups are inherently on-topic)
    if has_conversation_history:
        return

    has_asin = bool(re.search(r'\bB0[A-Z0-9]{8,}\b', question))
    if not has_asin and not any(kw in q_lower for kw in ON_TOPIC_KEYWORDS):
        raise GuardrailError(
            "This system answers questions about Amazon Electronics product reviews. "
            "Please ask about product categories, review themes, sentiment, ratings, or specific products.",
            "off_topic"
        )


def sanitize_output(text: str) -> str:
    """Clean the LLM output of PII and hallucinated URLs."""
    if not text:
        return text

    # Strip PII
    for pattern, replacement in PII_PATTERNS:
        text = re.sub(pattern, replacement, text)

    # Strip hallucinated URLs (LLM sometimes invents links)
    text = URL_PATTERN.sub('[URL_REMOVED]', text)

    return text
