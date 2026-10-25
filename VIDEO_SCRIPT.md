# BidScout demo video script (target 2:45, hard limit 3:00)

**Setup before recording:** backend deployed and warm (open `/health` once), browser at 110% zoom, demo
company pre-seeded, one opportunity already discovered so you can cut to it if live search is slow.
Record the screen at 1080p. Record the voiceover separately if possible.

| Time | Shot | Voiceover |
|---|---|---|
| **0:00–0:15** | Black screen, white text: *"$180B in small-business contracts each year."* Cut to SAM.gov search results: a wall of 10,000 listings. | "Every year the US government sets aside billions in contracts for small businesses. Most of the businesses that qualify never bid, because finding the right one and writing a compliant response takes days." |
| **0:15–0:25** | BidScout landing page. Cursor hovers over the four steps. | "BidScout is an AI agent that does that work in minutes. It runs on NVIDIA Nemotron through Nebius Token Factory." |
| **0:25–0:50** | Click **Try the demo company**. Profile card on the left. Hover a NAICS code to show the citation popover with the source sentence. Expand "unsupported facts dropped". | "Meet Ridgeline, a 42-person woman-owned janitorial company in San Antonio. BidScout crawled their site and built this profile. Every fact links to the sentence it came from. Anything it couldn't verify, it dropped." |
| **0:50–1:20** | Click **Find opportunities**. The trace panel fills live: Nano triage rows (green), Tavily search rows, Ultra fit-scoring rows (purple). Ranked cards appear. | "Now it searches SAM.gov and state and city procurement portals. Watch the trace on the right. Nemotron Nano triages dozens of results cheaply, low-confidence calls escalate to a bigger model, and Nemotron Ultra does the hard judgment: how well this company actually fits." |
| **1:20–1:35** | Zoom on the trace footer: **"Routing saved NN% vs. Ultra-only."** | "Every call is measured. Routing each task to the right tier saved NN% compared with running everything on Ultra, and our eval shows accuracy held." |
| **1:35–1:55** | Open the top opportunity. Fit-score tab: factor bars, hover a citation into the RFP text. | "Here's the top match. The score isn't a black box. Six factors, fixed weights, and every reason cites the RFP or the profile." |
| **1:55–2:15** | Click **Check eligibility**. The verdict banner appears. Scroll to show one *unknown* (bonding) with its "Next step". If available, show a second opportunity with a red **Dealbreaker: 8(a) set-aside**. | "Before you spend a week on a proposal: can you even bid? BidScout checks set-asides, insurance, bonding and deadlines, and flags dealbreakers with the exact RFP language." |
| **2:15–2:35** | Click **Draft response**. Text streams in. Cut to the finished compliance matrix (gaps highlighted amber), then the draft with citation chips. Hover one. | "Then it drafts. A compliance matrix maps every 'shall' in the RFP to a response section and flags gaps. The first draft cites a source for every sentence, and Ultra reviews it before you see it." |
| **2:35–2:45** | Runs page: savings stat, routing table. End card: BidScout logo, GitHub URL, "Nemotron × Nebius Token Factory × Tavily". | "Days of specialist work, done in minutes, for the businesses these contracts were meant for. This is BidScout." |

**Recording tips**
- Speak at about 150 words per minute. The script is about 400 words.
- Replace **NN%** with the measured number from `/runs` or the eval table.
- If live discovery takes over 30s, cut the wait in editing and keep the trace visible.
- Upload to YouTube as **Public**, title: *BidScout: AI agent that wins government contracts for small businesses (Nemotron + Nebius Token Factory)*.
