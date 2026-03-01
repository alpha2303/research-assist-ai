# Author Notes

**Updated:** 2026-03-01

**By:** Rahul Pavithran (Not AI-assisted)

Those who have closely interacted with me on the topic of AI would know that while I am a huge fanatic of AI as a concept, I mildly lean on the side of skepticism when it comes to Transformer-based models. Don't get me wrong, transformers, and specifically the Attention mechanism, are a revolution in sequential data generation that have overcome the limitations of predecessors like RNNs and LSTMs.

However, by design, transformers are brute-force machines, and as a result, have physical limitations we will eventually be unable to avoid. Will World Models be the answer? Will a completely new LLM paradigm reveal itself? The honest answer is, only time will tell, and at the speed of innovation that is happening in the current AI landscape, we may reach there sooner than expected.

So why this experiment?

At the moment, there's been a lot of buzz on the improved maturity of the latest AI models for autonomous software development that I had to give it a try. I've used Claude in the past year, usually for more basic coding tasks and have been happy with the results, so I felt it was the right time to explore building a project from scratch using the latest Claude models.

I've been meaning to build a RAG app to aggregate research papers and converse with them for a while. My previous attempt was to have the app completely written in Rust, but progress was stalled due to my own skill issues with type wrangling (AWS Rust SDK uses some weird internal types that caused conflicts with the rest of my code).

This project was created as an experiment to explore the nuances of AI-assisted software development in the big 2026. As part of this experiment, the AI agent would be handling the E2E implementation while I only involved on the decision-making and alignment when required.

## Timeline

- **Day 1: Software Design and Brainstorming**
  - First step was to manually prepare a requirement specification file, which contained high to medium level design idea of the project.
  - With the spec file ready, I initiated a planning session with Claude (Opus 4.6) via GitHub Copilot to analyse requirements. (All points below are from memory and may not be accurate.)
    - Role: Senior Full-stack AI Engineer with decades of experience in enterprise-level microservices and AI based application.
    - Instructions:
      - Prepare a design plan based on the information provided in the requirements-specification.md file. Do not start any implementation tasks.
      - Save all documentation to ./design/phase-1
      - Confirm any design decision with me prior to documenting them in the design doc.
      - Call out any concerns that may come up during planning.
  - Opus 4.6 was quite good when it came to designing and planning the system.
    - I went back and forth on many of the design decisions, with Opus 4.6 explaining why it opted for one approach instead of another. I would make the final call if the options are equally viable.
    - Unlike older models, Opus 4.6 was not hesitant to correct me when I made a statement backed by a wrong assumption, which is good as this is a learning experience for us both.
  - Once the design doc was completed, I asked Opus 4.6 to prepare the implementation plan using the design doc as reference. I also gave it a list of development practices to follow and asked it to document it in a separate markdown file for reference.
  - Based on our discussion, following documentation in the design/phase-1 folder were prepared:
    - design-doc.md
    - implementation-plan.md
    - implementation-standards.md
  - Looking back, this one day of planning and documentation actually formed the core effort and streamlined the implementation part.
- **Day 2: Implementation Phase 1-3**
  - Performed initially using Claude Sonnet 4.5 as I wanted to save on my Copilot credits
  - If any issues were encountered during implementation or testing, I requested Claude to document them in implementation-issues.md
  - Claude Sonnet 4.5 stopped working citing rate limiting due to request limit being reached. This may be due to some request limit at the model level set between Copilot and Anthropic. I realised Copilot also gave me access to Sonnet 4.6 with the same credit multiplier as Sonnet 4.5 (x1), so shifted to Sonnet 4.6 for rest of the work.
  - Spent a lot of time manually fixing the backend docker image, which was facing virtual environment issues due to uv as Sonnet couldn't figure it out. Can't blame it as uv brought in some deviations from the expected behavior.
  - At this point the frontend was also not rendering the CSS correctly, so opted to take a break and re-visit.
- **Day 3: Implementation Phase 4-5**
  - Continued with Sonnet 4.6 for this task.
  - Fixed the CSS issue in the frontend, finally started seeing responsive buttons.
  - Requested Sonnet to start writing unit tests for the backend for all the compoenents created so far, which was where most of the effort went into.
  - Continued with RAG pipeline implementation and testing, was finally able to run the backend system via docker. Document upload and Chat was not working as expected.
- **Day 4: Implementation Phase 6-7 and testing**
  - Rest of the work was completed using Claude Opus 4.6 (had Copilot credits to burn before allowance reset).
  - Fixed issue with document upload and chat interface, which was caused due to deviations in logic initially implemented by Sonnet 4.5.
  - Opus 4.6 retained context of the project much better compared to Sonnet 4.5. I believe Sonnet 4.6 would have done a decent job had it handled the implementation from the beginning.
  - I would periodically ask it to audit the code (logical, linting and type errors) and make fixes to ensure code performed as per the implementation plan.
  - Lot of last minute fixes popped up that stemmed from implementation change made later that were out of sync with the data models. There were also some design debt that had to be corrected, which was taken care of by Opus 4.6.
  - Decided to have additional scope - UI dark mode with toggle. Implementation completed by Opus 4.6.
  - Application can run locally without issues, requires AWS credentials set up locally for Bedrock access.

## Process Enhancement

If I could do this project from the beginning, here's what I'd try differently:

- **Git Setup:**
  - For this project, I did not concern myself with the git setup.
  - Going forward, have the git repo set up prior to implementation and have the agent make incremental commits to the remote repo (via GitHub MCP maybe?)
- **Experiment with Behaviour-Driven Design:**
  - I added unit tests into the implementation much later than I should have. Next time, I'd want to experiment having the agent approach development with a BDD setup:
    - Prepare unit tests based on current understanding of a component's designed behaviour.
    - Implement the component as per implementation plan.
    - Run unit tests and make corrections as needed.
- **Copilot Context Management:**
  - Copilot in VSCode currently has a context memory of 128k tokens, which can fill up pretty quickly as the agent iterated over long development tasks.
  - While context summarization does happen, it is not very frequent and I have experienced >80% memory utilization multiple times during the development session, which can affect response quality.
  - To handle this:
    - At 75% utilization, I would request the agent to generate a summary of work including:
      - Role used by the agent in the working project.
      - Tasks completed.
      - Tasks pending.
    - Once summary is generated, I would start a new copilot chat with the following prompt:
      ```
      "Based on the summary of work provided, continue the development work for this project. All context regarding this project is available in the `./.design/phase-1` folder:
      <INSERT SUMMARY HERE>
      ```
    - This is where having a maintained context files shines - your in-chat prompts can be brief and precise.
    - I'd need to experiment more on automating this additional summarization step.
- **Agent Instructions:**
  - For this project, all agent prompts were directly fed into the chat. However, I'd prefer having the agent instructions set up in dedicated files that Copilot supports, as documented [here](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions?tool=vscode).
  - During the implementation phases, there were some actions that I asked Claude to follow during its iterations to prevent it from deviating from the implementation plan. It would be better to have these actions set up in the beginning:
    - When using file paths in terminal execution, always use absolute paths to keep commands independent from current working directory.
    - Unit Tests:
      - For each component, ensure that unit tests are create with external services properly mocked.
      - Unit tests should not perform any operations against live environment.
      - Integration tests, or any test interacting with live environment need to be maintained in a separate directory to allow exclusion during test execution.
    - At the end of each task:
      - Run unit tests for all components and resolve any test failures.
      - Perform checks for linting and typing errors and resolve detected issues.
      - Document issues faced during task implementation, along with root cause and description of solution implemented.
    - At the end of each phase, perform an code audit to ensure all code matches the implementation plan for all tasks completed so far.
    - `<ADD MORE STEPS>`
- **Local deployment with On-system Models:**
    - Thanks to docker compose, the application is capable of running standalone as a local system. That's when I realised this was pretty good as a standalone local service.
    - Application still depends on AWS Bedrock for embedding and conversational models.
    - This may be a good use case for small language models that can operate locally on desktop systems, but additional research is required.