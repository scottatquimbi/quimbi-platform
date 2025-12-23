-- ================================================================
-- KNOWLEDGE BASE SCHEMA (No Vector Extension Required)
-- Purpose: Store KB articles, categories, and search infrastructure
-- Author: Quimbi Platform
-- Date: 2025-12-17
-- Note: Uses PostgreSQL native full-text search only
--       Vector embeddings will be added when pgvector is available
-- ================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create schema
CREATE SCHEMA IF NOT EXISTS knowledge_base;

-- ================================================================
-- CORE TABLES
-- ================================================================

-- Categories organize articles hierarchically
CREATE TABLE knowledge_base.categories (
    category_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Hierarchy support
    parent_category_id UUID REFERENCES knowledge_base.categories(category_id) ON DELETE SET NULL,

    -- Content
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(200) UNIQUE NOT NULL,
    description TEXT,
    icon VARCHAR(100),

    -- Display
    display_order INTEGER DEFAULT 0,
    is_visible BOOLEAN DEFAULT TRUE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_kb_categories_parent ON knowledge_base.categories(parent_category_id);
CREATE INDEX idx_kb_categories_slug ON knowledge_base.categories(slug);
CREATE INDEX idx_kb_categories_visible ON knowledge_base.categories(is_visible) WHERE is_visible = TRUE;


-- Articles are the core content units
CREATE TABLE knowledge_base.articles (
    article_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Content
    title VARCHAR(500) NOT NULL,
    slug VARCHAR(500) UNIQUE NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,

    -- Organization
    category_id UUID REFERENCES knowledge_base.categories(category_id) ON DELETE SET NULL,
    tags TEXT[],

    -- Metadata
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    visibility VARCHAR(50) DEFAULT 'private' CHECK (visibility IN ('private', 'public')),
    author_id VARCHAR(100),
    language VARCHAR(10) DEFAULT 'en',

    -- Search keywords
    search_keywords TEXT[],

    -- Placeholder for future vector embeddings
    -- embedding_vector will be added when pgvector is available
    embedding_metadata JSONB DEFAULT '{}'::jsonb,

    -- Analytics
    view_count INTEGER DEFAULT 0,
    helpful_count INTEGER DEFAULT 0,
    not_helpful_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    published_at TIMESTAMP WITH TIME ZONE,

    -- Full-text search (PostgreSQL native)
    tsv tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(summary, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(content, '')), 'C')
    ) STORED
);

-- Indexes for articles
CREATE INDEX idx_kb_articles_tsv ON knowledge_base.articles USING GIN(tsv);
CREATE INDEX idx_kb_articles_category ON knowledge_base.articles(category_id);
CREATE INDEX idx_kb_articles_status ON knowledge_base.articles(status);
CREATE INDEX idx_kb_articles_visibility ON knowledge_base.articles(visibility);
CREATE INDEX idx_kb_articles_tags ON knowledge_base.articles USING GIN(tags);
CREATE INDEX idx_kb_articles_published ON knowledge_base.articles(published_at) WHERE status = 'published';


-- Related articles (many-to-many)
CREATE TABLE knowledge_base.article_relations (
    from_article_id UUID REFERENCES knowledge_base.articles(article_id) ON DELETE CASCADE,
    to_article_id UUID REFERENCES knowledge_base.articles(article_id) ON DELETE CASCADE,
    relation_type VARCHAR(50) DEFAULT 'related' CHECK (relation_type IN ('related', 'prerequisite', 'next-step', 'alternative')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    PRIMARY KEY (from_article_id, to_article_id)
);

CREATE INDEX idx_kb_article_relations_from ON knowledge_base.article_relations(from_article_id);
CREATE INDEX idx_kb_article_relations_to ON knowledge_base.article_relations(to_article_id);


-- Attachments (images, PDFs, etc.)
CREATE TABLE knowledge_base.attachments (
    attachment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id UUID REFERENCES knowledge_base.articles(article_id) ON DELETE CASCADE,

    -- File info
    filename VARCHAR(500) NOT NULL,
    file_url TEXT NOT NULL,
    file_type VARCHAR(100),
    file_size BIGINT,

    -- Metadata
    alt_text TEXT,
    caption TEXT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    uploaded_by VARCHAR(100)
);

CREATE INDEX idx_kb_attachments_article ON knowledge_base.attachments(article_id);


-- Article versions (track changes)
CREATE TABLE knowledge_base.article_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id UUID REFERENCES knowledge_base.articles(article_id) ON DELETE CASCADE,

    -- Snapshot
    title VARCHAR(500),
    content TEXT,
    summary TEXT,

    -- Version metadata
    version_number INTEGER NOT NULL,
    change_description TEXT,
    edited_by VARCHAR(100),

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(article_id, version_number)
);

CREATE INDEX idx_kb_article_versions_article ON knowledge_base.article_versions(article_id);
CREATE INDEX idx_kb_article_versions_number ON knowledge_base.article_versions(article_id, version_number DESC);


-- ================================================================
-- INTEGRATION TABLES (Link KB to Tickets)
-- ================================================================

-- Track which articles were suggested/used for which tickets
CREATE TABLE knowledge_base.article_ticket_links (
    link_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- References
    article_id UUID REFERENCES knowledge_base.articles(article_id) ON DELETE CASCADE,
    ticket_id UUID REFERENCES support_app.tickets(ticket_id) ON DELETE CASCADE,

    -- Context
    link_type VARCHAR(50) CHECK (link_type IN ('suggested', 'cited', 'inserted', 'related')),
    agent_id VARCHAR(100),

    -- Feedback
    was_helpful BOOLEAN,
    agent_feedback TEXT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_kb_article_ticket_links_article ON knowledge_base.article_ticket_links(article_id);
CREATE INDEX idx_kb_article_ticket_links_ticket ON knowledge_base.article_ticket_links(ticket_id);
CREATE INDEX idx_kb_article_ticket_links_type ON knowledge_base.article_ticket_links(link_type);


-- Article analytics (effectiveness metrics)
CREATE TABLE knowledge_base.article_analytics (
    analytics_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id UUID REFERENCES knowledge_base.articles(article_id) ON DELETE CASCADE,

    -- Time period
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Usage metrics
    times_suggested INTEGER DEFAULT 0,
    times_used INTEGER DEFAULT 0,
    times_rated_helpful INTEGER DEFAULT 0,
    times_rated_not_helpful INTEGER DEFAULT 0,

    -- Ticket outcome metrics
    avg_resolution_time_seconds INTEGER,
    tickets_resolved_first_contact INTEGER,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(article_id, period_start, period_end)
);

CREATE INDEX idx_kb_article_analytics_article ON knowledge_base.article_analytics(article_id);
CREATE INDEX idx_kb_article_analytics_period ON knowledge_base.article_analytics(period_start, period_end);


-- ================================================================
-- SEARCH TABLES
-- ================================================================

-- Search query tracking (analytics)
CREATE TABLE knowledge_base.search_queries (
    query_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Query details
    query_text TEXT NOT NULL,
    searcher_type VARCHAR(50) CHECK (searcher_type IN ('agent', 'customer', 'ai')),
    searcher_id VARCHAR(100),

    -- Results
    result_count INTEGER,
    top_result_article_id UUID REFERENCES knowledge_base.articles(article_id) ON DELETE SET NULL,
    clicked_article_id UUID REFERENCES knowledge_base.articles(article_id) ON DELETE SET NULL,

    -- Context
    ticket_id UUID REFERENCES support_app.tickets(ticket_id) ON DELETE SET NULL,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_kb_search_queries_text ON knowledge_base.search_queries USING gin(to_tsvector('english', query_text));
CREATE INDEX idx_kb_search_queries_ticket ON knowledge_base.search_queries(ticket_id);
CREATE INDEX idx_kb_search_queries_created ON knowledge_base.search_queries(created_at);


-- ================================================================
-- FUNCTIONS & TRIGGERS
-- ================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION knowledge_base.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_kb_articles_updated_at BEFORE UPDATE
    ON knowledge_base.articles FOR EACH ROW
    EXECUTE FUNCTION knowledge_base.update_updated_at_column();

CREATE TRIGGER update_kb_categories_updated_at BEFORE UPDATE
    ON knowledge_base.categories FOR EACH ROW
    EXECUTE FUNCTION knowledge_base.update_updated_at_column();


-- Auto-create version when article is updated
CREATE OR REPLACE FUNCTION knowledge_base.create_article_version()
RETURNS TRIGGER AS $$
BEGIN
    -- Only create version if content changed
    IF OLD.content IS DISTINCT FROM NEW.content OR
       OLD.title IS DISTINCT FROM NEW.title OR
       OLD.summary IS DISTINCT FROM NEW.summary THEN

        INSERT INTO knowledge_base.article_versions (
            article_id,
            title,
            content,
            summary,
            version_number,
            change_description,
            edited_by
        )
        SELECT
            NEW.article_id,
            OLD.title,
            OLD.content,
            OLD.summary,
            COALESCE((
                SELECT MAX(version_number) + 1
                FROM knowledge_base.article_versions
                WHERE article_id = NEW.article_id
            ), 1),
            'Auto-saved version',
            NEW.author_id;
    END IF;

    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER create_kb_article_version AFTER UPDATE
    ON knowledge_base.articles FOR EACH ROW
    EXECUTE FUNCTION knowledge_base.create_article_version();


-- ================================================================
-- INITIAL DATA (Categories for Linda's Electric Quilters)
-- ================================================================

-- Insert top-level categories
INSERT INTO knowledge_base.categories (name, slug, description, display_order, icon) VALUES
('Products', 'products', 'Product guides, care instructions, and compatibility information', 1, 'package'),
('Policies', 'policies', 'Shipping, returns, payment, and store policies', 2, 'file-text'),
('Quilting Techniques', 'quilting-techniques', 'How-to guides and quilting tutorials', 3, 'book-open'),
('Troubleshooting', 'troubleshooting', 'Solutions for common issues and problems', 4, 'tool'),
('Account & Website', 'account-website', 'Help with your account and using the website', 5, 'user');

-- Insert subcategories for Products
INSERT INTO knowledge_base.categories (name, slug, description, parent_category_id, display_order) VALUES
('Thread', 'thread', 'Thread types, weights, colors, and storage',
    (SELECT category_id FROM knowledge_base.categories WHERE slug = 'products'), 1),
('Fabric', 'fabric', 'Fabric types, care instructions, and selection guides',
    (SELECT category_id FROM knowledge_base.categories WHERE slug = 'products'), 2),
('Batting', 'batting', 'Choosing and caring for batting',
    (SELECT category_id FROM knowledge_base.categories WHERE slug = 'products'), 3),
('Notions', 'notions', 'Quilting tools and accessories',
    (SELECT category_id FROM knowledge_base.categories WHERE slug = 'products'), 4),
('Machines & Parts', 'machines-parts', 'Sewing machines, long-arm machines, and parts',
    (SELECT category_id FROM knowledge_base.categories WHERE slug = 'products'), 5);

-- Insert subcategories for Policies
INSERT INTO knowledge_base.categories (name, slug, description, parent_category_id, display_order) VALUES
('Shipping & Delivery', 'shipping-delivery', 'Shipping methods, costs, and tracking',
    (SELECT category_id FROM knowledge_base.categories WHERE slug = 'policies'), 1),
('Returns & Exchanges', 'returns-exchanges', 'Return policy and process',
    (SELECT category_id FROM knowledge_base.categories WHERE slug = 'policies'), 2),
('Payment & Pricing', 'payment-pricing', 'Payment methods and pricing information',
    (SELECT category_id FROM knowledge_base.categories WHERE slug = 'policies'), 3);

-- Insert subcategories for Quilting Techniques
INSERT INTO knowledge_base.categories (name, slug, description, parent_category_id, display_order) VALUES
('Beginner Guides', 'beginner-guides', 'Getting started with quilting',
    (SELECT category_id FROM knowledge_base.categories WHERE slug = 'quilting-techniques'), 1),
('Advanced Techniques', 'advanced-techniques', 'Advanced quilting methods',
    (SELECT category_id FROM knowledge_base.categories WHERE slug = 'quilting-techniques'), 2),
('Pattern Instructions', 'pattern-instructions', 'Help with reading and following patterns',
    (SELECT category_id FROM knowledge_base.categories WHERE slug = 'quilting-techniques'), 3);

-- Insert subcategories for Troubleshooting
INSERT INTO knowledge_base.categories (name, slug, description, parent_category_id, display_order) VALUES
('Machine Issues', 'machine-issues', 'Sewing machine and long-arm troubleshooting',
    (SELECT category_id FROM knowledge_base.categories WHERE slug = 'troubleshooting'), 1),
('Fabric Issues', 'fabric-issues', 'Fabric puckering, bleeding, and other problems',
    (SELECT category_id FROM knowledge_base.categories WHERE slug = 'troubleshooting'), 2),
('Order Issues', 'order-issues', 'Problems with orders and deliveries',
    (SELECT category_id FROM knowledge_base.categories WHERE slug = 'troubleshooting'), 3);


-- ================================================================
-- VIEWS
-- ================================================================

-- View: Published articles with category info
CREATE VIEW knowledge_base.published_articles AS
SELECT
    a.article_id,
    a.title,
    a.slug,
    a.summary,
    a.category_id,
    c.name as category_name,
    c.slug as category_slug,
    a.tags,
    a.view_count,
    a.helpful_count,
    a.not_helpful_count,
    a.published_at,
    a.updated_at
FROM knowledge_base.articles a
LEFT JOIN knowledge_base.categories c ON a.category_id = c.category_id
WHERE a.status = 'published'
  AND a.visibility = 'public'
ORDER BY a.published_at DESC;


-- View: Article effectiveness scores
CREATE VIEW knowledge_base.article_effectiveness AS
SELECT
    a.article_id,
    a.title,
    a.category_id,
    a.view_count,
    a.helpful_count,
    a.not_helpful_count,
    CASE
        WHEN (a.helpful_count + a.not_helpful_count) > 0
        THEN ROUND((a.helpful_count::DECIMAL / (a.helpful_count + a.not_helpful_count) * 100), 2)
        ELSE NULL
    END as helpfulness_percentage,
    COUNT(atl.link_id) as times_linked_to_tickets
FROM knowledge_base.articles a
LEFT JOIN knowledge_base.article_ticket_links atl ON a.article_id = atl.article_id
WHERE a.status = 'published'
GROUP BY a.article_id, a.title, a.category_id, a.view_count, a.helpful_count, a.not_helpful_count
ORDER BY helpfulness_percentage DESC NULLS LAST;


-- ================================================================
-- COMMENTS
-- ================================================================

COMMENT ON SCHEMA knowledge_base IS 'Knowledge base for support articles and documentation (no vector extension)';
COMMENT ON TABLE knowledge_base.articles IS 'Core KB articles with full-text search (vector embeddings to be added)';
COMMENT ON TABLE knowledge_base.categories IS 'Hierarchical organization of articles';
COMMENT ON TABLE knowledge_base.article_ticket_links IS 'Links articles to tickets for effectiveness tracking';
COMMENT ON TABLE knowledge_base.article_analytics IS 'Article usage and effectiveness metrics';
COMMENT ON COLUMN knowledge_base.articles.embedding_metadata IS 'Placeholder for vector embedding metadata until pgvector is available';
COMMENT ON COLUMN knowledge_base.articles.tsv IS 'Generated full-text search vector (weighted: title=A, summary=B, content=C)';
