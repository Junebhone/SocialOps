"""The two seed brands.

Kept in one module because three things read them: `seed.py` writes them to the
database, `generate_comments.py` writes comments that sound like their
customers, and the eval set quotes their handles. Two brands rather than one is
deliberate (D17) — it is what makes the brand selector and per-brand cost real
rather than decorative.

`rules` matches the D16 shape exactly: one column, three consumers. The media
agent checks `prohibited_content` and `required_elements`, the content agent
respects `max_hashtags` and `tone`, the response agent uses `tone.avoid_words`.
"""

from typing import Any

BRANDS: list[dict[str, Any]] = [
    {
        "name": "Ridgeline Roasters",
        "voice_guidelines": (
            "You are the voice of a 9-person coffee roastery in Bellingham. Warm, "
            "specific, and unhurried. Talk about coffee the way a barista does across "
            "the counter: name the farm, the process, the roast date. Never oversell. "
            "If someone is disappointed, say what went wrong and what you will do, in "
            "that order, without corporate hedging. Short sentences. No exclamation "
            "marks beyond one per reply. Never claim health benefits."
        ),
        "rules": {
            "prohibited_content": [
                "competitor logos",
                "alcohol",
                "health or medical claims",
                "unaccompanied minors",
            ],
            "required_elements": ["product visible", "logo visible"],
            "tone": {
                "avoid_words": ["cheap", "guys", "world-class", "game-changer"],
                "prefer_words": ["small-batch", "crafted", "single-origin", "roasted to order"],
            },
            "max_hashtags": 5,
        },
        "accounts": [
            {"platform": "instagram", "handle": "@ridgelineroasters"},
            {"platform": "x", "handle": "@ridgelinecoffee"},
            {"platform": "linkedin", "handle": "ridgeline-roasters"},
        ],
        # Post templates. `metrics_json` scales with how well each one did.
        "posts": [
            ("Ethiopia Guji, washed. Roasted Tuesday, shipping Wednesday.", 2140, 96, 31),
            ("The new decaf is here. Sugarcane process, no solvents.", 1180, 142, 22),
            ("Behind the roaster with Nia, who has pulled every sample this month.", 3310, 210, 64),
            ("Cold brew concentrate is back in stock. One bottle makes eight cups.", 890, 54, 12),
            ("Our Colombia Huila just hit 88 on the cupping table.", 1620, 71, 28),
            ("Free pour-over class, Saturday 10am, at the Fairhaven shop.", 2480, 188, 47),
            ("Subscription boxes ship Monday. Change your grind before Sunday night.", 640, 39, 9),
            ("We switched to compostable valve bags. Same beans, less landfill.", 4020, 331, 118),
            ("Roast profile notes for the Kenya AB, if you like the technical side.", 770, 63, 19),
            ("Holiday sampler: four 100g bags, four origins, one box.", 5310, 402, 96),
        ],
    },
    {
        "name": "Fieldnote Skin",
        "voice_guidelines": (
            "You are the voice of a direct-to-consumer skincare brand with four "
            "products and no filler. Calm, factual, and plain. Name the actual "
            "ingredient and the actual percentage. Never promise a result or a "
            "timeline. If someone reports irritation, tell them to stop using it and "
            "offer a refund before anything else — never diagnose, never suggest they "
            "used it wrong. Avoid beauty-industry superlatives entirely."
        ),
        "rules": {
            "prohibited_content": [
                "competitor logos",
                "before-and-after claims",
                "medical or dermatological claims",
                "unaccompanied minors",
            ],
            "required_elements": ["product visible", "ingredient list legible"],
            "tone": {
                "avoid_words": ["miracle", "flawless", "anti-aging", "clinically proven", "guys"],
                "prefer_words": ["formulated", "fragrance-free", "barrier-supporting", "tested"],
            },
            "max_hashtags": 4,
        },
        "accounts": [
            {"platform": "instagram", "handle": "@fieldnoteskin"},
            {"platform": "x", "handle": "@fieldnoteskin"},
            {"platform": "linkedin", "handle": "fieldnote-skin"},
        ],
        "posts": [
            ("The barrier serum is back. 5% panthenol, fragrance-free.", 3120, 210, 44),
            ("What is actually in the cleanser, line by line.", 1870, 96, 33),
            ("We reformulated the moisturiser to drop the drying alcohol.", 2640, 178, 51),
            ("Patch testing: how we do it, and how you should.", 1290, 84, 27),
            ("Refill pouches ship this month. 62% less plastic per unit.", 4410, 302, 88),
            ("Our supplier audit for 2026, published in full.", 720, 41, 15),
            ("Niacinamide at 4%, not 10%, and here is why.", 5230, 388, 121),
            ("The SPF is still in testing. We are not shipping it early.", 1960, 130, 39),
            ("Sample sizes are now free with any order over 40 dollars.", 2880, 195, 46),
            ("Answering the twelve questions we get most about the serum.", 1140, 72, 24),
        ],
    },
]
