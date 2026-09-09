"""The 50 hand-labeled eval comments (D5).

Hand-written, not sampled from the generated dumps. Sampling would make the eval
set a test of whether the model agrees with `generate_comments.py`'s templates —
if a template is ambiguous, the label inherits that ambiguity and the score
means nothing. These are written and labeled deliberately, including cases that
are genuinely hard, because a set the 2B model scores 100% on would tell us
nothing about whether to promote triage to the standard tier (D4).

Label definitions, applied consistently:
  category    question | complaint | praise | spam | other
  sentiment   -2 hostile, -1 negative, 0 neutral, 1 positive, 2 delighted
  needs_reply true when the author is owed an answer. Questions and complaints
              are true; spam is always false; praise is false unless it also
              asks something.

Category is decided by what the comment DOES, not by how much text it contains.
An emoji-only reaction expressing clear approval is praise — "🔥🔥🔥" on a product
post is the same act as "love this", and filing it under `other` would hide real
positive sentiment from the Inbox. `other` is for comments that do not act on the
brand at all: engagement bait, tagging a friend, a reaction with no valence.

Deliberate composition: ~16 questions, ~10 complaints, ~9 praise, ~5 spam,
~10 other, with sarcasm, mixed sentiment, non-English, and emoji-only among
them. The hard cases are marked `hard` so `make eval` can report accuracy on
them separately — that split is what will actually decide the tier question.
"""

from typing import Any

EVAL: list[dict[str, Any]] = [
    # --- questions -------------------------------------------------------
    {"text": "Does this come in decaf?", "category": "question", "sentiment": 0,
     "needs_reply": True},
    {"text": "Do you ship to Canada, and how long does it usually take?",
     "category": "question", "sentiment": 0, "needs_reply": True},
    {"text": "What percentage niacinamide is in the serum?", "category": "question",
     "sentiment": 0, "needs_reply": True},
    {"text": "can i use this with retinol at night or is that too much",
     "category": "question", "sentiment": 0, "needs_reply": True},
    {"text": "Is the packaging actually recyclable or just the outer box?",
     "category": "question", "sentiment": -1, "needs_reply": True,
     "hard": "a question carrying scepticism — category is question, sentiment is not neutral"},
    {"text": "Hi! Any chance you'll do a bigger size of the barrier serum? I go through "
             "it so fast because I love it.", "category": "question", "sentiment": 2,
     "needs_reply": True,
     "hard": "praise wrapped around a question; the question is what needs answering"},
    {"text": "Do you do wholesale for cafes?", "category": "question", "sentiment": 0,
     "needs_reply": True},
    {"text": "whats the roast date on the guji", "category": "question", "sentiment": 0,
     "needs_reply": True},
    {"text": "Is there a student discount?", "category": "question", "sentiment": 0,
     "needs_reply": True},
    {"text": "When is the SPF launching? You've said 'soon' for four months.",
     "category": "question", "sentiment": -1, "needs_reply": True,
     "hard": "a question with an embedded complaint; still primarily a question"},
    {"text": "Ist das vegan?", "category": "question", "sentiment": 0, "needs_reply": True,
     "hard": "German, three words"},
    {"text": "Bonjour, est-ce que vous livrez en France ?", "category": "question",
     "sentiment": 0, "needs_reply": True, "hard": "French"},
    {"text": "¿Tienen envío a España?", "category": "question", "sentiment": 0,
     "needs_reply": True, "hard": "Spanish"},
    {"text": "Do the refill pouches fit the old bottle or do I need a new one?",
     "category": "question", "sentiment": 0, "needs_reply": True},
    {"text": "Sorry if this is obvious — is the cleanser fragrance free?",
     "category": "question", "sentiment": 0, "needs_reply": True},
    {"text": "Can someone check whether order RR-48210 has shipped? It's been a while.",
     "category": "question", "sentiment": -1, "needs_reply": True,
     "hard": "polite chase; a question, but the customer is drifting negative"},

    # --- complaints ------------------------------------------------------
    {"text": "Order RR-33127 arrived smashed. Two bags split open across the box.",
     "category": "complaint", "sentiment": -2, "needs_reply": True},
    {"text": "This gave me a rash within two days. I want a refund.",
     "category": "complaint", "sentiment": -2, "needs_reply": True,
     "hard": "safety plus refund — this is the urgency=high case"},
    {"text": "Been waiting 11 days with no shipping update at all.",
     "category": "complaint", "sentiment": -1, "needs_reply": True},
    {"text": "Third time the subscription has charged early. Sort it out please.",
     "category": "complaint", "sentiment": -2, "needs_reply": True},
    {"text": "Great, another price rise with no warning. Really valuing your loyal "
             "customers there.", "category": "complaint", "sentiment": -2,
     "needs_reply": True,
     "hard": "sarcasm — surface words are positive, meaning is hostile"},
    {"text": "The new formula is worse than the old one. Genuinely disappointed.",
     "category": "complaint", "sentiment": -1, "needs_reply": True},
    {"text": "arrived stale, roast date was 6 weeks ago", "category": "complaint",
     "sentiment": -1, "needs_reply": True},
    {"text": "I've emailed support three times and had nothing back.",
     "category": "complaint", "sentiment": -2, "needs_reply": True},
    {"text": "Cancelled my subscription last month and you charged me anyway. "
             "This is close to theft.", "category": "complaint", "sentiment": -2,
     "needs_reply": True},
    {"text": "Not the worst coffee I've had, but for the price I expected better.",
     "category": "complaint", "sentiment": -1, "needs_reply": True,
     "hard": "mild, hedged negative — easy to mislabel as neutral or praise"},

    # --- praise ----------------------------------------------------------
    {"text": "This is genuinely the best coffee I've had all year.",
     "category": "praise", "sentiment": 2, "needs_reply": False},
    {"text": "Third bag this month. No notes.", "category": "praise", "sentiment": 2,
     "needs_reply": False},
    {"text": "Finally a brand that just tells you what's actually in the bottle.",
     "category": "praise", "sentiment": 2, "needs_reply": False},
    {"text": "My skin has calmed down so much since switching. Thank you.",
     "category": "praise", "sentiment": 2, "needs_reply": False},
    {"text": "obsessed with this", "category": "praise", "sentiment": 2,
     "needs_reply": False},
    {"text": "Good coffee. Shipping was quick.", "category": "praise", "sentiment": 1,
     "needs_reply": False, "hard": "positive but flat — a 1, not a 2"},
    {"text": "Muy buen café, gracias.", "category": "praise", "sentiment": 2,
     "needs_reply": False, "hard": "Spanish praise"},
    {"text": "Respect for publishing the supplier audit in full. Almost nobody does.",
     "category": "praise", "sentiment": 2, "needs_reply": False},
    {"text": "the decaf is better than most regular coffee I've tried",
     "category": "praise", "sentiment": 2, "needs_reply": False},

    # --- spam ------------------------------------------------------------
    {"text": "Make $5000/week from home! Click my bio 💰💰", "category": "spam",
     "sentiment": 0, "needs_reply": False},
    {"text": "FOLLOW ME FOR FREE GIVEAWAYS 🎁🎁🎁", "category": "spam", "sentiment": 0,
     "needs_reply": False},
    {"text": "Best crypto signals, 300% returns guaranteed, DM now",
     "category": "spam", "sentiment": 0, "needs_reply": False},
    {"text": "check out my page for cheap designer bags", "category": "spam",
     "sentiment": 0, "needs_reply": False},
    {"text": "Love your page! I can grow you to 50k followers, link in bio 🚀",
     "category": "spam", "sentiment": 1, "needs_reply": False,
     "hard": "opens as praise, is a solicitation; needs_reply must still be false"},

    # --- other -----------------------------------------------------------
    {"text": "🔥🔥🔥", "category": "praise", "sentiment": 2, "needs_reply": False,
     "hard": "emoji-only, but unambiguously approving — praise, not other"},
    {"text": "😍", "category": "praise", "sentiment": 2, "needs_reply": False,
     "hard": "single emoji expressing approval"},
    {"text": "👀", "category": "other", "sentiment": 0, "needs_reply": False,
     "hard": "emoji-only with no clear valence — this one is genuinely a 0"},
    {"text": "commenting so I can find this later", "category": "other", "sentiment": 0,
     "needs_reply": False},
    {"text": "tagging @priya_makes you need to see this", "category": "other",
     "sentiment": 1, "needs_reply": False},
    {"text": "lol", "category": "other", "sentiment": 0, "needs_reply": False},
    {"text": "第一次买，包装很好看。", "category": "praise", "sentiment": 1,
     "needs_reply": False,
     "hard": "Chinese: 'first time buying, the packaging is lovely' — praise, not other"},
    {"text": "saving this one", "category": "other", "sentiment": 0, "needs_reply": False},
    {"text": "is this the same as the one from last year", "category": "question",
     "sentiment": 0, "needs_reply": True,
     "hard": "no question mark, lowercase — still a question"},
    {"text": "second", "category": "other", "sentiment": 0, "needs_reply": False,
     "hard": "meaningless engagement bait; not spam, because nothing is being sold"},
]
