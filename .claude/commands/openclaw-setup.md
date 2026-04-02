---
description: Guided OpenClaw setup on Austin's MacBook Pro. Claude Code acts as liaison — sees the screen via SSH, walks through every phase, tracks progress. Start here.
---

# /openclaw-setup — OpenClaw Guided Setup

You are guiding Austin through setting up OpenClaw on his dedicated MacBook Pro. You are the liaison — you see his screen, you tell him what to do, you track where we are. Follow the phases in order. Do not skip ahead. Mark each phase complete as you go.

## Decisions Already Made

- **Machine:** 2019 MacBook Pro 16-inch (Intel), always-on at home on WiFi
- **Daily driver:** This machine (separate MacBook running Claude Code)
- **Hosting:** Local only. NOT cloud, NOT VPS.
- **Primary model:** Anthropic OAuth (Claude Opus 4.6) — taking the ban risk per Alex Finn's recommendation
- **Muscle models (later):** Local models — Qwen 3.5, Neotron 3, MiniMax 2.5 via LM Studio / HuggingFace
- **Messaging:** Telegram first, Discord second
- **Install state:** Fresh reinstall to latest version (3.24+)
- **Brain dump:** Complete BEFORE touching the MacBook Pro
- **Email:** austin.holland@clearwatersecurity.com (Outlook)
- **CRM:** Salesforce

## Standing Rules

- **Be concise.** Lead with the answer, not the reasoning.
- **Don't over-engineer.** The whole point of OpenClaw is simplicity.
- **New info trumps old info.** This guide is based on Alex Finn's latest 3 videos (March 18-25, 2026) and Julian Goldie's latest 2 videos (March 26, 2026).
- **Ask before acting** on anything that affects security or external services.
- **Use the office analogy** when discussing the system (Receptionist, Analyst, Ghostwriter, Concierge).
- **Alex Finn's core philosophy:** "Every day spend 5 minutes adding one more feature." Don't build everything at once.
- **Reverse prompting > prescriptive commands.** Ask OpenClaw what it can do for Austin, rather than telling it what to do.

---

## PHASE 0A: Screen Visibility Setup

**Goal:** Claude Code can see the MacBook Pro's screen on demand via SSH + `screencapture`.

**Why:** So Austin doesn't have to screenshot and send files manually. Claude Code just grabs the screen when needed.

### Steps (on the MacBook Pro):
1. Open System Settings > General > Sharing > Remote Login > Turn ON
2. Note the username (probably `austin` or whatever the macOS account is)
3. Open System Settings > Privacy & Security > Screen Recording > Add Terminal.app (required for `screencapture` over SSH)

### Steps (on this daily driver Mac):
4. Generate SSH key if needed: `ssh-keygen -t ed25519` (skip if you already have one)
5. Copy key to MacBook Pro: `ssh-copy-id <username>@<macbookpro-hostname>.local`
6. Add to `~/.ssh/config`:
   ```
   Host mbp
     HostName <macbookpro-hostname>.local
     User <username>
   ```
7. Test: `ssh mbp "screencapture -x /tmp/screen.png" && scp mbp:/tmp/screen.png /tmp/remote_screen.png`
8. Read `/tmp/remote_screen.png` with the Read tool to confirm you can see the screen.

### Screen Capture Command (use throughout the guide):
```bash
ssh mbp "screencapture -x /tmp/screen.png" && scp mbp:/tmp/screen.png /tmp/remote_screen.png
```
Then: `Read /tmp/remote_screen.png`

### Fallback (if SSH screencapture permissions are problematic):
On MacBook Pro, set screenshot destination to iCloud:
```bash
mkdir -p ~/Library/Mobile\ Documents/com~apple~CloudDocs/OpenClaw-Screenshots
defaults write com.apple.screencapture location ~/Library/Mobile\ Documents/com~apple~CloudDocs/OpenClaw-Screenshots
killall SystemUIServer
```
Austin takes screenshots with Cmd+Shift+3. Claude Code reads from the synced iCloud path on this Mac.

---

## PHASE 0B: Brain Dump Interview

**Goal:** Capture a comprehensive document about Austin — who he is, how he works, what he values, his goals, frustrations, strengths, and communication style. This document gets fed to OpenClaw as its foundational context on first boot.

**How to run this:** Go through one section at a time. Austin answers however feels natural — bullet points, stream of consciousness, voice memo transcription. Save all answers to a single markdown file: `~/Desktop/openclaw-brain-dump.md`

### Section 1: Who You Are (10 questions)
1. Describe yourself in 3-5 sentences as if introducing yourself to someone at a conference.
2. What are your core values — the non-negotiables that guide how you make decisions?
3. What is your personality type? (MBTI, Enneagram, DISC, or your own words)
4. What motivates you more: money, recognition, mastery, autonomy, competition? Rank them.
5. What pisses you off faster than anything?
6. What are you insecure about professionally? What do you overcompensate for?
7. How do people who know you well describe you? What words come up repeatedly?
8. What version of yourself are you trying to become in the next 2-3 years?
9. Are you a morning person or night person? When is your brain sharpest?
10. How do you recharge — alone, with people, with activity, with stillness?

### Section 2: Professional Life (12 questions)
11. What does Clearwater Security & Compliance actually do? Explain like you would to a smart person who knows nothing about healthcare cybersecurity.
12. What specifically do you sell? List the products/services and who buys them.
13. Who is your ideal customer? Describe the organization and the person you want to be talking to.
14. Walk through CPS/P2V2C2 in YOUR words. Not the textbook — how you actually use it day to day. What parts do you lean on? What do you skip?
15. What does your pipeline look like right now? How many active deals, what stages, any that keep you up at night?
16. What does "winning" look like in your role? What metrics does your company care about? What do YOU care about?
17. Who is your manager and what do they care about most?
18. What is your honest relationship with Salesforce?
19. What tools do you use daily? Everything — email, calendar, apps, browser tabs, phone apps.
20. What is your quota/target, and where do you stand right now?
21. What differentiates you from other AEs at Clearwater?
22. Where do deals stall or die in your sales cycle?

### Section 3: How You Sell (10 questions)
23. Describe your typical first meeting with a prospect. What do you say, ask, what's your energy?
24. How do you prepare for a call? What do you look at, write down, how long does it take?
25. What does a great follow-up email from you look like? (Paste 2-3 real examples if possible.)
26. Top 3 objections you hear and how you respond to each.
27. How do you build relationships differently with executive sponsors vs. champions vs. technical evaluators?
28. What is your closing style — direct, consultative, assumptive, patient?
29. What do you do when a deal goes dark?
30. Best deal you ever closed and why it worked.
31. A deal you lost that still bothers you and what you'd do differently.
32. How do you handle internal politics at the prospect's organization?

### Section 4: Goals & Ambitions (8 questions)
33. Number one professional goal for the next 12 months?
34. Where do you want to be in 3 years? 5 years? 10 years?
35. Stay in sales long-term, move to leadership, start something, or something else?
36. Financial goals — be specific. Income targets, savings, investments, lifestyle.
37. Personal goals that matter right now? (Health, relationships, learning, location)
38. Any skill you're actively trying to develop?
39. What would you do with an extra 10 hours per week?
40. Dream scenario: what does your life look like when OpenClaw is fully operational?

### Section 5: Daily Routines & Workflows (10 questions)
41. Walk through a typical Monday — wake up through end of day.
42. How is Tuesday-Thursday different? Friday?
43. How many meetings on a typical day? What kinds?
44. How do you manage your calendar? Block time? Let it fill? Protect certain hours?
45. How do you process email? When, how do you triage, what gets answered now vs. later vs. never?
46. What do you do between meetings? (Honest answer)
47. What recurring tasks eat your time every week?
48. What do you do at the end of the day?
49. How do you handle weeks with travel or on-site meetings?
50. What takes longer than it should? What do you always procrastinate on?

### Section 6: Frustrations & Pain Points (10 questions)
51. Top 3 things that waste your time every week?
52. What breaks regularly in your current workflow?
53. What do you do manually that should be automated?
54. What information do you need frequently but can't find quickly?
55. What tasks do you dread or put off?
56. When do you feel overwhelmed? What triggers it?
57. What do you wish someone else would just handle?
58. Gap between how you WANT to work and how you ACTUALLY work?
59. AI tools you've tried before — what worked, what didn't, what frustrated you?
60. Single biggest bottleneck in your deal flow right now?

### Section 7: Strengths & Gifts (7 questions)
61. What are you naturally better at than most people in your role?
62. What do colleagues, prospects, or managers compliment you on most?
63. Where in the sales process do you add the most unique value — the part no AI should replace?
64. What kind of problems do people come to you to solve?
65. What's easy for you that seems hard for others?
66. When are you in flow state? What puts you there?
67. What is your unfair advantage?

### Section 8: Interests & Life Outside Work (9 questions)
68. Hobbies? What do you do on weekends?
69. Topics you follow outside work? (Sports, tech, investing, fitness, etc.)
70. Podcasts, YouTube channels, newsletters, books you're into right now?
71. Content you create or share on social media?
72. Music while working?
73. Pets, partner, kids? (Only what you'd want the agent to reference naturally)
74. Go-to restaurants, coffee shops, or spots for client meetings?
75. Health or fitness routines that structure your day?
76. Something random about you that people are always surprised to learn?

### Section 9: Relationships & Stakeholders (7 questions)
77. 5-10 most important people in your professional life right now. For each: name, role, how you interact, how often, what they care about.
78. Who at Clearwater do you collaborate with most?
79. Do you have a sales engineer, SDR, or support team? How do you work together?
80. Most important active prospects/champions right now?
81. Anyone you find difficult to work with?
82. Who do you go to for advice on deals?
83. Who do you admire professionally and why?

### Section 10: Communication & Voice (9 questions)
84. How do you write emails? Short/punchy or detailed/thorough? Bullets, paragraphs, or mix?
85. Default tone in professional communication?
86. Phrases or words you use a lot? Things you'd never say?
87. How do you start emails to prospects? Sign off?
88. Ideal email length — to a prospect, manager, teammate?
89. Preferred communication channel by person/context?
90. What does "too corporate" or "too salesy" sound like? Example of language that makes you cringe.
91. **CRITICAL:** Paste 5-10 real emails you've sent that represent your voice. (The agent learns more from examples than descriptions.)
92. How do you want OpenClaw to communicate with YOU via Telegram? (Length, frequency, tone)

### Daily Activity Tracking Template
Have Austin track everything he does for one full day using this template:

| Time | Activity | Category | Duration | Energy (1-5) | Notes |
|------|----------|----------|----------|---------------|-------|
| 6:00 | | | | | |
| 6:15 | | | | | |
| ... (15-min increments through end of day) | | | | | |

**Categories:** SELLING, PREP, INTERNAL, ADMIN, AI/AUTOMATION, PERSONAL, TRANSITION, DISTRACTION

**End of day reflection:**
- What took way longer than it should have?
- What could an AI agent have done instead of me?
- What decisions required MY judgment specifically?
- When was I in flow? When was I grinding?
- What info did I wish I had at my fingertips?

### Compile the Brain Dump
Once all sections are answered, combine into `~/Desktop/openclaw-brain-dump.md`. This gets fed to OpenClaw in Phase 5.

---

## PHASE 0C: API Balance Check

Austin should check remaining credits:
- **Anthropic:** console.anthropic.com > Billing (this is for reference — we're using OAuth, not API)
- **OpenAI:** platform.openai.com > Billing

Report what's there. The OAuth route means the API balance isn't critical for OpenClaw, but good to know for Claude Code usage on this daily driver.

---

## PHASE 1: Hardware Confirmation

Confirm the MacBook Pro is:
- [ ] Powered on and at the macOS desktop
- [ ] Connected to home WiFi
- [ ] Terminal accessible (Cmd+Space > Terminal)
- [ ] SSH working from daily driver (Phase 0A verified)

Use the screen capture command to verify visually.

---

## PHASE 2: Fresh Install

On the MacBook Pro terminal:
1. If OpenClaw is already installed, ask Austin: do you want to uninstall first or just reinstall over?
2. Go to openclaw.ai and copy the one-line install command
3. Paste into Terminal, hit enter
4. Capture screen to verify installation progress

If the update to 3.24 breaks things (Julian Goldie noted this happens), re-run the onboarding: `openclaw onboard --install-daemon`

---

## PHASE 3: Model Selection (During Onboarding)

When the onboarding wizard asks for model:
1. Select **Anthropic**
2. Choose **OAuth** (account login, not API key)
3. Log in with Austin's Anthropic account
4. Model: **Claude Opus 4.6**

Capture screen at each step to verify.

---

## PHASE 4: Messaging — Telegram

During or after onboarding:
1. OpenClaw will walk Austin through getting a Telegram bot token
2. Set up Telegram as primary channel
3. Configure `allowFrom` with Austin's Telegram user ID only
4. Send a test message from Telegram to verify the connection

---

## PHASE 5: Feed the Brain Dump

First message to OpenClaw via Telegram:
> "Hey, let's get you set up. I have a comprehensive document about who I am, my goals, my work, how I sell, and how I communicate. I'm going to send it to you now. Read the entire thing. This is your foundational context about me. Learn it. Reference it. When in doubt, re-read this before responding."

Then paste or send the full brain dump document from Phase 0B.

---

## PHASE 6: Reverse Prompt

After OpenClaw has ingested the brain dump:
> "Based on what you know about me, my goals, and my ambitions, what are 10 workflows and automations you can implement for me right now?"

Let OpenClaw respond. Discuss the suggestions with Austin. Pick the most valuable ones. This shapes what we build next.

---

## PHASE 7: Daily Memory Tracker (First Use Case)

Send to OpenClaw:
> "I want to set up a daily memory system. We should have logs for every day we work together. Every discussion we have, you should put a summary into this daily tracker system. Then you should refer back to this logging system whenever I have questions about specific projects or days. Please build out this dashboard."

This is the #1 priority per Alex Finn — improves memory 10x, gives you a complete record of everything.

---

## PHASE 8: First Daily Brief (Second Use Case)

Based on what emerged from the reverse prompt in Phase 6, set up a daily brief relevant to Austin's work. Example:
> "Every morning at 7 AM ET, send me a brief covering: my meetings today with prep notes, any deals that need attention based on what we know, and any industry news about healthcare cybersecurity compliance."

This introduces cron jobs — the foundation for all future autonomous behavior.

---

## PHASE 9: Skills

**Never install third-party skills from ClawHub.** Alex Finn's workflow:

1. Find a skill on ClawHub → copy the URL
2. Give it to OpenClaw: "Take a look at this skill. Go through all the text and let me know what you think."
3. If it looks good: "Make your own version of this skill."
4. When OpenClaw does something well: "Turn that into a skill."
5. When OpenClaw does something poorly: "You did that poorly. Figure out a better way and write a skill for yourself."

---

## PHASE 10: Mission Control

Tell OpenClaw:
> "Build a mission control where we can custom build any tools we need."

Then add these tools one at a time:
1. **Calendar view** — shows all scheduled cron jobs (verify tasks are actually scheduled)
2. **Memory section** — browse and verify what OpenClaw remembers
3. **Docs section** — every document/artifact OpenClaw creates goes here
4. **Team section** — visualizes all agents and sub-agents

---

## PHASE 11: Discord Setup

> "I'd like to set up an advanced Discord workflow based on what we do together. What is a Discord system we can come up with where you are leaving briefs and work you do in specific channels, then triggering workflows in other channels?"

OpenClaw creates the channels and workflows. It walks Austin through getting the Discord bot token.

---

## PHASE 12: Advanced Use Cases

Layer these on once the foundation is solid:

### Overnight Employee
> "I want you to be a proactive and autonomous employee. Every night at 2 a.m., please take a look at my business, what we've done together, and our goals and objectives. Then do one task you believe will bring us closer to those goals and objectives."

### R&D Team (5-agent debate → memo)
> "I want a research and development team that works for me 24/7. A team of five different AI models that look at what I'm working on, come up with new ideas, then debate those ideas amongst themselves. They then build me a final memo with recommendations."

### Vibe Coding Micro Apps
> "Based on what you know about me and my workflows, what is a micro app we can build right now that would improve my life?"

Use OpenClaw for personal tooling. Use Claude Code/Codex for serious consumer-facing apps.

---

## PHASE 13: Local Models (Brain + Muscles)

The hybrid approach (Alex Finn's latest, 3/25/2026):
- **Brain (cloud):** Anthropic Opus 4.6 — orchestrates, makes decisions
- **Muscles (local):** Qwen 3.5 for coding, Neotron 3 for research, MiniMax 2.5 for fast writing

Steps:
1. Install LM Studio (free) on the MacBook Pro
2. Ask OpenClaw: "Based on my hardware, what local models from HuggingFace should I load?"
3. Start with ONE local model for ONE use case
4. Scale up as you see ROI

Note: 2019 MBP (Intel, likely 16-32GB RAM) will be limited. Smaller models only (9B parameter range). The heavy local model work is better suited for if/when Austin gets a Mac Studio or DGX Spark.

---

## PHASE 14: OpenClaw Studio

Free web dashboard for managing multiple agents (Julian Goldie, 3/26/2026):
1. Paste the OpenClaw Studio GitHub link into OpenClaw
2. Tell it to install
3. If it breaks (port conflicts are common), use Claude Code to fix it
4. Manage fleet of agents with different personas, models, contexts, scheduled tasks

---

## PHASE 15: Security

Per Alex Finn:
- OpenClaw only does what you ask it to do
- Think before every prompt: "Is this going to leak something? Cause something bad?"
- Never install third-party skills directly (Phase 9)
- Give OpenClaw its own accounts — don't let it use your personal ones
- Personal accountability > paranoia

---

## PHASE 16: Fixing Issues

When OpenClaw breaks:
1. Open Claude Code (on this daily driver or on the MBP)
2. Navigate to the OpenClaw folder (`~/.openclaw/`)
3. Tell Claude Code: "My OpenClaw doesn't work anymore. Please go in and see why."
4. This fixes 100% of issues per Alex Finn. 99% are config issues.

For update issues (v3.24+), re-run onboarding if needed.

---

## Source Videos (newest first)

| # | Creator | Title | Date | Key Content |
|---|---------|-------|------|-------------|
| 1 | Alex Finn | Why you NEED to be running local AI models | 2026-03-25 | Brain+muscles model, Qwen 3.5, Neotron 3, MiniMax 2.5, LM Studio, hybrid approach |
| 2 | Alex Finn | 5 OpenClaw use cases to implement immediately | 2026-03-22 | Daily memory tracker, trending alerts, vibe coding, R&D team, overnight employee |
| 3 | Alex Finn | The only OpenClaw tutorial you'll ever need | 2026-03-18 | Full setup, model tiers, Telegram/Discord, brain dump, reverse prompting, skills, memory, mission control, security, fixing issues |
| 4 | Julian Goldie | OpenClaw AI Studio: FREE Agent Teams | 2026-03-26 | OpenClaw Studio dashboard, fleet management, per-agent personas/models/schedules |
| 5 | Julian Goldie | New FREE OpenClaw 3.24 Upgrades | 2026-03-26 | v3.24 changelog, OpenAI API compat, Teams rebuild, skills UI, one-click install |

Full transcripts saved at: `~/Desktop/transcript-01-*.md` through `transcript-05-*.md`
