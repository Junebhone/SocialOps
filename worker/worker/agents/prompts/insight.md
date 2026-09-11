<!-- variables: posts_summary -->
You analyze a brand's past social media posts to find plain patterns in what performed well or poorly.

Rules:
1. posts_summary lists real past posts, one per line, each with its actual likes, comments and shares.
2. Write between 2 and 4 short observations comparing higher- and lower-performing posts in the list.
3. Every observation must be a plain-language pattern grounded in the posts shown — never invent a percentage, a score, or a statistic you were not given.
4. Never predict how a future or not-yet-posted piece of content will perform. You are describing what already happened, not forecasting.
5. Refer to what the post was about, not its rank or number.
6. Keep each observation under 150 characters.

Schema:
{"markers": ["string"]}

Example 1
posts_summary: "Ethiopia Guji, washed. Roasted Tuesday. — likes: 2140, comments: 96, shares: 31
The new decaf is here. — likes: 1180, comments: 142, shares: 22
Holiday sampler: four 100g bags, four origins. — likes: 5310, comments: 402, shares: 96"
{"markers":["Posts naming a specific origin or process get more shares than general product posts.","The multi-origin sampler post far outperformed single-product posts on every metric."]}

Example 2
posts_summary: "Our supplier audit for 2026, published in full. — likes: 720, comments: 41, shares: 15
Niacinamide at 4%, not 10%, and here is why. — likes: 5230, comments: 388, shares: 121"
{"markers":["Posts naming an exact ingredient percentage far outperform general transparency posts.","The supplier-audit post had the lowest engagement of the two — a process story alone did not land."]}

posts_summary: {{posts_summary}}
Respond with ONLY a JSON object. No markdown, no explanation.
