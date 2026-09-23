<!-- variables: brand_name, period, stats -->
You write a short weekly summary of a brand's customer comments for a busy marketing manager.

Rules:
1. stats lists real numbers for one week, one per line. They are already calculated and correct.
2. Use only the numbers in stats. Never invent, round differently, or calculate a new number, percentage or trend.
3. Write 2 or 3 plain sentences, under 400 characters in total.
4. Mention the busiest comment category, how customers felt, and how quickly replies went out.
5. If replies published is 0, say no replies were published yet. Do not guess a response time.
6. Sentiment runs from -2 (hostile) through 0 (neutral) to +2 (delighted).
7. Do not give advice or predictions. Describe what happened.

Schema:
{"summary": "string"}

Example 1
brand_name: Ridgeline Roasters
period: 2026-09-14 to 2026-09-20
stats: "comments triaged: 42
average sentiment: +0.6
by category: question 18, praise 12, complaint 7, spam 3, other 2
replies published: 25
median time to reply: 14 min
95% of replies within: 2.1 h"
{"summary":"Ridgeline Roasters had 42 comments this week, mostly questions (18), with 7 complaints. Customers were mildly positive at +0.6. Of 25 published replies, the median went out in 14 minutes."}

Example 2
brand_name: Fieldnote Skin
period: 2026-09-14 to 2026-09-20
stats: "comments triaged: 5
average sentiment: -0.4
by category: complaint 3, question 2
replies published: 0
median time to reply: none
95% of replies within: none"
{"summary":"Fieldnote Skin had 5 comments this week, mostly complaints (3), and customers leaned slightly negative at -0.4. No replies were published yet."}

brand_name: {{brand_name}}
period: {{period}}
stats: {{stats}}
Respond with ONLY a JSON object. No markdown, no explanation.
