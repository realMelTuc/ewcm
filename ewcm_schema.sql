-- EWCM: EVE Wormhole Chain Mapper
-- Schema for Supabase (PostgreSQL)
-- All tables prefixed with ewcm_

-- Active chain sessions
CREATE TABLE IF NOT EXISTS ewcm_chains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    home_system VARCHAR(100),
    status VARCHAR(20) DEFAULT 'active',  -- active, archived, collapsed
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    collapsed_at TIMESTAMPTZ
);

-- Systems (nodes) within a chain
CREATE TABLE IF NOT EXISTS ewcm_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chain_id UUID REFERENCES ewcm_chains(id) ON DELETE CASCADE,
    system_name VARCHAR(100) NOT NULL,
    wh_class VARCHAR(10),          -- C1, C2, C3, C4, C5, C6, HS, LS, NS, Thera
    static1 VARCHAR(20),           -- First static wormhole type (e.g. C247, B274)
    static2 VARCHAR(20),           -- Second static (if any)
    effect VARCHAR(50),            -- Pulsar, Wolf-Rayet, Cataclysmic Variable, etc.
    is_home BOOLEAN DEFAULT FALSE,
    notes TEXT,
    pos_x FLOAT DEFAULT 0,         -- Saved graph x position
    pos_y FLOAT DEFAULT 0,         -- Saved graph y position
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Connections (edges) between nodes in a chain
CREATE TABLE IF NOT EXISTS ewcm_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chain_id UUID REFERENCES ewcm_chains(id) ON DELETE CASCADE,
    from_node_id UUID REFERENCES ewcm_nodes(id) ON DELETE CASCADE,
    to_node_id UUID REFERENCES ewcm_nodes(id) ON DELETE CASCADE,
    wh_type VARCHAR(20) DEFAULT 'K162',        -- K162, C247, H296, B274, etc.
    wh_size VARCHAR(15) DEFAULT 'large',       -- frigate, cruiser, large, capital
    mass_status VARCHAR(20) DEFAULT 'fresh',   -- fresh, reduced, critical
    time_status VARCHAR(20) DEFAULT 'fresh',   -- fresh, eol
    sig_id_from VARCHAR(10),                   -- e.g. ABC-123
    sig_id_to VARCHAR(10),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Reusable system reference data (persists across chains)
CREATE TABLE IF NOT EXISTS ewcm_system_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    system_name VARCHAR(100) UNIQUE NOT NULL,
    wh_class VARCHAR(10),
    static1 VARCHAR(20),
    static2 VARCHAR(20),
    effect VARCHAR(50),
    region VARCHAR(50),
    notes TEXT,
    visit_count INTEGER DEFAULT 1,
    last_visited_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Archived chain snapshots (immutable history)
CREATE TABLE IF NOT EXISTS ewcm_chain_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chain_id UUID,
    chain_name VARCHAR(100),
    home_system VARCHAR(100),
    node_count INTEGER DEFAULT 0,
    connection_count INTEGER DEFAULT 0,
    nodes_data JSONB,
    connections_data JSONB,
    duration_minutes INTEGER,
    collapsed_at TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ewcm_nodes_chain_id ON ewcm_nodes(chain_id);
CREATE INDEX IF NOT EXISTS idx_ewcm_connections_chain_id ON ewcm_connections(chain_id);
CREATE INDEX IF NOT EXISTS idx_ewcm_connections_nodes ON ewcm_connections(from_node_id, to_node_id);
CREATE INDEX IF NOT EXISTS idx_ewcm_chains_status ON ewcm_chains(status);
CREATE INDEX IF NOT EXISTS idx_ewcm_history_chain_id ON ewcm_chain_history(chain_id);
