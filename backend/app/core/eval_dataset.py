"""
Evaluation dataset — test questions spanning the different agents, each
with an expected/reference answer to compare against.
"""

EVAL_QUESTIONS = [
    {
        "question": "How many customers churned in Q3?",
        "reference": "3 customers churned in Q3.",
        "expects_agent": "data",
    },
    {
        "question": "Why did Enterprise customers churn in Q3?",
        "reference": (
            "Enterprise customers churned in Q3 primarily due to missing "
            "integrations with popular accounting tools, which came up "
            "repeatedly as an objection during renewal conversations."
        ),
        "expects_agent": "retriever",
    },
    {
        "question": "What is 15% of 480?",
        "reference": "72",
        "expects_agent": "code",
    },
    {
        "question": "How many customers churned in Q1?",
        "reference": "2 customers churned in Q1.",
        "expects_agent": "data",
    },
    {
        "question": "What caused churn to drop in Q2?",
        "reference": (
            "Churn dropped in Q2 after an annual billing discount was "
            "introduced and support response time improved."
        ),
        "expects_agent": "retriever",
    },
    {
        "question": "If we retain 92% of customers each quarter starting from 200, how many remain after 4 quarters?",
        "reference": "About 143.",
        "expects_agent": "code",
    },
]