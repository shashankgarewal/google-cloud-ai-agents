# Agentic AI Projects on Google Cloud

This repository contains projects and certificates related to the Google Cloud GenAI Academy APAC Edition:

- **[guided-projects](./guided-projects)** — Built as part of the [Google Cloud Gen AI Academy APAC](https://vision.hack2skill.com/event/apac-genaiacademy) by Hack2skill in collaboration with Google, with workshops and challenges designed and led by Google Cloud engineers.
- **[self-projects](./self-projects)** — Independent explorations and experiments beyond the curriculum
- **[hackathon](./hackathon/smart_travel_journey_planner)** — Smart Travel Journey Planner, built for the GenAI Academy Cohort 1 Hackathon

## Certificates
- **Google Cloud GenAI Academy Cohort 1 Hackathon** — [Certificate of Participation](./certificates/Cohort%201%20Hackathon%20-%20Certificate%20of%20Participation.pdf) | ([Verify Online](https://certificate.hack2skill.com/claim/ef3d510bc44d25cb586d4b092efefae2eab7c238d4a149089b6a1fa6b1548c76))

## Key Learnings

### 1. When NOT to Use GenAI Agents (Insights from Hackathon Project)
During the development of the **[Smart Travel Journey Planner](./hackathon/smart_travel_journey_planner)**, a key architectural realization was identifying when *not* to rely on GenAI agents:
- **Latency Sensitivity**: Agentic routing and reasoning steps introduce latency overhead. If a task requires low-latency real-time responses (such as fetching or filtering schedules rapidly), direct traditional API calls or rule-based processing are far more suitable than querying LLMs.
- **API Call Volume**: As the scale of data (e.g., the number of train options) grows, letting an agent handle individual item evaluations causes API call counts and token consumption to spike dramatically. A hybrid approach (where programmatic logic filters and prepares data, and the agent only does the final high-level synthesis/recommendation) is much more cost-effective and scalable.

### 2. Time Management & Deadline Strategy (Codelab/Hackathon Experience)
A crucial lesson was learned from narrowly missing a codelab deadline by a few seconds:
- **Task Prioritization Under Pressure**: When racing against a deadline, instead of rigidly following a sequential checklist or getting stuck on a long-running bottleneck, adapt immediately.
- **Parallel Work & Context Switching**: If one task takes longer than expected, either focus on fully completing it if it's the core blocker, or switch to other independent sections of the project that aren't blocked, ensuring you submit a functional product rather than an unfinished sequence.

For local development setup and workflow, see [process.md](process.md).