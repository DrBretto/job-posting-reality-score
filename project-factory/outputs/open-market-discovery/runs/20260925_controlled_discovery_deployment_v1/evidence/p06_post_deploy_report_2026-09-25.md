# Job Posting Reality Score — daily report 2026-09-25

Run: 2026-09-25  ·  scoring profile v1.2.0
Completeness: 15/15 sources succeeded

## Run health

- **Collection (VERIFIED-QUIET)** — every expected source produced a successful download; changes are listed below.
- **Discovery coverage (PARTIAL)** — 4/4 discovery sources returned results; 14/14 query families covered; hit a result ceiling (more may exist): ai-implementation, automation-integration, backend-cloud, data-extraction, internal-tools, ordinary-software, sector-construction, sector-healthcare, sector-hospitality, sector-insurance, sector-logistics, sector-manufacturing, sector-professional-services, sector-retail; 1 query items queued and resumable; not runnable without a credential: adzuna.
- **Freshness (CHANGED)** — 13 newly observed, 13 edited.
- **Interpretation (DEGRADED)** — 11 source(s) have coverage in question, so their removals are held.

> Collection health describes the sources that were actually queried. It is not a statement about the job market: a complete download of every configured source still covers only those sources, and the discovery coverage line above is the one that says how wide the search itself reached.

Retained credible roles: 35 (12 new, 16 needing a check, 7 already in progress). Policy exclusions: 225. Postings considered: 511.

Below the fit threshold and therefore not listed above: 251. These are retained with full scores in `daily_report.json` and are not a judgment by the research step — ranking is a triage aid, not a verdict.

Candidate policy: projection 1.0.0 built 2026-09-24 — policy sources not reachable from here (expected in production: the sibling repository is not deployed); screening used the committed projection

## Coverage and backlog

- Discovery sources queried: himalayas, jobicy, remoteok, remotive
- Query families: 14/14 covered
- Hit a result ceiling, so more may exist behind it: ai-implementation, automation-integration, backend-cloud, data-extraction, internal-tools, ordinary-software, sector-construction, sector-healthcare, sector-hospitality, sector-insurance, sector-logistics, sector-manufacturing, sector-professional-services, sector-retail
- Resumable backlog: 1 query item(s) — himalayas feed has more pages; position saved and resumable
- **adzuna did not run**: Adzuna requires app_id and app_key on every request; without them the API returns 400. This is the source that provides general, all-industry US breadth, so its absence is a real coverage limit, not a formality.. Required setup: ADZUNA_APP_ID and ADZUNA_APP_KEY
- Request budgets used: himalayas: 5/5, jobicy: 1/1, remoteok: 1/1, remotive: 1/1

## Source notices

- Future (greenhouse:future): source coverage is in question (removals suppressed). silent-subset SUCCESS (segments omitted: ['people team']); removals SUPPRESSED this run [snapshot=3141d78cf2c241479f1322857f38ddc4, event=2026-09-25:greenhouse:future:source-suspect]
- Grafana Labs (greenhouse:grafanalabs): source coverage is in question (removals suppressed). silent-subset SUCCESS (segments omitted: ['developer advocacy', 'gtm enablement', 'people', 'r&d: artificial intelligence (ai)', 'r&d: platform', 'sales operations', 'solutions engineering']); removals SUPPRESSED this run [snapshot=31e0303e5ac94c6a858dca400c945bbf, event=2026-09-25:greenhouse:grafanalabs:source-suspect]
- Icon (greenhouse:iconcareers): source coverage is in question (removals suppressed). silent-subset SUCCESS (segments omitted: ['accounting & finance', 'supply chain management & sourcing']); removals SUPPRESSED this run [snapshot=466fa64065bf4b0d8a76c126caa72034, event=2026-09-25:greenhouse:iconcareers:source-suspect]
- Machinify (greenhouse:machinifyinc): source coverage is in question (removals suppressed). silent-subset SUCCESS (segments omitted: ['analytics', 'client success', 'marketing', 'physicians', 'subrogation']); removals SUPPRESSED this run [snapshot=7e2bee629e3544b7a5445cc45b6a8a85, event=2026-09-25:greenhouse:machinifyinc:source-suspect]
- Mozilla (greenhouse:mozilla): source coverage is in question (removals suppressed). silent-subset SUCCESS (segments omitted: ['ads', 'finance', 'marketing', 'mzla/thunderbird', 'office of ceo']); removals SUPPRESSED this run [snapshot=250ddd8fe44344b3b9c98125f29b81a3, event=2026-09-25:greenhouse:mozilla:source-suspect]
- Snorkel Ai (greenhouse:snorkelai): source coverage is in question (removals suppressed). silent-subset SUCCESS (segments omitted: ['420 - solutions sales']); removals SUPPRESSED this run [snapshot=a4e29f5ff6924249a5e37fe8c6f8a7ea, event=2026-09-25:greenhouse:snorkelai:source-suspect]
- Cadence Solutions (greenhouse:solutions): source coverage is in question (removals suppressed). silent-subset SUCCESS (segments omitted: ['care delivery', 'it', 'partnerships']); removals SUPPRESSED this run [snapshot=6f4c05d19f474ddc88ddecc4590356cc, event=2026-09-25:greenhouse:solutions:source-suspect]
- Bolt New (greenhouse:stackblitz): source coverage is in question (removals suppressed). silent-subset SUCCESS (segments omitted: ['dev ops', 'marketing']); removals SUPPRESSED this run [snapshot=aa5752ef0ac7429994f0246c4c1c00f7, event=2026-09-25:greenhouse:stackblitz:source-suspect]
- Tailscale (greenhouse:tailscale): source coverage is in question (removals suppressed). silent-subset SUCCESS (segments omitted: ['design']); removals SUPPRESSED this run [snapshot=4550df7c1b0b448f8ecf6700c3b9c006, event=2026-09-25:greenhouse:tailscale:source-suspect]
- Warp (greenhouse:warp): source coverage is in question (removals suppressed). silent-subset SUCCESS (segments omitted: ['growth']); removals SUPPRESSED this run [snapshot=b633754a6a33484e80b2e1b17da29db4, event=2026-09-25:greenhouse:warp:source-suspect]
- Legion Intelligence (greenhouse:yurtsai): source coverage is in question (removals suppressed). silent-subset SUCCESS (segments omitted: ['human resources', 'sales']); removals SUPPRESSED this run [snapshot=c03d52095a8f43a3a92536c99843e735, event=2026-09-25:greenhouse:yurtsai:source-suspect]

## New strong candidates

- [Senior Software Engineer - Rails](https://job-boards.greenhouse.io/stackblitz/jobs/4006004009) — Bolt New | Remote | fit MEDIUM 0.54 | priority MEDIUM 0.59 | matches on software-engineering, apis-backend, aws-serverless, llms, typescript-node; remote compatible
- [Senior Software Engineer, Cloud Engineering](https://job-boards.greenhouse.io/mozilla/jobs/8031378) — Mozilla | Remote | fit MEDIUM 0.55 | priority MEDIUM 0.58 | matches on software-engineering, agents, aws-serverless, python; remote compatible
- [Senior Data Engineer - Analytics](https://job-boards.greenhouse.io/machinifyinc/jobs/4418234009) — Machinify | Remote - US | fit MEDIUM 0.50 | priority MEDIUM 0.57 | matches on data-engineering, apis-backend, llms, orchestration, python; remote compatible
- [Senior Software Engineer](https://job-boards.greenhouse.io/mozilla/jobs/8204384) — Mozilla | Remote | fit MEDIUM 0.45 | priority MEDIUM 0.55 | matches on software-engineering, apis-backend, python, typescript-node; remote compatible
- [Senior Software Engineer](https://job-boards.greenhouse.io/mozilla/jobs/8209734) — Mozilla | Remote US | fit MEDIUM 0.45 | priority MEDIUM 0.55 | matches on software-engineering, apis-backend, python, typescript-node; remote compatible
- [Senior Software Engineer, Add-Ons](https://job-boards.greenhouse.io/mozilla/jobs/7524337) — Mozilla | Remote | fit MEDIUM 0.45 | priority MEDIUM 0.55 | matches on software-engineering, apis-backend, python, typescript-node; remote compatible
- [Senior Software Engineer, Backend \| Audit Product Team](https://job-boards.greenhouse.io/machinifyinc/jobs/4398217009) — Machinify | Remote - US | fit MEDIUM 0.47 | priority MEDIUM 0.54 | matches on backend, software-engineering, agents, apis-backend; remote compatible
- [Software Engineer, Enterprise Security](https://job-boards.greenhouse.io/warp/jobs/6163780004) — Warp | Remote | fit MEDIUM 0.46 | priority MEDIUM 0.52 | matches on software-engineering, agents, orchestration; remote compatible
- [Software Architect](https://job-boards.greenhouse.io/machinifyinc/jobs/4222312009) — Machinify | Remote - US | fit MEDIUM 0.50 | priority MEDIUM 0.51 | matches on agents, apis-backend, llms, orchestration, python, retrieval; ordinary title, but the described work is in lane; remote compatible
- [Staff Data Scientist \| ML](https://job-boards.greenhouse.io/machinifyinc/jobs/4134253009) — Machinify | Remote - US | fit MEDIUM 0.48 | priority MEDIUM 0.50 | matches on ai-focus, machine-learning, llms; stretch level — judge the actual scope; remote compatible
- [Staff Data Scientist \| NLP](https://job-boards.greenhouse.io/machinifyinc/jobs/4146869009) — Machinify | Remote - US | fit MEDIUM 0.46 | priority MEDIUM 0.49 | matches on machine-learning, agents, apis-backend, aws-serverless, llms, python; stretch level — judge the actual scope; remote compatible
- [Staff Software Engineer \| Platform Team](https://job-boards.greenhouse.io/machinifyinc/jobs/4130254009) — Machinify | Remote - US | fit MEDIUM 0.45 | priority MEDIUM 0.49 | matches on platform, software-engineering, python; stretch level — judge the actual scope; remote compatible

## New since the last round

Nothing credible arrived since the previous check. Older strong fits below are still worth the morning; this is not an empty day.

## Older, still strong

Retained because the fit is strong, not because they are new. Age is stated on each row; nothing here is excluded for being older than the fresh window.

- [AI Engineer \| Agentic Systems](https://job-boards.greenhouse.io/machinifyinc/jobs/4146862009) — Machinify | Remote - US | fit HIGH 1.00 | priority HIGH 0.73 | matches on agentic-ai, ai-focus, applied-ai, agents, evals, llms; remote compatible | no publication date; employer last edited it 132d ago (an edit is not a new posting)
- [Agentic AI Engineer / Software Engineer - AI Applications (Remote US)](https://job-boards.greenhouse.io/yurtsai/jobs/5243856007) — Legion Intelligence | Remote USA | fit HIGH 0.94 | priority HIGH 0.77 | matches on agentic-ai, ai-focus, applied-ai, software-engineering, agents, apis-backend; remote compatible | no publication date; employer last edited it 3d ago (an edit is not a new posting)
- [AI Engineer](https://job-boards.greenhouse.io/cargomatic/jobs/5207803008) — Cargomatic | United States | fit HIGH 0.91 | priority HIGH 0.70 | matches on ai-focus, applied-ai, agents, apis-backend, aws-serverless, data-pipelines; remote compatible | no publication date; employer last edited it 14d ago (an edit is not a new posting)
- [Applied AI Engineer](https://job-boards.greenhouse.io/future/jobs/4683133005) — Future | Remote  | fit HIGH 0.91 | priority MEDIUM 0.69 | matches on ai-focus, applied-ai, agents, apis-backend, aws-serverless, evals; remote compatible | no publication date; employer last edited it 113d ago (an edit is not a new posting)
- [AI Engineer (US-Based / Part-Time)](https://job-boards.greenhouse.io/implicit/jobs/8039713) — Implicit | Remote / US-Based | fit HIGH 0.91 | priority HIGH 0.70 | matches on ai-focus, applied-ai, agents, apis-backend, llms, python; remote compatible | no publication date; employer last edited it 58d ago (an edit is not a new posting)
- [Senior Applied AI Engineer](https://job-boards.greenhouse.io/stackblitz/jobs/4005254009) — Bolt New | Remote | fit HIGH 0.91 | priority MEDIUM 0.69 | matches on ai-focus, applied-ai, agents, apis-backend, evals, llms; remote compatible | no publication date; employer last edited it 10d ago (an edit is not a new posting)
- [AI Engineer](https://job-boards.greenhouse.io/solutions/jobs/4680769006) — Cadence Solutions | Remote | fit HIGH 0.90 | priority MEDIUM 0.69 | matches on ai-focus, applied-ai, agents, apis-backend, llms, orchestration; remote compatible | no publication date; employer last edited it 65d ago (an edit is not a new posting)
- [Staff Applied AI Engineer](https://job-boards.greenhouse.io/stackblitz/jobs/4111216009) — Bolt New | Remote | fit HIGH 0.83 | priority MEDIUM 0.66 | matches on ai-focus, applied-ai, agents, apis-backend, evals, llms; stretch level — judge the actual scope; remote compatible | no publication date; employer last edited it 10d ago (an edit is not a new posting)
- [Senior Software Engineer - Machine Learning (Remote US)](https://job-boards.greenhouse.io/yurtsai/jobs/5205127007) — Legion Intelligence | USA | fit HIGH 0.83 | priority MEDIUM 0.66 | matches on machine-learning, software-engineering, agents, apis-backend, llms, orchestration; us wide location | no publication date; employer last edited it 3d ago (an edit is not a new posting)
- [Staff AI Engineer](https://job-boards.greenhouse.io/machinifyinc/jobs/4212332009) — Machinify | US | fit HIGH 0.75 | priority MEDIUM 0.62 | matches on ai-focus, applied-ai, evals, llms, mcp, orchestration; stretch level — judge the actual scope; us wide location | no publication date; employer last edited it 126d ago (an edit is not a new posting)
- [Staff AI Engineer \| US \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6092955004) — Grafana Labs | United States (Remote) | fit MEDIUM 0.68 | priority MEDIUM 0.59 | matches on ai-focus, applied-ai, agents, apis-backend, aws-serverless, evals; stretch level — judge the actual scope; remote compatible | no publication date; employer last edited it 28d ago (an edit is not a new posting)
- [Software Engineer, Strategic Projects](https://job-boards.greenhouse.io/tailscale/jobs/4721714005) — Tailscale | Remote (United States) | fit MEDIUM 0.67 | priority MEDIUM 0.59 | matches on software-engineering, agents, apis-backend, llms, mcp, python; remote compatible | no publication date; employer last edited it 50d ago (an edit is not a new posting)
- [AI Architect](https://job-boards.greenhouse.io/nimblegravity/jobs/4699013005) — Nimble Gravity | LATAM (Remote), US (Remote) | fit MEDIUM 0.63 | priority MEDIUM 0.58 | matches on ai-focus, agents, apis-backend, orchestration, python, retrieval; remote compatible | no publication date; employer last edited it 25d ago (an edit is not a new posting)
- [Forward Deployed Engineer](https://job-boards.greenhouse.io/warp/jobs/5749183004) — Warp | New York, New York | fit MEDIUM 0.63 | priority MEDIUM 0.57 | matches on forward-deployed, agents, apis-backend, aws-serverless, llms, mcp; remote compatible | no publication date; employer last edited it 56d ago (an edit is not a new posting)
- [Staff Software Engineer (Backend)](https://job-boards.eu.greenhouse.io/axiomaticai/jobs/4885093101) — Axiomatic Ai | Boston, US | fit MEDIUM 0.61 | priority MEDIUM 0.57 | matches on backend, software-engineering, apis-backend, evals, llms, mcp; stretch level — judge the actual scope; nh ma compatible | no publication date; employer last edited it 59d ago (an edit is not a new posting)
- [Staff Backend Engineer - Analytics \| US \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6114603004) — Grafana Labs | United States (Remote) | fit MEDIUM 0.55 | priority MEDIUM 0.53 | matches on backend, agents, apis-backend, aws-serverless, llms, mcp; stretch level — judge the actual scope; remote compatible | no publication date; employer last edited it 3d ago (an edit is not a new posting)
- [Senior Software Engineer, Cloud Engineering](https://job-boards.greenhouse.io/mozilla/jobs/8031378) — Mozilla | Remote | fit MEDIUM 0.55 | priority MEDIUM 0.58 | matches on software-engineering, agents, aws-serverless, python; remote compatible | no publication date; employer last edited it 23h ago (an edit is not a new posting)
- [Copilot & Power Platform Architect](https://job-boards.greenhouse.io/nimblegravity/jobs/4720332005) — Nimble Gravity | US (Remote) LATAM (Remote) | fit MEDIUM 0.54 | priority MEDIUM 0.54 | matches on platform, apis-backend, orchestration, python, retrieval, typescript-node; remote compatible | no publication date; employer last edited it 21d ago (an edit is not a new posting)
- [Senior Software Engineer - Rails](https://job-boards.greenhouse.io/stackblitz/jobs/4006004009) — Bolt New | Remote | fit MEDIUM 0.54 | priority MEDIUM 0.59 | matches on software-engineering, apis-backend, aws-serverless, llms, typescript-node; remote compatible | no publication date; employer last edited it 2d ago (an edit is not a new posting)
- [Senior RUST Developer / Senior Software Engineer - Platform (Remote US)](https://job-boards.greenhouse.io/yurtsai/jobs/5171066007) — Legion Intelligence | Remote USA | fit MEDIUM 0.54 | priority MEDIUM 0.53 | matches on platform, software-engineering, agents, apis-backend, orchestration; remote compatible | no publication date; employer last edited it 3d ago (an edit is not a new posting)

## Needs a check before preparing

These are credible on the evidence available, but something specific is unconfirmed.

- [Agentic AI Engineer / Software Engineer - AI Applications (Remote US)](https://job-boards.greenhouse.io/yurtsai/jobs/5243856007) — Legion Intelligence | Remote USA | fit HIGH 0.94 | priority HIGH 0.77 | matches on agentic-ai, ai-focus, applied-ai, software-engineering, agents, apis-backend; remote compatible
- [Senior Software Engineer - Machine Learning (Remote US)](https://job-boards.greenhouse.io/yurtsai/jobs/5205127007) — Legion Intelligence | USA | fit HIGH 0.83 | priority MEDIUM 0.66 | matches on machine-learning, software-engineering, agents, apis-backend, llms, orchestration; us wide location
- [Staff Applied AI Engineer](https://job-boards.greenhouse.io/stackblitz/jobs/4111216009) — Bolt New | Remote | fit HIGH 0.83 | priority MEDIUM 0.66 | matches on ai-focus, applied-ai, agents, apis-backend, evals, llms; stretch level — judge the actual scope; remote compatible
- [Staff AI Engineer](https://job-boards.greenhouse.io/machinifyinc/jobs/4212332009) — Machinify | US | fit HIGH 0.75 | priority MEDIUM 0.62 | matches on ai-focus, applied-ai, evals, llms, mcp, orchestration; stretch level — judge the actual scope; us wide location
- [Staff AI Engineer \| US \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6092955004) — Grafana Labs | United States (Remote) | fit MEDIUM 0.68 | priority MEDIUM 0.59 | matches on ai-focus, applied-ai, agents, apis-backend, aws-serverless, evals; stretch level — judge the actual scope; remote compatible
- [AI Architect](https://job-boards.greenhouse.io/nimblegravity/jobs/4699013005) — Nimble Gravity | LATAM (Remote), US (Remote) | fit MEDIUM 0.63 | priority MEDIUM 0.58 | matches on ai-focus, agents, apis-backend, orchestration, python, retrieval; remote compatible
- [Forward Deployed Engineer](https://job-boards.greenhouse.io/warp/jobs/5749183004) — Warp | New York, New York | fit MEDIUM 0.63 | priority MEDIUM 0.57 | matches on forward-deployed, agents, apis-backend, aws-serverless, llms, mcp; remote compatible
- [Staff Software Engineer (Backend)](https://job-boards.eu.greenhouse.io/axiomaticai/jobs/4885093101) — Axiomatic Ai | Boston, US | fit MEDIUM 0.61 | priority MEDIUM 0.57 | matches on backend, software-engineering, apis-backend, evals, llms, mcp; stretch level — judge the actual scope; nh ma compatible
- [Copilot & Power Platform Architect](https://job-boards.greenhouse.io/nimblegravity/jobs/4720332005) — Nimble Gravity | US (Remote) LATAM (Remote) | fit MEDIUM 0.54 | priority MEDIUM 0.54 | matches on platform, apis-backend, orchestration, python, retrieval, typescript-node; remote compatible
- [Staff Backend Engineer - Analytics \| US \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6114603004) — Grafana Labs | United States (Remote) | fit MEDIUM 0.55 | priority MEDIUM 0.53 | matches on backend, agents, apis-backend, aws-serverless, llms, mcp; stretch level — judge the actual scope; remote compatible
- [Senior RUST Developer / Senior Software Engineer - Platform (Remote US)](https://job-boards.greenhouse.io/yurtsai/jobs/5171066007) — Legion Intelligence | Remote USA | fit MEDIUM 0.54 | priority MEDIUM 0.53 | matches on platform, software-engineering, agents, apis-backend, orchestration; remote compatible
- [Software Engineer](https://job-boards.greenhouse.io/warp/jobs/4324888004) — Warp | New York, New York | fit MEDIUM 0.51 | priority MEDIUM 0.51 | matches on software-engineering, agents, apis-backend, orchestration; remote compatible
- [Staff Backend Engineer - Mimir Query, Databases \| USA \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6146604004) — Grafana Labs | United States (Remote) | fit MEDIUM 0.45 | priority MEDIUM 0.51 | matches on backend, apis-backend, aws-serverless, llms, python; stretch level — judge the actual scope; remote compatible
- [Principal Software Engineer / Rust Programmer - Platform (Remote US)](https://job-boards.greenhouse.io/yurtsai/jobs/5207621007) — Legion Intelligence | Remote USA | fit MEDIUM 0.46 | priority MEDIUM 0.50 | matches on platform, software-engineering, agents, apis-backend, orchestration; stretch level — judge the actual scope; remote compatible
- [Senior FullStack Engineer - Grafana Cloud Observability\| US \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6130907004) — Grafana Labs | United States (Remote) | fit MEDIUM 0.46 | priority MEDIUM 0.49 | matches on software-engineering, apis-backend, llms, typescript-node; remote compatible
- [Software Engineer (All Levels)](https://job-boards.greenhouse.io/solutions/jobs/4679222006) — Cadence Solutions | Remote | fit MEDIUM 0.40 | priority MEDIUM 0.47 | matches on software-engineering, apis-backend, aws-serverless; remote compatible

## Already prepared, submitted, or set aside

Surfaced separately so useful queued work stays visible without being announced as new.

- [AI Engineer \| Agentic Systems](https://job-boards.greenhouse.io/machinifyinc/jobs/4146862009) — Machinify | Remote - US | fit HIGH 1.00 | priority HIGH 0.73 | matches on agentic-ai, ai-focus, applied-ai, agents, evals, llms; remote compatible — history: SUBMITTED (Re-prepared on 2026-09-08 as the same requisition while already submitted on 2026-08-03; the submission stands and the later package is a duplicate.)
- [AI Engineer](https://job-boards.greenhouse.io/cargomatic/jobs/5207803008) — Cargomatic | United States | fit HIGH 0.91 | priority HIGH 0.70 | matches on ai-focus, applied-ai, agents, apis-backend, aws-serverless, data-pipelines; remote compatible — history: SUBMITTED
- [AI Engineer (US-Based / Part-Time)](https://job-boards.greenhouse.io/implicit/jobs/8039713) — Implicit | Remote / US-Based | fit HIGH 0.91 | priority HIGH 0.70 | matches on ai-focus, applied-ai, agents, apis-backend, llms, python; remote compatible — history: SUBMITTED
- [Applied AI Engineer](https://job-boards.greenhouse.io/future/jobs/4683133005) — Future | Remote  | fit HIGH 0.91 | priority MEDIUM 0.69 | matches on ai-focus, applied-ai, agents, apis-backend, aws-serverless, evals; remote compatible — history: SUBMITTED
- [Senior Applied AI Engineer](https://job-boards.greenhouse.io/stackblitz/jobs/4005254009) — Bolt New | Remote | fit HIGH 0.91 | priority MEDIUM 0.69 | matches on ai-focus, applied-ai, agents, apis-backend, evals, llms; remote compatible — history: SUBMITTED
- [AI Engineer](https://job-boards.greenhouse.io/solutions/jobs/4680769006) — Cadence Solutions | Remote | fit HIGH 0.90 | priority MEDIUM 0.69 | matches on ai-focus, applied-ai, agents, apis-backend, llms, orchestration; remote compatible — history: SUBMITTED
- [Software Engineer, Strategic Projects](https://job-boards.greenhouse.io/tailscale/jobs/4721714005) — Tailscale | Remote (United States) | fit MEDIUM 0.67 | priority MEDIUM 0.59 | matches on software-engineering, agents, apis-backend, llms, mcp, python; remote compatible — history: PREPARED (Same Tailscale ambiguity as the AI Enablement package. Needs operator confirmation.)

## Complete candidate list

All 35 retained credible role(s), each with a direct link and a reason. This is the full set — there is no hidden overflow.

1. **Bolt New** — [Senior Software Engineer - Rails](https://job-boards.greenhouse.io/stackblitz/jobs/4006004009)  
   Remote · compensation not published · UNSPECIFIED · via `greenhouse:stackblitz`  
   fit MEDIUM 0.54 · priority MEDIUM 0.59 · screen ELIGIBLE · history NEW  
   why: matches on software-engineering, apis-backend, aws-serverless, llms, typescript-node; remote compatible  
   check: no published compensation  
   dates: employer updated 2026-09-22; first seen by JPRS 2026-09-22  
   age: no publication date; employer last edited it 2d ago (an edit is not a new posting)  

2. **Mozilla** — [Senior Software Engineer, Cloud Engineering](https://job-boards.greenhouse.io/mozilla/jobs/8031378)  
   Remote · compensation not published · UNSPECIFIED · via `greenhouse:mozilla`  
   fit MEDIUM 0.55 · priority MEDIUM 0.58 · screen ELIGIBLE · history NEW  
   why: matches on software-engineering, agents, aws-serverless, python; remote compatible  
   check: no published compensation  
   dates: employer updated 2026-09-24; first seen by JPRS 2026-09-10  
   age: no publication date; employer last edited it 23h ago (an edit is not a new posting)  

3. **Machinify** — [Senior Data Engineer - Analytics](https://job-boards.greenhouse.io/machinifyinc/jobs/4418234009)  
   Remote - US · 170,000-200,000 USD · UNSPECIFIED · via `greenhouse:machinifyinc`  
   fit MEDIUM 0.50 · priority MEDIUM 0.57 · screen ELIGIBLE · history NEW  
   why: matches on data-engineering, apis-backend, llms, orchestration, python; remote compatible  
   dates: employer updated 2026-09-23; first seen by JPRS 2026-09-24  
   age: no publication date; employer last edited it 39h ago (an edit is not a new posting)  

4. **Mozilla** — [Senior Software Engineer](https://job-boards.greenhouse.io/mozilla/jobs/8204384)  
   Remote · compensation not published · UNSPECIFIED · via `greenhouse:mozilla`  
   fit MEDIUM 0.45 · priority MEDIUM 0.55 · screen ELIGIBLE · history NEW  
   why: matches on software-engineering, apis-backend, python, typescript-node; remote compatible  
   check: no published compensation  
   dates: employer updated 2026-09-24; first seen by JPRS 2026-09-25  
   age: no publication date; employer last edited it 16h ago (an edit is not a new posting)  

5. **Mozilla** — [Senior Software Engineer](https://job-boards.greenhouse.io/mozilla/jobs/8209734)  
   Remote US · compensation not published · UNSPECIFIED · via `greenhouse:mozilla`  
   fit MEDIUM 0.45 · priority MEDIUM 0.55 · screen ELIGIBLE · history NEW  
   why: matches on software-engineering, apis-backend, python, typescript-node; remote compatible  
   check: no published compensation  
   dates: employer updated 2026-09-24; first seen by JPRS 2026-09-25  
   age: no publication date; employer last edited it 16h ago (an edit is not a new posting)  

6. **Mozilla** — [Senior Software Engineer, Add-Ons](https://job-boards.greenhouse.io/mozilla/jobs/7524337)  
   Remote · compensation not published · UNSPECIFIED · via `greenhouse:mozilla`  
   fit MEDIUM 0.45 · priority MEDIUM 0.55 · screen ELIGIBLE · history NEW  
   why: matches on software-engineering, apis-backend, python, typescript-node; remote compatible  
   check: no published compensation  
   dates: employer updated 2026-09-24; first seen by JPRS 2026-09-23  
   age: no publication date; employer last edited it 23h ago (an edit is not a new posting)  

7. **Machinify** — [Senior Software Engineer, Backend \| Audit Product Team](https://job-boards.greenhouse.io/machinifyinc/jobs/4398217009)  
   Remote - US · 200,000-230,000 USD · UNSPECIFIED · via `greenhouse:machinifyinc`  
   fit MEDIUM 0.47 · priority MEDIUM 0.54 · screen ELIGIBLE · history NEW  
   why: matches on backend, software-engineering, agents, apis-backend; remote compatible  
   dates: employer updated 2026-09-08; first seen by JPRS 2026-09-09  
   age: no publication date; employer last edited it 16d ago (an edit is not a new posting)  

8. **Warp** — [Software Engineer, Enterprise Security](https://job-boards.greenhouse.io/warp/jobs/6163780004)  
   Remote · 230,000-290,000 USD · UNSPECIFIED · via `greenhouse:warp`  
   fit MEDIUM 0.46 · priority MEDIUM 0.52 · screen ELIGIBLE · history NEW  
   why: matches on software-engineering, agents, orchestration; remote compatible  
   dates: employer updated 2026-08-28; first seen by JPRS 2026-08-27  
   age: no publication date; employer last edited it 27d ago (an edit is not a new posting)  

9. **Machinify** — [Software Architect](https://job-boards.greenhouse.io/machinifyinc/jobs/4222312009)  
   Remote - US · 230,000-280,000 USD · UNSPECIFIED · via `greenhouse:machinifyinc`  
   fit MEDIUM 0.50 · priority MEDIUM 0.51 · screen ELIGIBLE · history NEW  
   why: matches on agents, apis-backend, llms, orchestration, python, retrieval; ordinary title, but the described work is in lane; remote compatible  
   dates: employer updated 2026-04-16; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 161d ago (an edit is not a new posting)  

10. **Machinify** — [Staff Data Scientist \| ML](https://job-boards.greenhouse.io/machinifyinc/jobs/4134253009)  
   Remote - US · compensation not published · UNSPECIFIED · via `greenhouse:machinifyinc`  
   fit MEDIUM 0.48 · priority MEDIUM 0.50 · screen ELIGIBLE · history NEW  
   why: matches on ai-focus, machine-learning, llms; stretch level — judge the actual scope; remote compatible  
   check: no published compensation  
   dates: employer updated 2026-05-15; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 132d ago (an edit is not a new posting)  

11. **Machinify** — [Staff Data Scientist \| NLP](https://job-boards.greenhouse.io/machinifyinc/jobs/4146869009)  
   Remote - US · 180,000-230,000 USD · UNSPECIFIED · via `greenhouse:machinifyinc`  
   fit MEDIUM 0.46 · priority MEDIUM 0.49 · screen ELIGIBLE · history NEW  
   why: matches on machine-learning, agents, apis-backend, aws-serverless, llms, python; stretch level — judge the actual scope; remote compatible  
   dates: employer updated 2026-05-21; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 126d ago (an edit is not a new posting)  

12. **Machinify** — [Staff Software Engineer \| Platform Team](https://job-boards.greenhouse.io/machinifyinc/jobs/4130254009)  
   Remote - US · 225,000-260,000 USD · UNSPECIFIED · via `greenhouse:machinifyinc`  
   fit MEDIUM 0.45 · priority MEDIUM 0.49 · screen ELIGIBLE · history NEW  
   why: matches on platform, software-engineering, python; stretch level — judge the actual scope; remote compatible  
   dates: employer updated 2026-08-24; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 31d ago (an edit is not a new posting)  

13. **Legion Intelligence** — [Agentic AI Engineer / Software Engineer - AI Applications (Remote US)](https://job-boards.greenhouse.io/yurtsai/jobs/5243856007)  
   Remote USA · compensation not published · UNSPECIFIED · via `greenhouse:yurtsai`  
   fit HIGH 0.94 · priority HIGH 0.77 · screen PENDING_CHECK · history NEW  
   why: matches on agentic-ai, ai-focus, applied-ai, software-engineering, agents, apis-backend; remote compatible  
   check: government-adjacent without a stated clearance requirement; the policy requires explicit operator reconsideration before preparation rather than an automatic exclusion or an automatic pass; no published compensation  
   dates: employer updated 2026-09-21; first seen by JPRS 2026-09-22  
   age: no publication date; employer last edited it 3d ago (an edit is not a new posting)  

14. **Legion Intelligence** — [Senior Software Engineer - Machine Learning (Remote US)](https://job-boards.greenhouse.io/yurtsai/jobs/5205127007)  
   USA · compensation not published · UNSPECIFIED · via `greenhouse:yurtsai`  
   fit HIGH 0.83 · priority MEDIUM 0.66 · screen PENDING_CHECK · history NEW  
   why: matches on machine-learning, software-engineering, agents, apis-backend, llms, orchestration; us wide location  
   check: government-adjacent without a stated clearance requirement; the policy requires explicit operator reconsideration before preparation rather than an automatic exclusion or an automatic pass; no explicit remote statement and the worksite is unclear; eligibility from New Hampshire needs confirmation before preparation; no published compensation  
   dates: employer updated 2026-09-21; first seen by JPRS 2026-08-06  
   age: no publication date; employer last edited it 3d ago (an edit is not a new posting)  

15. **Bolt New** — [Staff Applied AI Engineer](https://job-boards.greenhouse.io/stackblitz/jobs/4111216009)  
   Remote · compensation not published · UNSPECIFIED · via `greenhouse:stackblitz`  
   fit HIGH 0.83 · priority MEDIUM 0.66 · screen PENDING_CHECK · history NEW  
   why: matches on ai-focus, applied-ai, agents, apis-backend, evals, llms; stretch level — judge the actual scope; remote compatible  
   check: the posting does not describe its interview or application process; the live form still needs inspection for recorded-video and AI-interview requirements; no published compensation  
   dates: employer updated 2026-09-14; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 10d ago (an edit is not a new posting)  

16. **Machinify** — [Staff AI Engineer](https://job-boards.greenhouse.io/machinifyinc/jobs/4212332009)  
   US · 210,000-280,000 USD · UNSPECIFIED · via `greenhouse:machinifyinc`  
   fit HIGH 0.75 · priority MEDIUM 0.62 · screen PENDING_CHECK · history NEW  
   why: matches on ai-focus, applied-ai, evals, llms, mcp, orchestration; stretch level — judge the actual scope; us wide location  
   check: no explicit remote statement and the worksite is unclear; eligibility from New Hampshire needs confirmation before preparation  
   dates: employer updated 2026-05-21; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 126d ago (an edit is not a new posting)  

17. **Grafana Labs** — [Staff AI Engineer \| US \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6092955004)  
   United States (Remote) · compensation not published · UNSPECIFIED · via `greenhouse:grafanalabs`  
   fit MEDIUM 0.68 · priority MEDIUM 0.59 · screen PENDING_CHECK · history NEW  
   why: matches on ai-focus, applied-ai, agents, apis-backend, aws-serverless, evals; stretch level — judge the actual scope; remote compatible  
   check: the posting does not describe its interview or application process; the live form still needs inspection for recorded-video and AI-interview requirements; no published compensation  
   dates: employer updated 2026-08-27; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 28d ago (an edit is not a new posting)  

18. **Nimble Gravity** — [AI Architect](https://job-boards.greenhouse.io/nimblegravity/jobs/4699013005)  
   LATAM (Remote), US (Remote) · compensation not published · UNSPECIFIED · via `greenhouse:nimblegravity`  
   fit MEDIUM 0.63 · priority MEDIUM 0.58 · screen PENDING_CHECK · history NEW  
   why: matches on ai-focus, agents, apis-backend, orchestration, python, retrieval; remote compatible  
   check: the posting does not describe its interview or application process; the live form still needs inspection for recorded-video and AI-interview requirements; no published compensation  
   dates: employer updated 2026-08-30; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 25d ago (an edit is not a new posting)  

19. **Warp** — [Forward Deployed Engineer](https://job-boards.greenhouse.io/warp/jobs/5749183004)  
   New York, New York · 200,000-250,000 USD · UNSPECIFIED · via `greenhouse:warp`  
   fit MEDIUM 0.63 · priority MEDIUM 0.57 · screen PENDING_CHECK · history NEW  
   why: matches on forward-deployed, agents, apis-backend, aws-serverless, llms, mcp; remote compatible  
   check: no explicit remote statement and the worksite is unclear; eligibility from New Hampshire needs confirmation before preparation  
   dates: employer updated 2026-07-30; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 56d ago (an edit is not a new posting)  

20. **Axiomatic Ai** — [Staff Software Engineer (Backend)](https://job-boards.eu.greenhouse.io/axiomaticai/jobs/4885093101)  
   Boston, US · compensation not published · UNSPECIFIED · via `greenhouse:axiomaticai`  
   fit MEDIUM 0.61 · priority MEDIUM 0.57 · screen PENDING_CHECK · history NEW  
   why: matches on backend, software-engineering, apis-backend, evals, llms, mcp; stretch level — judge the actual scope; nh ma compatible  
   check: onsite or hybrid presence is required but the worksite could not be identified from the posting; confirm where the work happens before preparing; the posting does not describe its interview or application process; the live form still needs inspection for recorded-video and AI-interview requirements; no published compensation  
   dates: employer updated 2026-07-27; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 59d ago (an edit is not a new posting)  

21. **Nimble Gravity** — [Copilot & Power Platform Architect](https://job-boards.greenhouse.io/nimblegravity/jobs/4720332005)  
   US (Remote) LATAM (Remote) · compensation not published · UNSPECIFIED · via `greenhouse:nimblegravity`  
   fit MEDIUM 0.54 · priority MEDIUM 0.54 · screen PENDING_CHECK · history NEW  
   why: matches on platform, apis-backend, orchestration, python, retrieval, typescript-node; remote compatible  
   check: government-adjacent without a stated clearance requirement; the policy requires explicit operator reconsideration before preparation rather than an automatic exclusion or an automatic pass; the posting does not describe its interview or application process; the live form still needs inspection for recorded-video and AI-interview requirements; no published compensation  
   dates: employer updated 2026-09-03; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 21d ago (an edit is not a new posting)  

22. **Grafana Labs** — [Staff Backend Engineer - Analytics \| US \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6114603004)  
   United States (Remote) · compensation not published · UNSPECIFIED · via `greenhouse:grafanalabs`  
   fit MEDIUM 0.55 · priority MEDIUM 0.53 · screen PENDING_CHECK · history NEW  
   why: matches on backend, agents, apis-backend, aws-serverless, llms, mcp; stretch level — judge the actual scope; remote compatible  
   check: the posting does not describe its interview or application process; the live form still needs inspection for recorded-video and AI-interview requirements; no published compensation  
   dates: employer updated 2026-09-21; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 3d ago (an edit is not a new posting)  

23. **Legion Intelligence** — [Senior RUST Developer / Senior Software Engineer - Platform (Remote US)](https://job-boards.greenhouse.io/yurtsai/jobs/5171066007)  
   Remote USA · compensation not published · UNSPECIFIED · via `greenhouse:yurtsai`  
   fit MEDIUM 0.54 · priority MEDIUM 0.53 · screen PENDING_CHECK · history NEW  
   why: matches on platform, software-engineering, agents, apis-backend, orchestration; remote compatible  
   check: government-adjacent without a stated clearance requirement; the policy requires explicit operator reconsideration before preparation rather than an automatic exclusion or an automatic pass; the posting does not describe its interview or application process; the live form still needs inspection for recorded-video and AI-interview requirements; no published compensation  
   dates: employer updated 2026-09-21; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 3d ago (an edit is not a new posting)  

24. **Warp** — [Software Engineer](https://job-boards.greenhouse.io/warp/jobs/4324888004)  
   New York, New York · 165,000-260,000 USD · UNSPECIFIED · via `greenhouse:warp`  
   fit MEDIUM 0.51 · priority MEDIUM 0.51 · screen PENDING_CHECK · history NEW  
   why: matches on software-engineering, agents, apis-backend, orchestration; remote compatible  
   check: no explicit remote statement and the worksite is unclear; eligibility from New Hampshire needs confirmation before preparation  
   dates: employer updated 2026-08-24; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 31d ago (an edit is not a new posting)  

25. **Grafana Labs** — [Staff Backend Engineer - Mimir Query, Databases \| USA \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6146604004)  
   United States (Remote) · compensation not published · UNSPECIFIED · via `greenhouse:grafanalabs`  
   fit MEDIUM 0.45 · priority MEDIUM 0.51 · screen PENDING_CHECK · history NEW  
   why: matches on backend, apis-backend, aws-serverless, llms, python; stretch level — judge the actual scope; remote compatible  
   check: the posting does not describe its interview or application process; the live form still needs inspection for recorded-video and AI-interview requirements; no published compensation  
   dates: employer updated 2026-09-17; first seen by JPRS 2026-08-19  
   age: no publication date; employer last edited it 7d ago (an edit is not a new posting)  

26. **Legion Intelligence** — [Principal Software Engineer / Rust Programmer - Platform (Remote US)](https://job-boards.greenhouse.io/yurtsai/jobs/5207621007)  
   Remote USA · compensation not published · UNSPECIFIED · via `greenhouse:yurtsai`  
   fit MEDIUM 0.46 · priority MEDIUM 0.50 · screen PENDING_CHECK · history NEW  
   why: matches on platform, software-engineering, agents, apis-backend, orchestration; stretch level — judge the actual scope; remote compatible  
   check: government-adjacent without a stated clearance requirement; the policy requires explicit operator reconsideration before preparation rather than an automatic exclusion or an automatic pass; no published compensation  
   dates: employer updated 2026-09-21; first seen by JPRS 2026-08-08  
   age: no publication date; employer last edited it 3d ago (an edit is not a new posting)  

27. **Grafana Labs** — [Senior FullStack Engineer - Grafana Cloud Observability\| US \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6130907004)  
   United States (Remote) · 185-154,445 USD · UNSPECIFIED · via `greenhouse:grafanalabs`  
   fit MEDIUM 0.46 · priority MEDIUM 0.49 · screen PENDING_CHECK · history NEW  
   why: matches on software-engineering, apis-backend, llms, typescript-node; remote compatible  
   check: the posting does not describe its interview or application process; the live form still needs inspection for recorded-video and AI-interview requirements  
   dates: employer updated 2026-08-31; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 24d ago (an edit is not a new posting)  

28. **Cadence Solutions** — [Software Engineer (All Levels)](https://job-boards.greenhouse.io/solutions/jobs/4679222006)  
   Remote · 150,000-250,000 USD · UNSPECIFIED · via `greenhouse:solutions`  
   fit MEDIUM 0.40 · priority MEDIUM 0.47 · screen PENDING_CHECK · history NEW  
   why: matches on software-engineering, apis-backend, aws-serverless; remote compatible  
   check: the posting does not describe its interview or application process; the live form still needs inspection for recorded-video and AI-interview requirements  
   dates: employer updated 2026-07-22; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 64d ago (an edit is not a new posting)  

29. **Machinify** — [AI Engineer \| Agentic Systems](https://job-boards.greenhouse.io/machinifyinc/jobs/4146862009)  
   Remote - US · 130,000-200,000 USD · UNSPECIFIED · via `greenhouse:machinifyinc`  
   fit HIGH 1.00 · priority HIGH 0.73 · screen ELIGIBLE · history SUBMITTED  
   why: matches on agentic-ai, ai-focus, applied-ai, agents, evals, llms; remote compatible  
   dates: employer updated 2026-05-15; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 132d ago (an edit is not a new posting)  

30. **Cargomatic** — [AI Engineer](https://job-boards.greenhouse.io/cargomatic/jobs/5207803008)  
   United States · 150,000-210,000 USD · UNSPECIFIED · via `greenhouse:cargomatic`  
   fit HIGH 0.91 · priority HIGH 0.70 · screen PENDING_CHECK · history SUBMITTED  
   why: matches on ai-focus, applied-ai, agents, apis-backend, aws-serverless, data-pipelines; remote compatible  
   check: the posting does not describe its interview or application process; the live form still needs inspection for recorded-video and AI-interview requirements  
   dates: employer updated 2026-09-10; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 14d ago (an edit is not a new posting)  

31. **Implicit** — [AI Engineer (US-Based / Part-Time)](https://job-boards.greenhouse.io/implicit/jobs/8039713)  
   Remote / US-Based · compensation not published · UNSPECIFIED · via `greenhouse:implicit`  
   fit HIGH 0.91 · priority HIGH 0.70 · screen ELIGIBLE · history SUBMITTED  
   why: matches on ai-focus, applied-ai, agents, apis-backend, llms, python; remote compatible  
   check: no published compensation  
   dates: employer updated 2026-07-28; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 58d ago (an edit is not a new posting)  

32. **Future** — [Applied AI Engineer](https://job-boards.greenhouse.io/future/jobs/4683133005)  
   Remote  · 215,000-250,000 USD · UNSPECIFIED · via `greenhouse:future`  
   fit HIGH 0.91 · priority MEDIUM 0.69 · screen PENDING_CHECK · history SUBMITTED  
   why: matches on ai-focus, applied-ai, agents, apis-backend, aws-serverless, evals; remote compatible  
   check: the posting does not describe its interview or application process; the live form still needs inspection for recorded-video and AI-interview requirements  
   dates: employer updated 2026-06-03; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 113d ago (an edit is not a new posting)  

33. **Bolt New** — [Senior Applied AI Engineer](https://job-boards.greenhouse.io/stackblitz/jobs/4005254009)  
   Remote · compensation not published · UNSPECIFIED · via `greenhouse:stackblitz`  
   fit HIGH 0.91 · priority MEDIUM 0.69 · screen ELIGIBLE · history SUBMITTED  
   why: matches on ai-focus, applied-ai, agents, apis-backend, evals, llms; remote compatible  
   check: no published compensation  
   dates: employer updated 2026-09-14; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 10d ago (an edit is not a new posting)  

34. **Cadence Solutions** — [AI Engineer](https://job-boards.greenhouse.io/solutions/jobs/4680769006)  
   Remote · 150,000-250,000 USD · UNSPECIFIED · via `greenhouse:solutions`  
   fit HIGH 0.90 · priority MEDIUM 0.69 · screen PENDING_CHECK · history SUBMITTED  
   why: matches on ai-focus, applied-ai, agents, apis-backend, llms, orchestration; remote compatible  
   check: the posting does not describe its interview or application process; the live form still needs inspection for recorded-video and AI-interview requirements  
   dates: employer updated 2026-07-21; first seen by JPRS 2026-08-02  
   age: no publication date; employer last edited it 65d ago (an edit is not a new posting)  

35. **Tailscale** — [Software Engineer, Strategic Projects](https://job-boards.greenhouse.io/tailscale/jobs/4721714005)  
   Remote (United States) · compensation not published · UNSPECIFIED · via `greenhouse:tailscale`  
   fit MEDIUM 0.67 · priority MEDIUM 0.59 · screen ELIGIBLE · history PREPARED  
   why: matches on software-engineering, agents, apis-backend, llms, mcp, python; remote compatible  
   check: no published compensation  
   dates: employer updated 2026-08-05; first seen by JPRS 2026-08-06  
   age: no publication date; employer last edited it 50d ago (an edit is not a new posting)  


## Excluded by candidate policy

Grouped by rule, with the text that triggered each one.

**clearance-government**
- Icon — [Director, Information Technology and Systems](https://job-boards.greenhouse.io/iconcareers/jobs/5820804004): requires a clearance, federal-suitability or drug-screening process (security clearance)
- Icon — [Director of Construction, Military Construction (MILCON)](https://job-boards.greenhouse.io/iconcareers/jobs/6013514004): requires a clearance, federal-suitability or drug-screening process (security clearance)
- Icon — [Sr. Capture Specialist I, ICON Prime](https://job-boards.greenhouse.io/iconcareers/jobs/6123677004): requires a clearance, federal-suitability or drug-screening process (Security Clearance)
- Machinify — [Sr. Healthcare Reclamation Analyst](https://job-boards.greenhouse.io/machinifyinc/jobs/4415507009): requires a clearance, federal-suitability or drug-screening process (drug screening)
- Snorkel Ai — [Applied AI Engineer, Federal - Top Secret Clearance](https://job-boards.greenhouse.io/snorkelai/jobs/5721276004): requires a clearance, federal-suitability or drug-screening process (Top Secret)
- Legion Intelligence — [Engineering Manager DevOps/DevSecOps/Site Reliability/Deployment Engineering (D.C. Area)](https://job-boards.greenhouse.io/yurtsai/jobs/5157353007): requires a clearance, federal-suitability or drug-screening process (Top Secret)
- Legion Intelligence — [Federal Mission Success Manager (Engagement Manager/Program Manager/Product Manager/Customer Success/Account Manager) - Federal Intelligence Community (D.C. Area)](https://job-boards.greenhouse.io/yurtsai/jobs/5169935007): requires a clearance, federal-suitability or drug-screening process (TS/SCI)
- Legion Intelligence — [Forward Deployed Engineer (D.C Area)](https://job-boards.greenhouse.io/yurtsai/jobs/5193362007): requires a clearance, federal-suitability or drug-screening process (Top Secret)
- Legion Intelligence — [Solutions Engineer/Agentic AI Tools/Generative AI Protoyping/Proof of Concept (POC) - (Southeastern US Area)](https://job-boards.greenhouse.io/yurtsai/jobs/5190525007): requires a clearance, federal-suitability or drug-screening process (Top Secret)

**frontend-specialist**
- Grafana Labs — [Staff Frontend Engineer - Grafana DataViz \| Canada \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6194971004): role's primary identity is frontend engineering (Frontend Engineer)
- Grafana Labs — [Staff Frontend Engineer - Grafana DataViz \| US \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6194871004): role's primary identity is frontend engineering (Frontend Engineer)
- Machinify — [Sr/Staff Frontend Engineer \| Web Products](https://job-boards.greenhouse.io/machinifyinc/jobs/4110559009): role's primary identity is frontend engineering (Frontend Engineer)
- Mozilla — [Contract Staff Front End Engineer (Web Conference/Screen Sharing)](https://job-boards.greenhouse.io/mozilla/jobs/8223350): role's primary identity is frontend engineering (Front End Engineer)

**location-eligibility**
- Axiomatic Ai — [AI Research Scientist - Scientific Reasoning](https://job-boards.eu.greenhouse.io/axiomaticai/jobs/4844948101): the stated worksite is outside the US and no US-remote eligibility is stated
- Axiomatic Ai — [Internship – Research Intern (AI for Scientific Reasoning)](https://job-boards.eu.greenhouse.io/axiomaticai/jobs/4845060101): the stated worksite is outside the US and no US-remote eligibility is stated
- Grafana Labs — [Commercial Account Executive, Acquisition \| Remote \| Netherlands](https://job-boards.greenhouse.io/grafanalabs/jobs/6116452004): the stated worksite is outside the US and no US-remote eligibility is stated
- Grafana Labs — [Commercial Account Executive, Acquisition \| Remote \| Sweden](https://job-boards.greenhouse.io/grafanalabs/jobs/6116460004): the stated worksite is outside the US and no US-remote eligibility is stated
- Grafana Labs — [Demand Generation Program Manager \| Canada \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6115636004): location is outside the US with no US-remote eligibility stated
- Grafana Labs — [Engineering Manager - Observability \| Germany \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6202561004): the stated worksite is outside the US and no US-remote eligibility is stated
- Grafana Labs — [Engineering Manager - Observability \| Ireland \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6202563004): the stated worksite is outside the US and no US-remote eligibility is stated
- Grafana Labs — [Engineering Manager - Observability \| Spain \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6202560004): the stated worksite is outside the US and no US-remote eligibility is stated
- Grafana Labs — [Engineering Manager - Observability \| Sweden \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6202558004): the stated worksite is outside the US and no US-remote eligibility is stated
- Grafana Labs — [Engineering Manager - Observability \| UK \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6202562004): location is outside the US with no US-remote eligibility stated
- Grafana Labs — [Enterprise Account Executive, Acquisition - META \| Remote \| Spain](https://job-boards.greenhouse.io/grafanalabs/jobs/6116471004): the stated worksite is outside the US and no US-remote eligibility is stated
- Grafana Labs — [Enterprise Account Executive, Acquisition \| Remote \| Sweden](https://job-boards.greenhouse.io/grafanalabs/jobs/6116462004): the stated worksite is outside the US and no US-remote eligibility is stated
- Grafana Labs — [Enterprise Account Executive, Growth \| Remote \| Netherlands](https://job-boards.greenhouse.io/grafanalabs/jobs/6191321004): the stated worksite is outside the US and no US-remote eligibility is stated
- Grafana Labs — [Incentive Compensation Systems Manager \| Canada \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6150635004): location is outside the US with no US-remote eligibility stated
- Grafana Labs — [Manager, Solutions Engineering \| NorBen \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6121600004): the stated worksite is outside the US and no US-remote eligibility is stated
- and 153 more under this rule (all in JSON)

**location-residency**
- Future — [Health Coach](https://job-boards.greenhouse.io/future/jobs/4727680005): the posting limits employment to residents of AZ, FL, GA, NC, OH, SC, TN, TX, UT, which does not include New Hampshire; a remote label does not make this role available from New Hampshire
- Machinify — [DME Supervisor](https://job-boards.greenhouse.io/machinifyinc/jobs/4380681009): the posting limits employment to residents of MS, which does not include New Hampshire; a remote label does not make this role available from New Hampshire
- Machinify — [Medical Review Nurse, Clinical Appeals Auditor](https://job-boards.greenhouse.io/machinifyinc/jobs/4401791009): the posting limits employment to residents of MS, which does not include New Hampshire; a remote label does not make this role available from New Hampshire

**sales-ownership**
- Cargomatic — [Customer Success Manager](https://job-boards.greenhouse.io/cargomatic/jobs/4967355008): title is a sales role (Customer Success Manager)
- Cargomatic — [Customer Success Manager](https://job-boards.greenhouse.io/cargomatic/jobs/4967348008): title is a sales role (Customer Success Manager)
- Cargomatic — [SMB Sales Manager — Drayage Transportation](https://job-boards.greenhouse.io/cargomatic/jobs/5190848008): role owns sales outcomes (pipeline generation); 2 such duties stated
- Grafana Labs — [Commercial Account Executive, Acquisition \| Remote \| Italy](https://job-boards.greenhouse.io/grafanalabs/jobs/6116479004): title is a sales role (Account Executive)
- Grafana Labs — [Commercial Account Executive, Acquisition \| Remote \| Netherlands](https://job-boards.greenhouse.io/grafanalabs/jobs/6116452004): title is a sales role (Account Executive)
- Grafana Labs — [Commercial Account Executive, Acquisition \| Remote \| Sweden](https://job-boards.greenhouse.io/grafanalabs/jobs/6116460004): title is a sales role (Account Executive)
- Grafana Labs — [Commercial Account Executive, Acquisition \| Switzerland \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6121134004): title is a sales role (Account Executive)
- Grafana Labs — [Enterprise Account Executive, Acquisition \| FL \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6131159004): title is a sales role (Account Executive)
- Grafana Labs — [Enterprise Account Executive, Acquisition - META \| Remote \| Spain](https://job-boards.greenhouse.io/grafanalabs/jobs/6116471004): title is a sales role (Account Executive)
- Grafana Labs — [Enterprise Account Executive, Acquisition \| Remote \| Italy](https://job-boards.greenhouse.io/grafanalabs/jobs/6191319004): title is a sales role (Account Executive)
- Grafana Labs — [Enterprise Account Executive, Acquisition \| Remote \| Sweden](https://job-boards.greenhouse.io/grafanalabs/jobs/6116462004): title is a sales role (Account Executive)
- Grafana Labs — [Enterprise Account Executive, Acquisition \| Switzerland \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/6121146004): title is a sales role (Account Executive)
- Grafana Labs — [Enterprise Account Executive, Growth \| Remote \| Netherlands](https://job-boards.greenhouse.io/grafanalabs/jobs/6191321004): title is a sales role (Account Executive)
- Grafana Labs — [Enterprise Account Executive, Growth \| Southeast \| Remote](https://job-boards.greenhouse.io/grafanalabs/jobs/5755394004): title is a sales role (Account Executive)
- Grafana Labs — [Future Sales Openings: Account Executive, US \|Remote\|](https://job-boards.greenhouse.io/grafanalabs/jobs/5823504004): title is a sales role (Account Executive)
- and 59 more under this rule (all in JSON)

## Newly observed postings

- [Senior Software Engineer](https://job-boards.greenhouse.io/mozilla/jobs/8204384) at Mozilla: first observed [snapshot=250ddd8fe44344b3b9c98125f29b81a3, event=2026-09-25:greenhouse:mozilla#8204384:first-seen]
- [Senior Software Engineer](https://job-boards.greenhouse.io/mozilla/jobs/8209734) at Mozilla: first observed [snapshot=250ddd8fe44344b3b9c98125f29b81a3, event=2026-09-25:greenhouse:mozilla#8209734:first-seen]

## Duplicates and distinct requisitions

- Merged as the same posting seen more than once: 0
- Cross-linked as possibly the same, both kept for review: 0
- Deliberately NOT merged because they are distinct openings: 1

## Newly discovered sources

- QUEUED_UNSUPPORTED: 218 (1Password, A.Team, AE Perkins, AJC Group, AWeber, Acceleration Partners, Ace IT Careers, Actian, …)

## Source attribution

- Jobs via Himalayas (himalayas.app) — linked back to the Himalayas posting URL.
- Jobs via Jobicy (jobicy.com) — apply links point at the original Jobicy posting URL.
- Jobs via Remote OK (remoteok.com) — linked back to the Remote OK posting URL.
- Jobs via Remotive (remotive.com) — linked back to the Remotive posting URL.
