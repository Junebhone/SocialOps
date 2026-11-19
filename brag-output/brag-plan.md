# SocialOps launch video: plan

**What it is:** a command center where AI agents triage every comment on a small brand's posts and draft the replies; a person approves each one.
**For:** a marketing manager running three to five brands, buried after a post takes off.
**Sets it apart:** nothing posts without a human; it runs on AWS and rolls itself back when a deploy is bad.
**Hook:** comments raining onto a dark screen, a counter racing to 2,000.
**Share caption:** One viral post, two thousand comments. SocialOps triages every one and drafts the reply; you just approve.
**Tone:** `polished`, with a quick hook. Square 1080×1080, 30 fps, 28 s (fills the 30-second title-slide slot in the deck).
**Audio:** none. The deck plays this muted and autoplaying on slide 1, so a soundtrack would never be heard.
**Identity:** the app's own palette and fonts: cream #faf5ee, ink #2c2723, terracotta #b0532c, dark #221e1a; Newsreader, Public Sans, Geist Mono.
**Data:** comment text from the synthetic `data/comments_small.json` (fake brand "Ridgeline Roasters"). Author handles replaced with generic ones. The draft reply is illustrative UI text.

| # | Time | Scene | On screen |
|---|---|---|---|
| 1 | 0.0–3.0 | Hook (dark) | Comment cards drop in fast, piling up; counter 0 → 2,000. "One viral post." |
| 2 | 3.0–7.0 | The problem (dark) | Pile keeps growing; line: "Two thousand comments. One of you." |
| 3 | 7.0–12.5 | Triage (cream) | Five real comments in a list; each gets a category badge and urgency; spam rows strike out and fade. Title "Agents triage every comment." |
| 4 | 12.5–18.5 | Approve (cream) | Inbox row from the real UI: comment, draft reply types in, cursor clicks Approve, toast "Reply approved". Title "You approve every reply." |
| 5 | 18.5–24.0 | AWS (dark) | Four chips land: ECS Fargate, Amazon Bedrock, CloudWatch alarm, Automatic rollback; then a deploy line: build → deploy → health check ✕ → rolled back ✓. Title "Running on AWS." |
| 6 | 24.0–28.0 | Outro (cream) | "SocialOps" wordmark, "Every comment answered. Nothing posts without you.", app.socialops.website |

Transitions: dip through the background colour (old out, then new in), never a crossfade of two busy layouts.
