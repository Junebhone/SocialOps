SELECT 'agent_runs', count(*) FROM agent_runs
UNION ALL SELECT 'analytics_summaries', count(*) FROM analytics_summaries
UNION ALL SELECT 'assets', count(*) FROM assets
UNION ALL SELECT 'brands', count(*) FROM brands
UNION ALL SELECT 'comments', count(*) FROM comments
UNION ALL SELECT 'content_drafts', count(*) FROM content_drafts
UNION ALL SELECT 'content_ideas', count(*) FROM content_ideas
UNION ALL SELECT 'failed_jobs', count(*) FROM failed_jobs
UNION ALL SELECT 'insights', count(*) FROM insights
UNION ALL SELECT 'outbox', count(*) FROM outbox
UNION ALL SELECT 'platform_accounts', count(*) FROM platform_accounts
UNION ALL SELECT 'posts', count(*) FROM posts
UNION ALL SELECT 'reply_drafts', count(*) FROM reply_drafts
ORDER BY 1;
