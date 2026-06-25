# Architecture — LLM Wiki

Living architecture diagrams for this project. **Update this file at the end of each phase.**

**Last updated:** 2026-06-24 — Phase 7 complete (Steps 0–7); LangGraph lint; structural + LLM checks; interactive fixes  
**Companion doc:** [dev-notes.md](dev-notes.md)

---

## 1. System overview (Phases 0–7)

What exists today: full ingest → index/log → Oracle search → query agent → multi-wiki registry → **lint health-checks with interactive fixes**. Streamlit UI is Phase 8.

```mermaid
flowchart TB
    subgraph external [External services]
        OpenAI[OpenAI API]
        Ollama[Ollama local\nindex one-liners]
        Oracle[(Oracle DB 26ai\nwiki_pages + wiki_projects)]
    end

    subgraph dev [Developer]
        CLI[cli.py]
        Scraper[scripts/scrape_corpus.py]
        VerifyLint[scripts/verify_lint.py]
    end

    subgraph app [llm_wiki package]
        WikiMod[wiki/\nwiki_manager\nfrontmatter\nschema_generator]
        Ingest[ingestion/\nLangGraph pipeline]
        IndexLog[index_log/\nindex log readers]
        DB[db/\nconnection schema]
        EmbedMod[embeddings/\nNomic sync]
        Search[search/\nvector FTS hybrid]
        QueryMod[query/\nLangGraph Q&A]
        ProjectsMod[projects/\nregistry + stats]
        LintMod[lint/\nLangGraph + fixes]
        Prompts[prompts/*.md]
        Config[config/.env]
    end

    subgraph data [On disk + DB]
        Corpus[corpus/raw/\nstaging articles]
        Wikis[wikis/*/\nraw summaries entities topics\nSCHEMA index log]
    end

    Scraper --> Corpus
    CLI --> WikiMod
    CLI --> Ingest
    CLI --> IndexLog
    CLI --> DB
    CLI --> EmbedMod
    CLI --> Search
    CLI --> QueryMod
    CLI --> ProjectsMod
    CLI --> LintMod
    VerifyLint --> LintMod
    WikiMod --> Wikis
    Ingest --> WikiMod
    Ingest --> IndexLog
    Ingest --> EmbedMod
    Ingest --> Prompts
    Ingest --> OpenAI
    Ingest --> Ollama
    WikiMod --> OpenAI
    IndexLog --> Wikis
    IndexLog --> Ollama
    EmbedMod --> Wikis
    EmbedMod --> Oracle
    Search --> Oracle
    QueryMod --> IndexLog
    QueryMod --> Search
    QueryMod --> OpenAI
    QueryMod --> WikiMod
    QueryMod --> EmbedMod
    ProjectsMod --> Oracle
    ProjectsMod --> Wikis
    LintMod --> WikiMod
    LintMod --> IndexLog
    LintMod --> EmbedMod
    LintMod --> OpenAI
    LintMod --> ProjectsMod
    DB --> Oracle
    Config --> Ingest
    Config --> WikiMod
    Config --> IndexLog
    Config --> DB
    Config --> QueryMod
    Config --> LintMod
    Corpus -->|ingest via CLI| Ingest
    Ingest -->|copy to raw/| Wikis
    QueryMod -->|optional save| Wikis
    LintMod -->|optional fix| Wikis
    UI[Phase 8\nStreamlit UI] -.-> QueryMod
    UI -.-> LintMod
```

**Solid lines** = implemented (Phases 0–7). **Dotted** = planned (Phase 8 UI only).

---

## 2. Phase roadmap (challenge steps)

```mermaid
flowchart LR
    P0[Phase 0\nEnvironment] --> P1[Phase 1\nWiki scaffold]
    P1 --> P2[Phase 2\nIngestion]
    P2 --> P3[Phase 3\nIndex and log]
    P3 --> P4[Phase 4\nOracle vectors]
    P4 --> P5[Phase 5\nQuery]
    P5 --> P6[Phase 6\nMulti-wiki DB]
    P6 --> P7[Phase 7\nLint]
    P7 --> P8[Phase 8\nUI]

    style P0 fill:#2d6a4f,color:#fff
    style P1 fill:#2d6a4f,color:#fff
    style P2 fill:#2d6a4f,color:#fff
    style P3 fill:#2d6a4f,color:#fff
    style P4 fill:#2d6a4f,color:#fff
    style P5 fill:#2d6a4f,color:#fff
    style P6 fill:#2d6a4f,color:#fff
    style P7 fill:#2d6a4f,color:#fff
    style P8 fill:#40916c,color:#fff
```

| Color | Meaning |
|-------|---------|
| Dark green (`#2d6a4f`) | Done (Phases 0–7) |
| Mid green (`#40916c`) | Next up (Phase 8) |

---

## 3. Phase 0 — Environment

```mermaid
flowchart TB
    subgraph phase0 [Phase 0 setup]
        Env[.env\nOPENAI_API_KEY\nORACLE_*]
        Docker[Oracle 26ai Docker\nport 1521]
        Embed[nomic-embed-text-v2-moe\n768-dim local]
        LC[LangChain + LangGraph]
        Corpus[corpus/raw/\n15 articles]
    end

    Env --> LC
    Env --> Docker
    Embed --> Docker
    Scrape[scrape_corpus.py] --> Corpus
```

---

## 4. Phase 1 — Wiki scaffolding

```mermaid
flowchart TB
    subgraph cli1 [CLI Phase 1]
        CW[create-wiki]
        LW[list-wikis]
        IW[inspect-wiki]
    end

    subgraph wiki_pkg [llm_wiki/wiki]
        WM[wiki_manager.py\ncreate list inspect links]
        FM[frontmatter.py\nvalidate read write]
        SG[schema_generator.py\nLLM SCHEMA.md]
    end

    subgraph wiki_disk [wikis/eggless-baking/]
        RAW[raw/]
        SUM[summaries/]
        ENT[entities/]
        TOP[topics/]
        SCHEMA[SCHEMA.md]
        IDX[index.md]
        LOG[log.md]
    end

    CW --> WM
    CW --> SG
    LW --> WM
    IW --> WM
    IW --> FM
    SG --> SCHEMA
    WM --> wiki_disk
    FM --> ENT
```

---

## 5. Phase 2 — Ingestion pipeline

### 5a. End-to-end ingest flow

```mermaid
flowchart TB
    User[Developer] -->|cli.py ingest| Run[run_ingestion]
    Src[corpus/raw/article.md] --> Run
    Run --> Copy[prepare_source\ncopy to wiki/raw/]
    Copy --> Graph[LangGraph pipeline]

    Graph --> Disk[(wikis/eggless-baking/\nsummaries entities topics)]
    Graph --> IndexLog[index_log/\nrebuild_index append_log]
    Graph --> EmbedSync[embeddings/sync\nsync_page_paths]
    IndexLog --> Disk2[(index.md log.md)]
    EmbedSync --> Oracle[(Oracle wiki_pages)]

    Graph --> OpenAI[OpenAI gpt-4o-mini]
    Graph --> Ollama[Ollama\nindex one-liners]
    Graph --> Nomic[Nomic 768-dim\nembed_text]
    Nomic --> EmbedSync
    SCHEMA[SCHEMA.md] --> Graph
```

### 5b. LangGraph nodes (detailed)

```mermaid
flowchart LR
    START((START)) --> RS[read_source]
    RS --> EI[extract_info]
    EI --> WS[write_summary_page]
    WS --> UE[update_entity_pages]
    UE --> UC[update_concept_pages]
    UC --> UT[update_topic_pages]
    UT --> DC[detect_contradictions]
    DC --> FG[flag_gaps]
    FG --> SE[sync_embeddings]
    SE --> UI[update_index]
    UI --> AL[append_log]
    AL --> END((END))

    RS -.- RSd[Load SCHEMA\nCopy/read raw]
    EI -.- EId[LLM JSON extract]
    WS -.- WSd[LLM summary\n+ index_summary]
    UE -.- UEd[LLM entities/\n+ index_summary]
    UC -.- UCd[LLM topics/ concept\n+ index_summary]
    UT -.- UTd[LLM topics/ overview\n+ index_summary]
    DC -.- DCd[LLM compare claims]
    FG -.- FGd[LLM stub pages\n+ index_summary]
    SE -.- SEd[Oracle upsert\npages_written only]
    UI -.- UId[index_log.rebuild_index]
    AL -.- ALd[index_log.append_log_entry\nwith timestamp]
```

### 5c. IngestionState (shared backpack)

```mermaid
flowchart TB
    subgraph state [IngestionState]
        direction TB
        S1[wiki_root source_path source_text]
        S2[schema_text extraction]
        S3[pages_written contradictions gaps_flagged]
        S4[embed_embedded embed_skipped embed_warnings]
        S5[errors]
    end

    RS[read_source] -->|fills| S1
    RS -->|fills| S2
    EI[extract_info] -->|fills| S2
    WS[write_summary_page] -->|fills| S3
    UE[update_entity_pages] -->|fills| S3
    DC[detect_contradictions] -->|fills| S3
    SE[sync_embeddings] -->|fills| S4
```

---

## 6. Wiki page model (Option A)

```mermaid
flowchart TB
    subgraph raw [raw/ — read only]
        R1[king-arthur-guide-aquafaba.md]
    end

    subgraph summaries [summaries/ type summary]
        S1[king-arthur-guide-aquafaba.md]
    end

    subgraph entities [entities/ type entity]
        E1[aquafaba.md]
        E2[flaxseeds.md]
    end

    subgraph topics [topics/ type concept or overview]
        T1[emulsification.md\nconcept]
        T2[egg-substitutes-comparison.md\noverview]
    end

    R1 -->|ingest| S1
    R1 -->|ingest| E1
    R1 -->|ingest| T2
    S1 -->|wikilink| E1
    S1 -->|wikilink| T1
    T2 -->|wikilink| E1
```

---

## 7. Data flow — corpus to wiki

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant CLI as cli.py
    participant Scraper as scrape_corpus.py
    participant Corpus as corpus/raw
    participant Ingest as ingestion/graph
    participant IndexLog as index_log
    participant Embed as embeddings/sync
    participant Oracle as Oracle DB
    participant OpenAI as OpenAI
    participant Ollama as Ollama
    participant Nomic as Nomic embed
    participant Wiki as wikis/eggless-baking

    Note over Scraper,Corpus: Phase 0
    Dev->>Scraper: --limit 15
    Scraper->>Corpus: save .md articles

    Note over Dev,Wiki: Phase 2–4 ingest
    Dev->>CLI: ingest eggless-baking article.md
    CLI->>Ingest: run_ingestion()
    Ingest->>Wiki: copy to raw/ (once)
    Ingest->>Wiki: read SCHEMA.md
    loop Each LangGraph node
        Ingest->>OpenAI: prompt + source/schema
        OpenAI-->>Ingest: text or JSON
        Ingest->>Ollama: index_oneliner prompt
        Ollama-->>Ingest: index_summary
        Ingest->>Wiki: write/update pages + frontmatter
    end

    Note over Ingest,Oracle: Phase 3 index and log
    Ingest->>Embed: sync_page_paths(pages_written)
    Embed->>Nomic: embed_text title + index_summary
    Nomic-->>Embed: 768-dim vector
    Embed->>Oracle: MERGE wiki_pages
    Ingest->>IndexLog: rebuild_index()
    IndexLog->>Wiki: rewrite index.md
    Ingest->>IndexLog: append_log_entry()
    IndexLog->>Wiki: append log.md line with timestamp
    CLI-->>Dev: pages written, embed stats
```

### 7b. Query flow (Phase 5)

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant CLI as cli.py query/chat
    participant Query as query/graph
    participant IndexLog as index_log
    participant Search as hybrid_search
    participant Oracle as Oracle DB
    participant OpenAI as OpenAI
    participant Wiki as wikis/eggless-baking

    Dev->>CLI: query eggless-baking "How does aquafaba work?"
    CLI->>Query: run_query()
    Query->>IndexLog: load_wiki_context()
    IndexLog->>Wiki: read index.md + log tail
    Query->>Search: hybrid_search(project, question)
    Search->>Oracle: vector + FTS
    Oracle-->>Search: top pages
    Query->>Wiki: read full page bodies
    Query->>OpenAI: query_synthesize.md + pages
    OpenAI-->>Query: cited markdown + coverage JSON
    Query->>IndexLog: append_log_entry(query)
    CLI-->>Dev: answer + coverage
    opt Save answer
        Dev->>CLI: confirm save
        CLI->>Wiki: write topics/ overview page
        CLI->>IndexLog: rebuild_index()
        CLI->>Oracle: sync_page_paths()
    end
```

---

## 8. Phase 3 — Index & log

Extracted from ingestion nodes into `llm_wiki/index_log/`. Index rebuild is filesystem-driven (stale entries drop when pages are deleted). One-liners use a **hybrid** model: Ollama at write time → `index_summary` in frontmatter; heuristic fallback on rebuild (no LLM).

### 8a. Module layout

```mermaid
flowchart TB
    subgraph index_log [llm_wiki/index_log]
        IB[index_builder.py\nrebuild_index]
        LW[log_writer.py\nappend_log_entry\nlist_log_entries]
        OL[oneliner.py\ngenerate_index_summary\nenrich_meta_with_index_summary]
        RD[readers.py\nread_index read_log\nload_wiki_context]
    end

    subgraph cli3 [CLI Phase 3]
        SI[show-index]
        SL[show-log --tail N]
        RI[rebuild-index]
    end

    subgraph disk [wikis/eggless-baking/]
        IDX[index.md\nSources Entities Concepts Overviews]
        LOG[log.md\ntimestamped entries]
        PAGES[summaries/ entities/ topics/\nindex_summary in FM]
    end

    IB --> IDX
    LW --> LOG
    OL --> PAGES
    PAGES --> IB
    SI --> RD
    SL --> RD
    RI --> IB
    RI --> LW
    RD --> IDX
    RD --> LOG
```

### 8b. Hybrid one-liner flow

```mermaid
flowchart LR
    subgraph write [At page write time]
        Ingest[ingestion nodes]
        Ollama[Ollama\nindex_oneliner.md]
        Heur[heuristic fallback]
        Page[page.md\n+ index_summary FM]
    end

    subgraph rebuild [On rebuild / post-ingest]
        Builder[index_builder.rebuild_index]
        Index[index.md]
    end

    Ingest --> Ollama
    Ollama --> Page
    Ollama -.->|fail| Heur
    Heur --> Page
    Page -->|read index_summary| Builder
    Page -.->|missing FM field| Builder
    Builder --> Index
```

### 8c. Log format and events

```mermaid
flowchart TB
    subgraph events [Event types]
        E1[ingest]
        E2[ingest-failed]
        E3[index-rebuild]
        E4[embed-sync]
        E5[query]
        E6[lint]
        E7[schema-change — reserved]
    end

    Writer[log_writer.append_log_entry] --> Line["## [YYYY-MM-DD HH:MM:SS] type | description"]
    Line --> LogFile[log.md append-only]

    E1 --> Writer
    E2 --> Writer
    E3 --> Writer
```

**Log format:** `## [YYYY-MM-DD HH:MM:SS] event-type | description`  
Legacy date-only entries (`## [YYYY-MM-DD] ...`) still parse.  
**Index sections:** Sources (summaries), Entities, Concepts, Overviews — each entry shows wikilink, one-liner, path, `created`, source count.

---

## 9. Phase 4 — Vector & hybrid search

Wiki pages are embedded with Nomic (`768`-dim) and stored in Oracle `wiki_pages`. Search combines vector similarity + Oracle Text via reciprocal rank fusion (RRF).

### 9a. Module layout

```mermaid
flowchart TB
    subgraph db [llm_wiki/db]
        Conn[connection.py\noracle_connection]
        Schema[schema.py\nensure_schema\nTABLESPACE USERS]
    end

    subgraph embed [llm_wiki/embeddings]
        Model[model.py\nNomic embed_text embed_query]
        Text[text.py\nembed_text search_text\ncontent_hash]
        Sync[sync.py\nsync_wiki sync_page_paths]
    end

    subgraph search [llm_wiki/search]
        Vec[vector.py\nVECTOR_DISTANCE COSINE]
        FTS[fts.py\nOracle Text CONTAINS]
        Hyb[hybrid.py\nRRF merge k=60]
    end

    subgraph cli4 [CLI Phase 4]
        Ping[db-ping]
        Init[db-init]
        Status[db-status]
        EW[embed-wiki]
        SR[search --mode hybrid]
    end

    subgraph oracle [Oracle FREEPDB1]
        TBL[wiki_pages\nembed_text search_text\nembedding VECTOR768]
        VIX[wiki_pages_vec_idx]
        FIX[wiki_pages_fts_idx]
    end

    Ping --> Conn
    Init --> Schema
    EW --> Sync
    SR --> Hyb
    Sync --> Model
    Sync --> Text
    Sync --> TBL
    Hyb --> Vec
    Hyb --> FTS
    Vec --> VIX
    FTS --> FIX
    Schema --> TBL
```

### 9b. Embed & upsert flow

```mermaid
flowchart LR
    Page[page.md on disk] --> Build[build_page_texts]
    Build --> ET[embed_text\ntitle + index_summary]
    Build --> ST[search_text\ntitle + summary + body]
    ET --> Hash[content_hash SHA-256]
    Hash -->|unchanged| Skip[skip re-embed]
    Hash -->|new or changed| Nomic[Nomic 768-dim]
    Nomic --> Merge[MERGE wiki_pages\nproject_name + page_path]
    ST --> Merge
```

**Incremental rule:** only re-embed when `content_hash` of `embed_text` changes. Ingestion calls `sync_page_paths` for `pages_written` only; full backfill via `embed-wiki`.

### 9c. Hybrid search (RRF)

```mermaid
flowchart LR
    Q[User query] --> VQ[embed_query]
    Q --> FTQ[Oracle Text query]

    VQ --> VS[vector_search top 20\nCOSINE on embedding]
    FTQ --> FS[fts_search top 20\nSCORE on search_text]

    VS --> RRF[RRF merge k=60]
    FS --> RRF
    RRF --> Top[top 10 results\npage_path title snippet]
```

**Scope:** all searches filter `WHERE project_name = :wiki_name` (folder name, e.g. `eggless-baking`).

**Oracle setup notes:** table in `USERS` tablespace; `db-init` sets `SYSTEM` default tablespace to `USERS` for vector indexes. Set `USE_TF=0` for Nomic/Keras compatibility.

---

## 10. Phase 5 — Query system

LangGraph workflow answers questions from wiki pages only, with `[[Page Title]]` citations. Supports single-shot `query` and multi-turn `chat`; optional save back to `topics/` as an overview page.

### 10a. Module layout

```mermaid
flowchart TB
    subgraph query [llm_wiki/query]
        State[state.py\nQueryState messages]
        Nodes[nodes.py\nload_context hybrid_search\nread_pages synthesize]
        Graph[graph.py\nrun_query]
        Save[save.py\nsave_answer_as_page]
        LLM[llm.py\nquery system prompt]
    end

    subgraph cli5 [CLI Phase 5]
        Q[query wiki question]
        C[chat wiki]
    end

    subgraph deps [Reused modules]
        IL[index_log.load_wiki_context]
        HS[search.hybrid_search]
        FM[frontmatter write_page]
        EM[embeddings.sync_page_paths]
        RB[index_log.rebuild_index]
    end

    Q --> Graph
    C --> Graph
    Graph --> Nodes
    Nodes --> IL
    Nodes --> HS
    Nodes --> LLM
    Save --> FM
    Save --> RB
    Save --> EM
    Q -.->|optional| Save
    C -.->|optional| Save
```

### 10b. Query graph nodes

```mermaid
flowchart LR
    START((START)) --> LC[load_context]
    LC --> HS[hybrid_search]
    HS --> RP[read_pages]
    RP --> SA[synthesize_answer]
    SA --> AL[append_query_log]
    AL --> END((END))

    LC -.- LCd[index + log + SCHEMA excerpt]
    HS -.- HSd[Oracle RRF top 8]
    RP -.- RPd[full page bodies\n18k char budget]
    SA -.- SAd[OpenAI query_synthesize.md\nwikilink citations]
    AL -.- ALd[log query event\nappend messages]
```

### 10c. Coverage and save-to-wiki

```mermaid
flowchart TB
    Answer[LLM markdown answer] --> Meta["JSON: coverage full|partial|none\npages_used suggested_title"]
    Meta --> CLI[CLI shows answer + coverage]
    CLI -->|user confirms or --save| Save[save_answer_as_page]
    Save --> Page[topics/new-overview.md]
    Save --> Index[rebuild_index]
    Save --> Embed[sync_page_paths]
    Save --> Log[log query saved answer]
```

**Follow-ups:** `chat` passes accumulated `messages`; search prepends prior user question for context.  
**Honesty rule:** synthesis prompt requires admitting gaps (`coverage: none`) — no outside knowledge.

---

## 11. Phase 6 — Multi-wiki project registry

Oracle `wiki_projects` metadata + disk merge; all embed/search/query scoped by `project_name`.

```mermaid
flowchart TB
    CLI[cli.py\ncreate-wiki ingest embed-wiki\nquery list-projects sync-project]

    CLI --> W1[wikis/eggless-baking/]
    CLI --> W2[wikis/vr-research-papers/]
    CLI --> WN[wikis/...]

    subgraph shared [Shared code — llm_wiki/]
        Graph[ingestion graph]
        QGraph[query graph]
        FM[frontmatter]
        IL[index_log]
        Proj[projects/\nregistry stats]
    end

    CLI --> shared
    shared --> W1
    shared --> W2
    IL --> W1
    IL --> W2
    QGraph --> W1
    QGraph --> W2
    EmbedMod[embeddings/search] --> W1
    EmbedMod --> W2
    Proj --> W1
    Proj --> W2

    Oracle[(Oracle\nwiki_pages project_name\nwiki_projects metadata)] --> W1
    Oracle --> W2
```

**Isolation:** searches and embeddings filter by `project_name`; empty wiki returns zero cross-wiki hits.

---

## 12. Phase 7 — Lint system

LangGraph workflow health-checks a wiki (structural + LLM analysis), prints a prioritized report, and optionally applies fixes with user approval in the CLI.

### 12a. Module layout

```mermaid
flowchart TB
    subgraph lint [llm_wiki/lint]
        State[state.py\nLintIssue LintState]
        Struct[structural.py\norphan broken link\nmissing page FM]
        LLM[llm_checks.py\ncontradiction stale gap]
        Nodes[nodes.py\ngraph node fns]
        Graph[graph.py\nrun_lint]
        Report[report.py\nformat_lint_report]
        Fixes[fixes.py\napply_fix finalize]
    end

    subgraph cli7 [CLI Phase 7]
        Lint[lint wiki\n--checks structural|llm|all]
        RO[--report-only]
        AF[--auto-fix]
    end

    subgraph shared [Reused]
        WM[wiki_manager\nwikilinks title index]
        IL[index_log rebuild log]
        EM[embeddings.sync_page_paths]
        Proj[projects.try_sync_project]
        Contr[wiki/contradictions.py]
    end

    subgraph fixtures [Verification]
        LT[wikis/lint-test/]
        VL[scripts/verify_lint.py]
    end

    Lint --> Graph
    Graph --> Struct
    Graph --> LLM
    Lint --> Report
    Lint --> Fixes
    Fixes --> WM
    Fixes --> IL
    Fixes --> EM
    Fixes --> Proj
    Fixes --> Contr
    VL --> Graph
    VL --> LT
```

### 12b. Lint graph (analysis)

```mermaid
flowchart LR
    START((START)) --> LC[load_context]
    LC --> SC[structural_checks]
    SC --> LLM[llm_checks]
    LLM --> PF[prioritize_findings]
    PF --> END((END))

    LC -.- LCd[SCHEMA + page stats]
    SC -.- SCd[wikilink graph\nno LLM]
    LLM -.- LLMd[contradiction stale\ndata gaps prompts]
    PF -.- PFd[dedupe by id\nsort severity]
```

**Check modes:** `--checks structural` (7.1), `llm` (7.2), or `all`. Nodes skip passes not selected.

### 12c. Interactive fix loop (CLI, not in graph)

```mermaid
flowchart TB
    Report[format_lint_report] --> Loop{auto_fixable issues}
    Loop -->|each issue| Preview[preview_fix]
    Preview --> Confirm{user confirms\nor --auto-fix}
    Confirm -->|yes| Apply[apply_fix by fix_kind]
    Confirm -->|no| Skip[skip]
    Apply --> Finalize[finalize_wiki_changes]
    Skip --> Loop
    Finalize --> Index[rebuild_index]
    Finalize --> Embed[sync_page_paths]
    Finalize --> Log[append_log_entry lint]
    Finalize --> Meta[try_sync_project]
```

| `fix_kind` | Issue types | MVP action |
|------------|-------------|------------|
| `create_stub` | broken link, missing page | LLM stub in `entities/` |
| `add_backlink` | orphan | Add line to `index.md` |
| `append_contradiction` | contradiction | `## Contradictions` on pages |
| `revise_claim` | stale claim | `## Revision note` on page |

**Severity order:** Critical (contradiction, stale) → Warning (orphan, links, FM) → Suggestion (data gaps + research prompts).

**Verified:** `wikis/lint-test/` fixtures + `python3 scripts/verify_lint.py` (challenge Step 7 checklist).

---

## 13. Planned architecture (Phase 8)

*Phases 0–7 are built; update this section when Phase 8 ships.*

```mermaid
flowchart TB
    subgraph done [Built — Phases 0–7]
        Ingest[Ingestion graph\n+ sync_embeddings]
        WikiFS[Wiki filesystem]
        IndexLog[index_log module]
        OllamaSvc[Ollama one-liners]
        CLI3[CLI index and log]
        DBMod[db + embeddings + search]
        OracleDB[(Oracle wiki_pages\nvector + FTS indexes)]
        CLISearch[CLI db-ping embed-wiki search]
        QueryMod[query LangGraph\nquery + chat CLI]
        SaveAns[save answer to topics/]
        Projects[wiki_projects table\nlist-projects sync-project]
        LintMod[lint LangGraph\nstructural + LLM checks\ninteractive fixes]
        LintCLI[CLI lint + verify_lint.py]
    end

    subgraph p8 [Phase 8 — next]
        UI[Streamlit web UI\nrich chat + browse]
    end

    Ingest --> WikiFS
    Ingest --> IndexLog
    Ingest --> DBMod
    Ingest --> OllamaSvc
    Ingest --> Projects
    CLI3 --> IndexLog
    CLISearch --> DBMod
    DBMod --> OracleDB
    Projects --> OracleDB
    QueryMod --> DBMod
    QueryMod --> IndexLog
    QueryMod --> SaveAns
    QueryMod --> Projects
    SaveAns --> WikiFS
    SaveAns --> DBMod
    LintMod --> WikiFS
    LintMod --> IndexLog
    LintMod --> DBMod
    LintCLI --> LintMod
    UI --> QueryMod
    UI --> LintMod
    UI --> Ingest

    style done fill:#2d6a4f,color:#fff
    style p8 fill:#40916c,color:#fff
```

---

## How to update this doc

When completing a phase:

1. Change **Last updated** at the top.
2. Update **Section 2** roadmap colors (done / partial / planned).
3. Add or expand a dedicated section with a new diagram (mirror Phase 1–2 pattern).
4. Update **Section 1** system overview — solid vs dotted lines.
5. Refine **Section 12** — move components from planned to built.
6. Note changes in [dev-notes.md](dev-notes.md) project status table.

**Preview:** Open this file in the Cursor/VS Code Markdown preview (`Cmd+Shift+V`) to render Mermaid diagrams. For ASCII fallbacks in plain terminals, ask and we can add a compact text version per section.
