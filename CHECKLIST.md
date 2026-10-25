# Submission checklist

Deadline: **Oct 30, 2026, 10:30pm IST (12:00pm US Central)**. Aim to submit by 6pm IST.

## Hard requirements (missing any one disqualifies the submission)

- [x] Uses **Nebius Token Factory** (OpenAI-compatible API): `backend/app/llm.py`
- [x] Uses an **NVIDIA Nemotron** open model (Nano, Super and Ultra routed per task): `backend/app/router.py`
- [ ] Verified live: `/api/status` shows real Nemotron model IDs resolved from `/v1/models`
- [x] **Public GitHub repo**: https://github.com/Yashika2211/Nebius-ai-hack
- [x] **MIT license** detected by GitHub (shown at the top of the repo page)
- [x] README: setup steps
- [x] README: how to run
- [x] README: architecture diagram (Mermaid)
- [x] README: "How we used Nemotron + Token Factory"
- [x] README: "Other Nebius services used"
- [ ] README: "Feedback on Token Factory / Nemotron" (expand with real usage notes)
- [ ] **Hosted demo URL** works in an incognito window (backend on Render, frontend on Vercel)
- [ ] Demo URL added to the README and Devpost
- [ ] **Demo video ≤ 3:00**, uploaded to YouTube as **Public**
- [ ] Video link added to the README and Devpost
- [ ] Devpost track selected: **Best Apps and Agents**

## Quality bar

- [ ] Golden path works end to end on the deployed URL: demo company → find opportunities → check eligibility → draft
- [ ] Demo cache exported (`python -m app.seed export`) and committed, so the deployed demo works if a live call fails
- [ ] Eval run on 10–20 real labeled RFPs; results table pasted into the README
- [ ] Routing-savings number in the README, SUBMISSION.md and the video matches the measured number
- [ ] Screenshots in the README (landing, dashboard with trace, eligibility, draft)
- [x] CI green (backend tests + frontend build)
- [ ] No secrets in the repo (`git log -p | grep -i "api_key="` shows only empty examples)

## Devpost form

- [ ] Paste SUBMISSION.md sections into the matching Devpost fields
- [ ] "Built with" tags: nvidia-nemotron, nebius-token-factory, tavily, fastapi, next.js, tailwind, python, typescript, sqlite
- [ ] Team members added
- [ ] Opted into extra prizes: Best Use of Tavily, Most Valuable Feedback
