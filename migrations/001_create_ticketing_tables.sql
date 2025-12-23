-- Ticketing System Tables Migration
-- Created: 2025-11-13
-- Description: Creates tables for tickets, messages, notes, and AI recommendations

-- ==================== Tickets Table ====================
CREATE TABLE IF NOT EXISTS tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_number VARCHAR(20) UNIQUE NOT NULL,
    customer_id VARCHAR(255) NOT NULL,
    channel VARCHAR(50) NOT NULL,
    assigned_to VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    priority VARCHAR(50) NOT NULL DEFAULT 'normal',
    subject VARCHAR(500),
    tags JSONB DEFAULT '[]'::jsonb,
    custom_fields JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMP
);

-- Indexes for tickets table
CREATE INDEX IF NOT EXISTS ix_tickets_ticket_number ON tickets(ticket_number);
CREATE INDEX IF NOT EXISTS ix_tickets_customer_id ON tickets(customer_id);
CREATE INDEX IF NOT EXISTS ix_tickets_assigned_to ON tickets(assigned_to);
CREATE INDEX IF NOT EXISTS ix_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS ix_tickets_created_at ON tickets(created_at);

-- ==================== Ticket Messages Table ====================
CREATE TABLE IF NOT EXISTS ticket_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    from_agent BOOLEAN NOT NULL DEFAULT false,
    content TEXT NOT NULL,
    author_name VARCHAR(255),
    author_email VARCHAR(255),
    author_id VARCHAR(255),
    custom_fields JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for ticket_messages table
CREATE INDEX IF NOT EXISTS ix_ticket_messages_ticket_id ON ticket_messages(ticket_id);
CREATE INDEX IF NOT EXISTS ix_ticket_messages_created_at ON ticket_messages(created_at);

-- ==================== Ticket Notes Table ====================
CREATE TABLE IF NOT EXISTS ticket_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    author_name VARCHAR(255) NOT NULL,
    author_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for ticket_notes table
CREATE INDEX IF NOT EXISTS ix_ticket_notes_ticket_id ON ticket_notes(ticket_id);

-- ==================== Ticket AI Recommendations Table ====================
CREATE TABLE IF NOT EXISTS ticket_ai_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    priority VARCHAR(50),
    actions JSONB NOT NULL,
    talking_points JSONB,
    warnings JSONB,
    estimated_impact JSONB,
    draft_response TEXT,
    draft_tone VARCHAR(50),
    draft_personalization JSONB,
    generated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);

-- Indexes for ticket_ai_recommendations table
CREATE INDEX IF NOT EXISTS ix_ticket_ai_recommendations_ticket_id ON ticket_ai_recommendations(ticket_id);
CREATE INDEX IF NOT EXISTS ix_ticket_ai_recommendations_expires_at ON ticket_ai_recommendations(expires_at);

-- ==================== Auto-update Timestamp Trigger ====================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_tickets_updated_at
    BEFORE UPDATE ON tickets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==================== Ticket Number Generator Function ====================
CREATE OR REPLACE FUNCTION generate_ticket_number()
RETURNS TEXT AS $$
DECLARE
    next_num INTEGER;
    ticket_num TEXT;
BEGIN
    -- Get the next number from sequence
    SELECT COALESCE(MAX(CAST(SUBSTRING(ticket_number FROM 3) AS INTEGER)), 0) + 1
    INTO next_num
    FROM tickets
    WHERE ticket_number ~ '^T-[0-9]+$';

    -- Format as T-001, T-002, etc.
    ticket_num := 'T-' || LPAD(next_num::TEXT, 3, '0');

    RETURN ticket_num;
END;
$$ LANGUAGE plpgsql;

-- ==================== Comments ====================
COMMENT ON TABLE tickets IS 'Main support tickets from all channels (email, SMS, phone, chat, etc.)';
COMMENT ON TABLE ticket_messages IS 'Individual messages within ticket conversations (from customers and agents)';
COMMENT ON TABLE ticket_notes IS 'Internal agent notes (not visible to customers)';
COMMENT ON TABLE ticket_ai_recommendations IS 'Cached AI-generated recommendations and draft responses';

COMMENT ON COLUMN tickets.ticket_number IS 'Human-readable ticket number (e.g., T-001, T-002)';
COMMENT ON COLUMN tickets.channel IS 'Channel: email, sms, phone, chat, whatsapp, etc.';
COMMENT ON COLUMN tickets.status IS 'Status: open, pending, closed';
COMMENT ON COLUMN tickets.priority IS 'Priority: urgent, high, normal, low';
COMMENT ON COLUMN tickets.tags IS 'Array of tags: ["vip", "shipping_issue", "resolved"]';

-- ==================== Verification ====================
-- Verify tables were created
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'tickets') THEN
        RAISE NOTICE 'SUCCESS: tickets table created';
    END IF;
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'ticket_messages') THEN
        RAISE NOTICE 'SUCCESS: ticket_messages table created';
    END IF;
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'ticket_notes') THEN
        RAISE NOTICE 'SUCCESS: ticket_notes table created';
    END IF;
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'ticket_ai_recommendations') THEN
        RAISE NOTICE 'SUCCESS: ticket_ai_recommendations table created';
    END IF;
END $$;
