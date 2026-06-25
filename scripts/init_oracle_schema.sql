-- Phase 4: wiki page embeddings (reference DDL; prefer: python3 cli.py db-init)
-- Phase 6: wiki_projects metadata registry
-- Run as SYSTEM or app user on FREEPDB1

CREATE TABLE wiki_pages (
    id              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_name    VARCHAR2(100) NOT NULL,
    page_path       VARCHAR2(500) NOT NULL,
    title           VARCHAR2(200),
    page_type       VARCHAR2(50),
    tags            VARCHAR2(500),
    embed_text      CLOB,
    search_text     CLOB,
    embedding       VECTOR(768, FLOAT32),
    content_hash    VARCHAR2(64),
    updated_at      TIMESTAMP DEFAULT SYSTimestamp NOT NULL,
    CONSTRAINT wiki_pages_uk UNIQUE (project_name, page_path)
) TABLESPACE USERS;

CREATE VECTOR INDEX wiki_pages_vec_idx
ON wiki_pages (embedding)
ORGANIZATION NEIGHBOR PARTITIONS
DISTANCE COSINE
WITH TARGET ACCURACY 95;

CREATE INDEX wiki_pages_fts_idx
ON wiki_pages (search_text)
INDEXTYPE IS CTXSYS.CONTEXT;

CREATE TABLE wiki_projects (
    id                NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name              VARCHAR2(100) NOT NULL UNIQUE,
    wiki_path         VARCHAR2(500),
    created_at        TIMESTAMP DEFAULT SYSTimestamp NOT NULL,
    last_ingestion    TIMESTAMP,
    last_query        TIMESTAMP,
    page_count        NUMBER DEFAULT 0,
    source_count      NUMBER DEFAULT 0,
    embedding_count   NUMBER DEFAULT 0,
    updated_at        TIMESTAMP DEFAULT SYSTimestamp NOT NULL
) TABLESPACE USERS;
