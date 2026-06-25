**

[Coding Challenges](/)

# [Coding Challenges](/)

SubscribeSign in

# Coding Challenge #123 - Database Driven LLM Wiki

### This challenge is to build your own database powered LLM Wiki.

[John Crickett's avatar](https://substack.com/@johncrickett)

[John Crickett](https://substack.com/@johncrickett)

Jun 06, 2026

18

4

1

Share

*Hi, this is John with this week’s Coding Challenge.*

🙏 *Thank you for being a subscriber, I’m honoured to have you as a reader. 🎉*

*If there is a Coding Challenge you’d like to see, please let me know by replying to this email📧*

## Coding Challenge #123 - Database Driven LLM Wiki

This challenge is to build your own personal knowledge base tool - a system where an LLM agent reads your curated sources, extracts the key information, and builds you a living, interlinked wiki that grows smarter with everything you add.

Most people’s experience with LLMs and documents is RAG: upload files, ask questions, get answers stitched together from retrieved chunks. It works, but the LLM rediscovers knowledge from scratch every time. Ask a subtle question that spans five documents, and the system has to find and piece together fragments it’s seen before. Nothing accumulates.

LLM Wiki takes a different approach. Instead of just retrieving from raw documents at query time, an LLM agent incrementally builds and maintains a persistent wiki - a structured collection of markdown files that sits between you and your sources. When you add a new source, the agent reads it, extracts key information, and integrates it into the existing wiki: updating entity pages, revising topic summaries, noting where new data contradicts old claims, strengthening or challenging the evolving synthesis. The knowledge is compiled once and then kept current, not re-derived on every query.

You’re in charge of sourcing, exploration, and asking good questions. The LLM does all the grunt work: summarising, cross-referencing, filing, and the bookkeeping that makes a knowledge base actually useful over time.

This challenge is inspired by Andrej Karpathy’s [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) concept - a pattern for building personal knowledge bases using LLMs. Karpathy describes the idea in the abstract; our job is to build a working implementation.

Under the hood, the system stores vector embeddings and full-text indexes for every wiki page in [Oracle AI Database](https://fandf.co/4x9nXJd). When you ask a question, it finds relevant pages using hybrid search, and an LLM synthesises an answer with citations. The agentic behaviour - ingestion workflows, multi-step querying, lint passes - is orchestrated using LangGraph’s state machine model, while LangChain handles the LLM integration. It’s a practical introduction to agent-based knowledge management, vector search, full-text search, and building tools that genuinely compound in value over time.

## The Challenge - Building LLM Wiki

You’re going to build a personal knowledge base that an LLM agent writes and maintains for you. It starts by ingesting source documents into a wiki of markdown files, then lets you query it through a web interface or CLI chat. Step by step you’ll add wiki scaffolding, source ingestion, index and log management, vector storage, semantic retrieval, project management, linting, and a user interface. By the end, you’ll have a tool that genuinely helps you build and navigate a growing body of knowledge.

### Step Zero

In this introductory step you’re going to set your environment up ready to begin developing and testing your solution.

You’ll need to make a few decisions and get some infrastructure running:

1. Set up your vector and full-text database.** You’ll need [Oracle Database 26ai](https://fandf.co/4x9nXJd) running in a local Docker container. Pull the `container-registry.oracle.com/database/free:latest` image, start the container, and set a password for the admin account. You can find full setup instructions in the [Oracle Database Free Get Started guide](https://fandf.co/4nSWzL1). Once the container is running, connect using a SQL client and verify you can create a table. Store all credentials in an environment file, not hardcoded anywhere.

```
`docker pull container-registry.oracle.com/database/free:latest
docker run -d -p 1521:1521 -e ORACLE_PWD= container-registry.oracle.com/database/free:latest`
```

1. **Choose your embedding model.** You need a text embedding model that captures semantic meaning. Nomic’s `nomic-embed-text` is open source (Apache 2.0) and runs locally on CPU. It produces 768-dimensional vectors. Install it via Hugging Face: `pip install sentence-transformers` and load it as `nomic-ai/nomic-embed-text-v2-moe`. Any general-purpose embedding model with reasonable semantic quality will work - the key requirement is that it can capture the meaning of wiki pages well enough to find relevant ones for a given query.
2. **Set up your LLM provider.** You’ll need a language model for writing wiki pages, summarising sources, and answering questions. Any provider with a chat API will work - Anthropic, OpenAI, Google, Mistral, or a local model via Ollama. The model needs to be capable enough to write coherent markdown and extract structured information from source documents.
3. **Set up LangChain and LangGraph.** You’ll use LangChain for LLM integration and LangGraph for orchestrating the agent’s workflows. Install both: `pip install langchain langgraph`. LangChain handles the plumbing of prompting and response parsing. LangGraph handles the agentic flows - the multi-step processes of ingesting a source (read, extract, write summaries, update pages, update index, log), answering queries (search, read pages, synthesise), and running lint passes.
4. **Pick a topic for your first wiki.** Choose a domain you’re genuinely curious about and gather 50-100 source documents - articles, papers, blog posts - about it. Save them as markdown or plain text files. This will be your test corpus. Pick something where the articles naturally reference the same entities and concepts, so there are connections for your wiki to surface. A technical topic works well (e.g. database internals, a specific ML technique, a programming language), but any domain with depth will do - history, cooking, fitness, whatever interests you.

**Testing:** Verify your Oracle Database container is running and you can connect to it. Load your embedding model and generate a test embedding to confirm it returns a vector of 768 dimensions. Make a test call to your LLM API to confirm it returns a valid response. Verify your environment file is being read correctly and no credentials are in your source code.

### Step 1

In this step your goal is to build the wiki scaffolding - the system that creates and manages the directory of markdown files that will become your knowledge base.

The wiki lives on disk as a directory of markdown files. Before you can ingest sources or answer questions, you need the infrastructure to create pages, write content to them, and link them together. Think of this as the file system layer of your knowledge base.

Start by defining what a new wiki looks like on disk. When you create a wiki, the system should scaffold a directory structure with subdirectories for different page types: summaries for source summaries, entities for pages about people/companies/concepts, topics for overview pages, and a raw directory for the original source files. Alongside the directories, create a schema file (call it [SCHEMA.md](http://schema.md/)) that defines the conventions for this wiki - what the directories are for, what naming conventions to use, what frontmatter fields pages should have, and how cross-references should be formatted.

Pages should carry YAML frontmatter at the top with metadata: title, type (entity, concept, summary, overview), date created, date updated, tags, and a list of sources the page draws from. The frontmatter makes pages queryable later and lets tools like Obsidian’s Dataview plugin generate dynamic views.

Cross-references between pages should use standard markdown links or wikilinks (`[[Page Name]]`). Which style you use is up to you, but the schema file should record the convention so the agent can be consistent. When one page references another, the agent should be able to follow that link, read the target page, and update both sides of the relationship.

Build a simple CLI that lets you create a new wiki, list existing wikis, and inspect a wiki’s structure - how many pages it has, what directories exist, and what the schema says. This CLI is just for development and testing; you’ll replace it with a proper interface later.

**Testing:**

- Create a wiki. Verify the directory structure and [SCHEMA.md](http://schema.md/) file were created on disk.
- Manually add a few test pages with frontmatter and cross-references. Verify the frontmatter parses correctly and links resolve to the expected paths.
- Create a second wiki with a different schema configuration (different frontmatter fields, different link style). Verify both wikis coexist and respect their own conventions.
- List your wikis and verify both appear.
- Delete a wiki directory manually and verify the listing correctly reflects its absence.

### Step 2

In this step your goal is to build the source ingestion pipeline - the agent workflow that reads a source document and integrates its knowledge into the wiki.

This is the heart of the system. When you drop a new source into the raw directory and tell the agent to ingest it, a multi-step workflow begins. The agent reads the source, extracts key information, discusses the takeaways with you (in interactive mode), and then updates the wiki across multiple pages.

Model the ingestion workflow as a graph in LangGraph. Each node handles one concern: read the source, extract entities and concepts, identify claims and key information, write a summary page in the summaries directory, update or create entity pages for each entity found, update or create concept pages for each concept, revise topic overview pages, flag contradictions with existing content, update the index, and append an entry to the log. A single source might touch 10-15 wiki pages.

The agent should be able to detect contradictions. When a new source makes a claim that conflicts with something already in the wiki, the agent should note the discrepancy on the relevant page rather than silently overwriting or ignoring it. The user should be able to see where sources disagree and make their own judgement.

The agent should also identify gaps - entities or concepts referenced in the source that don’t yet have pages - and create stub pages or flag them for later attention.

Think carefully about how you prompt the LLM for each of these tasks. The quality of the wiki depends entirely on the quality of the extraction and synthesis. You’ll likely need different prompts for different page types: a summary page prompt, an entity page prompt, a concept page prompt, and so on. The schema file you built in Step 1 should guide these prompts.

The original source file should go into the raw directory and never be modified. The agent reads from it but never writes to it. This is your source of truth.

**Testing:**

- Ingest a single source document (a short article, 500-1000 words) into a test wiki. Verify the agent creates a summary page that captures the key points without hallucinating facts not in the source.
- Verify the agent creates or updates entity pages for the key people, companies, or concepts mentioned in the source.
- Verify the agent creates or updates topic overview pages that connect this source to existing knowledge (if the wiki already has content).
- Ingest a second source on the same topic that contradicts something in the first source. Verify the agent flags the contradiction on the relevant page.
- Check the wiki directory after ingestion. It should contain new or updated files in the summaries, entities, and topics directories. The raw directory should contain the original source unchanged.
- Ingest a source that mentions an entity not yet in the wiki. Verify the agent creates a stub page or flags the gap.

### Step 3

In this step your goal is to build the index and log - two special files that help the agent (and you) navigate the wiki as it grows.

The index (`index.md`) is content-oriented. It’s a catalogue of every page in the wiki, organised by category: entities, concepts, sources, overviews. Each entry includes a link to the page, a one-line summary, and optionally metadata like creation date and the number of sources that feed into it. When the agent needs to answer a query, it reads the index first to find candidate pages, then drills into the most relevant ones. This approach works well at moderate scale (hundreds of pages) and avoids the need for embedding-based RAG infrastructure at the browsing level.

The log (`log.md`) is chronological. It’s an append-only record of everything that happened: ingests, queries, lint passes, schema changes. Each entry starts with a consistent prefix format: `## [YYYY-MM-DD] type | Description`. This makes the log parseable with simple command-line tools - `grep "^## \\\\[" log.md | tail -5` gives you the last five entries.

The key design decision is that the agent owns both files. Every ingestion should update the index with new pages and revised summaries. Every operation should append to the log. The agent should read the index at the start of every query to know what’s available. The agent should read the log at the start of every session to know what’s been done recently.

Build the index and log maintenance into your LangGraph workflows from Step 2. After the agent finishes writing wiki pages for an ingestion, it should update the index and append to the log as the final nodes in the graph. If an ingestion fails partway through, the log should record the failure.

**Testing:**

- Ingest a source and verify the index is updated with entries for the new summary page, entity pages, and concept pages. Each entry should have a link and a one-line description.
- Ingest a second source and verify the index reflects both sources, with shared entity pages showing updated descriptions.
- Check the log after several ingestions. Verify each entry has the correct format (`## [YYYY-MM-DD] ingest | Title`) and appears in chronological order.
- Run `grep "^## \\\\[" log.md` and verify you get a clean chronological listing.
- Manually delete a wiki page. Ingest a new source and verify the index accounts for the missing page (removes the stale entry rather than leaving dead links).

### Step 4

In this step your goal is to add semantic search over your wiki pages using vector embeddings and full-text search stored in [Oracle AI Database](https://fandf.co/4x9nXJd).

So far the agent navigates the wiki by reading the index and following links. That works at moderate scale, but as your wiki grows to hundreds of pages, you’ll want semantic search - finding pages by meaning, not just by browsing the catalogue.

Take every wiki page (excluding the index and log themselves, and excluding raw source files), generate a vector embedding for it using your embedding model, and store the embedding alongside the page’s path, title, type, tags, and a snippet or summary in Oracle Database. The metadata fields should all be stored and indexed so you can filter by type (”only entity pages”) or by tag.

Create a vector index on the embedding column for fast cosine similarity search. Also create an Oracle Text full-text index on the page content (or at minimum on the title and summary fields). Vector search finds semantically related pages even when the words don’t match. Full-text search catches exact names, technical terms, and phrases that vector search might rank lower. Together they give you robust retrieval.

Think about when embeddings should be generated. Every time the agent creates or updates a page during ingestion, the new or revised page needs to be re-embedded and stored. Pages that weren’t touched by an ingestion should keep their existing embeddings. You’ll need to track which pages changed so you only re-embed those.

Also think about what you embed. You could embed the full page text, but long pages might dilute the semantic signal. You could embed a summary or the first N paragraphs. You could embed both the title and the body separately and combine scores. Experiment and find what works for your test corpus - different approaches suit different types of content.

**Testing:**

- Run the full pipeline against your test wiki: parse all pages, generate embeddings, store in Oracle Database. Verify that the number of stored embeddings matches the number of wiki pages.
- Query Oracle Database directly to inspect a few stored entries. Verify each contains the embedding vector, page path, title, type, and tags.
- Verify that both the vector index and the full-text index have been created.
- Update a page (by ingesting a new source that modifies an existing entity page). Verify only the changed page is re-embedded; unchanged pages keep their existing embeddings.
- Search for a page by a concept it discusses (not by its exact title). Verify vector search returns it even though the words don’t match.
- Search for an exact technical term or person’s name. Verify full-text search catches it with high confidence.

### Step 5

In this step your goal is to build the query system - the agent workflow that answers your questions by searching the wiki and synthesising a response.

Now that you have a searchable wiki, you need the agent to put it to use. When you ask a question, the agent should follow a multi-step process: read the index to identify candidate pages, search for semantically relevant pages using the hybrid search you built in Step 4, read the most relevant pages in full, and synthesise an answer with citations to specific pages and sections.

Model the query workflow as a LangGraph graph. The nodes might include: read index, hybrid search, read candidate pages, and synthesise answer. If the agent finds gaps - the question touches on something the wiki doesn’t cover well - it should say so honestly rather than speculating.

The system should support different answer formats depending on the question. A comparison between two concepts might be best as a table. A timeline of events might be best as a chronological list. A straightforward explanation might be best as prose. Give the LLM the flexibility to choose the format, and provide guidance in your prompts.

An important capability: the system should offer to file good answers back into the wiki as new pages. When you ask a question that generates a useful analysis, comparison, or synthesis, the agent should ask if you want to save it. If you do, it writes the answer as a new wiki page, adds it to the index, logs it, and embeds it. This way your explorations compound in the knowledge base just like ingested sources do.

Support follow-up questions within a session. If you ask “tell me about X” and then “what about Y?”, the agent should understand from context that Y relates to the broader topic X is part of. LangGraph’s state carries conversation context forward between queries.

**Testing:**

- Ask a question about something well-covered in your wiki. The answer should be accurate, cite specific pages, and not hallucinate facts not in the wiki.
- Ask the same question with different phrasing. Verify you get a similar answer - semantic search should match by meaning, not exact wording.
- Ask a question that spans two or more wiki pages. Verify the agent reads multiple pages and synthesises an answer that connects them.
- Ask a follow-up question without re-stating the topic. Verify the agent maintains context from the previous exchange.
- Ask a question about something not covered in your wiki. Verify the agent honestly reports the gap rather than making things up.
- Ask the agent to save an answer as a wiki page. Verify the page is created on disk, added to the index, logged, and embedded in Oracle Database.
- Ask a comparison question (”what’s the difference between X and Y?”). Verify the answer uses an appropriate format (table, side-by-side, etc.).

### Step 6

In this step your goal is to add wiki project management so you can maintain separate knowledge bases for different topics.

A single wiki is useful, but you’ll likely want separate knowledge bases for different areas of your life - one for your research topic, one for book notes, one for health and fitness, one for career learning. Each should be isolated, with its own set of pages, its own embeddings, and its own agent memory.

Add support for named wiki projects. Store project metadata - name, creation date, last ingestion timestamp, page count, source count - in [Oracle AI Database](https://fandf.co/4x9nXJd). Each project’s embeddings and metadata should be isolated so that searches against one wiki never return pages from another.

The user should be able to create a new wiki project, list existing projects, and select which project to work with. When the user starts the system, they should be able to specify a project name and immediately pick up where they left off.

All wiki data should persist between runs. The markdown files live on disk in their project directories. The embeddings and metadata live in [Oracle AI Database](https://fandf.co/4x9nXJd). When the user comes back and selects a project, everything should be exactly as they left it - the same pages, the same index, the same log, the same search capability.

**Testing:**

- Create two wikis on different topics, each with a small set of source documents. Ingest sources into both.
- Query one wiki and verify results come only from that wiki, not the other.
- List your wikis and verify both appear with correct names and metadata (page count, last ingestion time).
- Query the project metadata directly in Oracle Database and verify it matches what the system reports.
- Stop and restart your system. Verify all wiki data is intact and queryable for both projects.
- Add a new source to an existing wiki and re-run ingestion. Verify only new or changed pages are re-embedded; unchanged pages preserve their existing embeddings.

### Step 7

In this step your goal is to build a linting system that health-checks your wiki and helps it stay consistent as it grows.

As your wiki accumulates pages and sources, inconsistencies creep in. A page makes a claim that a newer source contradicts, but the older page was never updated. A concept is discussed across five pages but never got its own dedicated page. A page references another that was renamed or deleted. Links only go one way. Gaps appear where you have half the story. Humans abandon wikis because this maintenance burden grows faster than the value. The agent can handle it.

Build a lint operation as a LangGraph workflow. The agent should walk the wiki systematically and check for: contradictions between pages (two pages make incompatible claims), stale claims (a page asserts something that a newer source has revised or disproven), orphan pages (pages with no inbound links from other wiki pages), missing pages (entities or concepts referenced but lacking their own page), broken cross-references (links that point to non-existent pages), and data gaps (areas where the wiki is thin and could benefit from additional sources).

The agent should report its findings as a prioritised list: critical issues first (contradictions, stale claims), then warnings (orphans, missing pages), then suggestions (gaps, possible new sources to look for). Each issue should include the specific pages involved and a suggested action.

The lint pass should also suggest new questions to investigate and new sources to look for - what’s missing from the wiki that would fill important gaps? This turns the lint operation from a bug-finding exercise into a research planning tool.

Make the lint operation interactive by default. The agent presents its findings, and you accept, reject, or modify each suggestion before any changes are made. The agent should not modify pages without confirmation unless you explicitly run in auto-fix mode.

**Testing:**

- Create a deliberate contradiction: write two entity pages that make incompatible claims about the same thing. Run lint and verify the agent detects and reports the contradiction, citing both pages.
- Create an orphan page: a page with no other pages linking to it. Run lint and verify it’s flagged.
- Reference a page that doesn’t exist (a broken wikilink). Run lint and verify the broken link is reported.
- Have a concept discussed across multiple pages but without its own dedicated page. Run lint and verify the agent suggests creating one.
- Accept a lint suggestion and verify the agent applies the fix correctly.
- Reject a lint suggestion and verify no changes are made.

### Step 8

In this step your goal is to build a user interface for your LLM Wiki, providing a chat-based interface for querying and managing your knowledge base.

Your wiki agent currently works through a development CLI. Now give it a proper interface. You have a choice: build a web interface (similar to the Code Sherpa challenge), a CLI chat interface, or both. The core requirements are the same regardless.

The interface should provide a chat panel for querying the wiki. The user types questions in natural language, and the agent responds with synthesised answers that cite specific wiki pages. Responses should render markdown so that tables, lists, and formatted text display clearly. Citations should be clickable links that open the referenced page.

The interface should support the full query workflow you built in Step 5: semantic search, multi-page synthesis, follow-up questions with context, different answer formats, and saving answers as new wiki pages.

Provide a way to browse the wiki structure: a page tree or list showing categories (entities, concepts, summaries, overviews) and the pages within each. This helps the user understand the shape of their knowledge base at a glance.

When the agent is processing a query, show a loading state so the user knows something is happening. LangGraph workflows can take several seconds as the agent reads the index, searches for pages, reads them, and synthesises an answer.

Build a separate CLI tool for source ingestion that doesn’t require launching the full interface. A user should be able to run something like `llm-wiki ingest my-research ./new-article.md` and have the agent process the source in the background, updating the wiki, index, log, and embeddings. This makes adding sources a quick, low-friction operation.

**Testing:**

- Launch the interface and verify you can access it.
- Select a wiki project and ask a question. Verify the response appears with markdown rendering and citations to wiki pages.
- Click a citation link. Verify it opens the referenced page.
- Ask a follow-up question and verify the system maintains context from the previous exchange.
- Browse the wiki structure through the interface. Verify it accurately reflects the pages on disk.
- Ask the agent to save an answer as a wiki page. Verify the page appears in the wiki structure immediately.
- Use the CLI ingestion tool to add a new source. Verify the wiki updates without needing to launch the full interface.
- Submit a query and verify a loading indicator appears while the agent processes it.

### Going Further

You’ve built a working personal knowledge base with an LLM agent that ingests sources, writes wiki pages, answers questions, and keeps everything consistent. Here are some ways to take it further:

- **Cloud database support:** Add an option to connect to a cloud-hosted [Oracle AI Database](https://fandf.co/4x9nXJd) instance instead of the local Docker container. Read the connection string from configuration.
- **Batch ingestion:** Add a batch mode that ingests multiple sources at once with less supervision. The agent processes each source, generates updates, and presents a summary of changes for your review rather than discussing each source individually.
- **Marp slide generation:** Add the ability to generate slide decks (using Marp format) from wiki content. This turns a collection of pages on a topic into a presentation with a single request.
- **Obsidian integration:** Build tighter integration with Obsidian. Watch the wiki directory for changes made through Obsidian and update embeddings automatically. Use Obsidian’s Dataview plugin with the frontmatter your agent already writes.
- **Multi-format sources:** Extend source ingestion to handle PDFs, web URLs (with scraping), and audio transcripts. The more formats you support, the more knowledge you can capture.

### Share Your Solutions!

If you think your solution is an example other developers can learn from please share it, put it on GitHub, GitLab or elsewhere. Then let me know via [Bluesky](https://bsky.app/profile/johncrickett.bsky.social) or [LinkedIn](https://www.linkedin.com/in/johncrickett/) or just post about it there and tag me. Alternately please add a link to it in the [Coding Challenges Shared Solutions](https://github.com/CodingChallengesFYI/SharedSolutions) Github repo

### Request for Feedback

I’m writing these challenges to help you develop your skills as a software engineer based on how I’ve approached my own personal learning and development. What works for me, might not be the best way for you - so if you have suggestions for how I can make these challenges more useful to you and others, please get in touch and let me know. All feedback is greatly appreciated.

You can reach me on [Bluesky](https://bsky.app/profile/johncrickett.bsky.social), [LinkedIn](https://www.linkedin.com/in/johncrickett/) or through [SubStack](https://codingchallenges.substack.com/)

Thanks and happy coding!

John

18

4

1

Share

Previous

#### Discussion about this post

CommentsRestacks

[Ahmed Moniem's avatar](https://substack.com/profile/326669388-ahmed-moniem?utm_source=comment)

[Ahmed Moniem](https://substack.com/profile/326669388-ahmed-moniem?utm_source=substack-feed-item)

[5d](https://codingchallenges.substack.com/p/coding-challenge-122-database-driven/comment/271500837)

Liked by John Crickett

For the 1st step, can we use postgress rather then oracle ?

Reply

Share

[1 reply by John Crickett](https://codingchallenges.substack.com/p/coding-challenge-122-database-driven/comment/271500837)

[Sawala's avatar](https://substack.com/profile/256078109-sawala?utm_source=comment)

[Sawala](https://substack.com/profile/256078109-sawala?utm_source=substack-feed-item)

[5d](https://codingchallenges.substack.com/p/coding-challenge-122-database-driven/comment/271497734)

Liked by John Crickett

123? 😅

Reply

Share

[1 reply by John Crickett](https://codingchallenges.substack.com/p/coding-challenge-122-database-driven/comment/271497734)

[2 more comments...](https://codingchallenges.substack.com/p/coding-challenge-122-database-driven/comments)

TopLatestDiscussions

No posts

### Ready for more?

© 2026 John Crickett · [Privacy](https://substack.com/privacy) ∙ [Terms](https://substack.com/tos) ∙ [Collection notice](https://substack.com/ccpa#personal-data-collected)

[Start your SubstackGet the app](https://substack.com/signup?utm_source=substack&utm_medium=web&utm_content=footer)

[Substack](https://substack.com) is the home for great culture