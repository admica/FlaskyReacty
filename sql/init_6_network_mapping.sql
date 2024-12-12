-- PostgreSQL database version 16.6
-- Network mapping optimization and monitoring
-- This replaces the old subnet mapping logic with an optimized version

-- Create sequence for mapping IDs
CREATE SEQUENCE subnet_mapping_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE subnet_mapping_id_seq OWNER TO pcapuser;

-- Create the main mapping table with ID-based partitioning
CREATE TABLE subnet_location_map (
    id bigint DEFAULT nextval('subnet_mapping_id_seq') NOT NULL,
    src_subnet cidr NOT NULL,
    dst_subnet cidr NOT NULL,
    src_location varchar(50) NOT NULL,
    dst_location varchar(50) NOT NULL,
    first_seen bigint NOT NULL,
    last_seen bigint NOT NULL,
    packet_count bigint DEFAULT 1 NOT NULL,
    last_updated timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT subnet_location_map_pkey PRIMARY KEY (id, last_seen),
    CONSTRAINT subnet_location_map_src_location_fkey FOREIGN KEY (src_location) REFERENCES locations(site),
    CONSTRAINT subnet_location_map_dst_location_fkey FOREIGN KEY (dst_location) REFERENCES locations(site),
    CONSTRAINT check_packet_count CHECK (packet_count > 0),
    CONSTRAINT check_seen_times CHECK (last_seen >= first_seen)
) PARTITION BY RANGE (last_seen);
ALTER TABLE subnet_location_map OWNER TO pcapuser;

-- Create indexes on the parent table (will be inherited by partitions)
CREATE INDEX idx_subnet_map_src_subnet ON subnet_location_map USING gist (src_subnet inet_ops);
CREATE INDEX idx_subnet_map_dst_subnet ON subnet_location_map USING gist (dst_subnet inet_ops);
CREATE INDEX idx_subnet_map_locations ON subnet_location_map(src_location, dst_location);
CREATE INDEX idx_subnet_map_last_seen ON subnet_location_map(last_seen);
CREATE INDEX idx_subnet_map_packet_count ON subnet_location_map(packet_count);

-- Create monthly summary table
CREATE TABLE subnet_mapping_monthly_summary (
    year_month date NOT NULL,
    src_location varchar(50) NOT NULL,
    dst_location varchar(50) NOT NULL,
    unique_src_subnets int NOT NULL,
    unique_dst_subnets int NOT NULL,
    total_packets bigint NOT NULL,
    avg_packets_per_mapping numeric(10,2) NOT NULL,
    total_mappings int NOT NULL,
    storage_bytes bigint NOT NULL,
    CONSTRAINT subnet_mapping_monthly_pkey PRIMARY KEY (year_month, src_location, dst_location),
    CONSTRAINT subnet_mapping_monthly_src_fkey FOREIGN KEY (src_location) REFERENCES locations(site),
    CONSTRAINT subnet_mapping_monthly_dst_fkey FOREIGN KEY (dst_location) REFERENCES locations(site)
);
ALTER TABLE subnet_mapping_monthly_summary OWNER TO pcapuser;

CREATE INDEX idx_monthly_summary_locations ON subnet_mapping_monthly_summary(src_location, dst_location);
CREATE INDEX idx_monthly_summary_date ON subnet_mapping_monthly_summary(year_month);

-- Create function to manage partitions
CREATE FUNCTION manage_subnet_partitions(
    p_retention_hours integer DEFAULT 24,
    p_future_hours integer DEFAULT 3
) RETURNS void AS $$
DECLARE
    partition_name text;
    partition_start bigint;
    partition_end bigint;
    v_current_time bigint;
    v_current_hour bigint;
    cutoff_time bigint;
BEGIN
    -- Get current time and align to hour boundary
    v_current_time := EXTRACT(EPOCH FROM NOW())::bigint;
    v_current_hour := v_current_time - (v_current_time % 3600);
    cutoff_time := v_current_hour - (p_retention_hours * 3600);
    
    -- Create future partitions
    FOR i IN 0..p_future_hours LOOP
        partition_start := v_current_hour + (i * 3600);
        partition_end := partition_start + 3600;
        partition_name := 'subnet_location_map_' || partition_start::text;
        
        IF NOT EXISTS (
            SELECT 1 
            FROM pg_class c 
            JOIN pg_namespace n ON n.oid = c.relnamespace 
            WHERE c.relname = partition_name
            AND n.nspname = 'public'
        ) THEN
            EXECUTE format(
                'CREATE TABLE %I PARTITION OF subnet_location_map 
                FOR VALUES FROM (%L) TO (%L)',
                partition_name, partition_start, partition_end
            );
            
            -- Set ownership
            EXECUTE format(
                'ALTER TABLE %I OWNER TO pcapuser',
                partition_name
            );
        END IF;
    END LOOP;

    -- Drop old partitions
    FOR partition_name IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public'
        AND tablename LIKE 'subnet_location_map_%'
        AND split_part(tablename, '_', 4)::bigint < cutoff_time
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', partition_name);
    END LOOP;
END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION manage_subnet_partitions(integer, integer) OWNER TO pcapuser;

-- Create function to update subnet mappings efficiently
CREATE FUNCTION update_subnet_mappings(
    p_src_location varchar,
    p_dst_location varchar,
    p_current_time bigint
) RETURNS void AS $$
DECLARE
    batch_size integer := 10000;
    processed integer := 0;
    v_sql text;
    v_src_table text;
    v_dst_table text;
BEGIN
    -- Ensure partition exists
    PERFORM manage_subnet_partitions();
    
    -- Drop the temporary table if it exists
    DROP TABLE IF EXISTS tmp_new_mappings;
    
    -- Create temporary table for new mappings
    CREATE TEMPORARY TABLE tmp_new_mappings (
        src_subnet cidr,
        dst_subnet cidr,
        first_seen bigint,
        last_seen bigint,
        packet_count bigint
    ) ON COMMIT DROP;
    
    -- Build table names safely with double quotes to preserve case
    v_src_table := format('public."loc_src_%s"', p_src_location);
    v_dst_table := format('public."loc_dst_%s"', p_dst_location);
    
    -- Build dynamic SQL for the location-specific query
    v_sql := format(
        'INSERT INTO tmp_new_mappings
        SELECT 
            src.subnet as src_subnet,
            dst.subnet as dst_subnet,
            LEAST(src.first_seen, dst.first_seen) as first_seen,
            GREATEST(src.last_seen, dst.last_seen) as last_seen,
            GREATEST(src.count, dst.count) as packet_count
        FROM (
            SELECT DISTINCT s.subnet, s.first_seen, s.last_seen, s.count, s.sensor, s.device
            FROM %s s
            WHERE s.last_seen >= %L - 86400
        ) src
        JOIN (
            SELECT DISTINCT d.subnet, d.first_seen, d.last_seen, d.count, d.sensor, d.device
            FROM %s d
            WHERE d.last_seen >= %L - 86400
        ) dst ON src.sensor = dst.sensor AND src.device = dst.device',
        v_src_table, p_current_time, v_dst_table, p_current_time
    );
    
    -- Execute the dynamic SQL
    EXECUTE v_sql;
    
    -- Insert new mappings in batches
    LOOP
        INSERT INTO subnet_location_map (
            src_subnet,
            dst_subnet,
            src_location,
            dst_location,
            first_seen,
            last_seen,
            packet_count
        )
        SELECT 
            src_subnet,
            dst_subnet,
            p_src_location,
            p_dst_location,
            first_seen,
            last_seen,
            packet_count
        FROM tmp_new_mappings
        OFFSET processed
        LIMIT batch_size
        ON CONFLICT (id, last_seen) DO UPDATE
        SET first_seen = LEAST(subnet_location_map.first_seen, EXCLUDED.first_seen),
            packet_count = subnet_location_map.packet_count + EXCLUDED.packet_count,
            last_updated = CURRENT_TIMESTAMP;
            
        GET DIAGNOSTICS processed = ROW_COUNT;
        EXIT WHEN processed < batch_size;
        processed := processed + batch_size;
    END LOOP;
    
    -- Clean up
    DROP TABLE IF EXISTS tmp_new_mappings;
END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION update_subnet_mappings(varchar, varchar, bigint) OWNER TO pcapuser;

-- Create monitoring view
CREATE MATERIALIZED VIEW network_traffic_summary AS
WITH partition_stats AS (
    SELECT 
        src_location,
        dst_location,
        (last_seen - (last_seen % 3600)) as hour_bucket,
        COUNT(DISTINCT src_subnet) as unique_src_subnets,
        COUNT(DISTINCT dst_subnet) as unique_dst_subnets,
        SUM(packet_count) as total_packets,
        MIN(first_seen) as earliest_seen,
        MAX(last_seen) as latest_seen,
        COUNT(*) as total_mappings,
        pg_size_pretty(pg_total_relation_size(
            format('subnet_location_map_%s', 
            (last_seen - (last_seen % 3600))::text)::regclass
        )) as partition_size
    FROM subnet_location_map
    WHERE last_seen >= EXTRACT(EPOCH FROM NOW() - INTERVAL '24 hours')::bigint
    GROUP BY src_location, dst_location, hour_bucket
)
SELECT 
    src_location,
    dst_location,
    SUM(unique_src_subnets) as unique_src_subnets,
    SUM(unique_dst_subnets) as unique_dst_subnets,
    SUM(total_packets) as total_packets,
    MIN(earliest_seen) as earliest_seen,
    MAX(latest_seen) as latest_seen,
    SUM(total_mappings) as total_mappings,
    MAX(partition_size) as partition_size
FROM partition_stats
GROUP BY src_location, dst_location
WITH NO DATA;
ALTER MATERIALIZED VIEW network_traffic_summary OWNER TO pcapuser;

-- Create indexes for the materialized view
CREATE UNIQUE INDEX idx_traffic_summary_unique ON network_traffic_summary(src_location, dst_location);
CREATE INDEX idx_traffic_summary_locations ON network_traffic_summary(src_location);
CREATE INDEX idx_traffic_summary_dst_locations ON network_traffic_summary(dst_location);

-- Create function to refresh the network traffic summary view
CREATE FUNCTION refresh_network_traffic_summary() RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY network_traffic_summary;
EXCEPTION
    WHEN OTHERS THEN
        -- Fall back to non-concurrent refresh if concurrent fails
        REFRESH MATERIALIZED VIEW network_traffic_summary;
END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION refresh_network_traffic_summary() OWNER TO pcapuser;

-- Create monitoring functions
CREATE FUNCTION get_mapping_statistics(
    hours integer DEFAULT 24
) RETURNS TABLE (
    time_bucket text,
    total_mappings bigint,
    unique_subnets bigint,
    avg_packet_count numeric,
    partition_size text
) AS $$
BEGIN
    RETURN QUERY
    WITH time_buckets AS (
        SELECT 
            to_timestamp(last_seen)::date::text as bucket,
            COUNT(*) as mappings,
            COUNT(DISTINCT src_subnet) + COUNT(DISTINCT dst_subnet) as subnets,
            AVG(packet_count) as avg_packets,
            pg_size_pretty(pg_total_relation_size(
                format('subnet_location_map_%s', 
                (last_seen - (last_seen % 3600))::text)::regclass
            )) as part_size
        FROM subnet_location_map
        WHERE last_seen >= EXTRACT(EPOCH FROM NOW() - (hours || ' hours')::interval)::bigint
        GROUP BY bucket
    )
    SELECT * FROM time_buckets
    ORDER BY bucket DESC;
END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION get_mapping_statistics(integer) OWNER TO pcapuser;

-- Create cleanup function with volume control
CREATE FUNCTION cleanup_subnet_mappings(
    p_min_packet_count bigint DEFAULT 1000,
    p_batch_size integer DEFAULT 100000
) RETURNS void AS $$
DECLARE
    deleted integer;
    total_deleted integer := 0;
    cutoff_time bigint;
BEGIN
    -- Update monthly summary before cleanup
    INSERT INTO subnet_mapping_monthly_summary
    WITH monthly_stats AS (
        SELECT 
            src_location,
            dst_location,
            COUNT(DISTINCT src_subnet) as unique_src_subnets,
            COUNT(DISTINCT dst_subnet) as unique_dst_subnets,
            SUM(packet_count) as total_packets,
            COUNT(*) as total_mappings,
            SUM(pg_total_relation_size(
                format('subnet_location_map_%s', 
                (last_seen - (last_seen % 3600))::text)::regclass
            )) as storage_bytes
        FROM subnet_location_map
        WHERE to_timestamp(last_seen)::date >= date_trunc('month', CURRENT_DATE)
        AND to_timestamp(last_seen)::date < date_trunc('month', CURRENT_DATE + interval '1 month')
        GROUP BY src_location, dst_location
    )
    SELECT 
        date_trunc('month', CURRENT_DATE),
        src_location,
        dst_location,
        unique_src_subnets,
        unique_dst_subnets,
        total_packets,
        (total_packets::numeric / NULLIF(total_mappings, 0))::numeric(10,2) as avg_packets_per_mapping,
        total_mappings,
        storage_bytes
    FROM monthly_stats
    ON CONFLICT (year_month, src_location, dst_location) DO UPDATE
    SET unique_src_subnets = EXCLUDED.unique_src_subnets,
        unique_dst_subnets = EXCLUDED.unique_dst_subnets,
        total_packets = EXCLUDED.total_packets,
        avg_packets_per_mapping = EXCLUDED.avg_packets_per_mapping,
        total_mappings = EXCLUDED.total_mappings,
        storage_bytes = EXCLUDED.storage_bytes;
    
    cutoff_time := EXTRACT(EPOCH FROM NOW() - INTERVAL '24 hours')::bigint;
    
    LOOP
        -- Delete in batches
        WITH batch AS (
            SELECT id, last_seen
            FROM subnet_location_map
            WHERE last_seen < cutoff_time
            OR packet_count < p_min_packet_count
            LIMIT p_batch_size
            FOR UPDATE SKIP LOCKED
        )
        DELETE FROM subnet_location_map m
        USING batch b
        WHERE m.id = b.id AND m.last_seen = b.last_seen;
        
        GET DIAGNOSTICS deleted = ROW_COUNT;
        total_deleted := total_deleted + deleted;
        
        EXIT WHEN deleted < p_batch_size;
        COMMIT;
    END LOOP;
END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION cleanup_subnet_mappings(bigint, integer) OWNER TO pcapuser;

-- Create function to clean up old subnet mappings
CREATE FUNCTION cleanup_old_subnet_mappings() RETURNS void AS $$
DECLARE
    cutoff_time bigint;
BEGIN
    -- Set cutoff time to 24 hours ago
    cutoff_time := EXTRACT(EPOCH FROM NOW())::bigint - (24 * 3600);
    
    -- Delete old mappings that are older than 24 hours
    DELETE FROM subnet_location_map
    WHERE last_seen < cutoff_time;
    
    -- Run partition management to clean up old partitions
    PERFORM manage_subnet_partitions();
END;
$$ LANGUAGE plpgsql;
ALTER FUNCTION cleanup_old_subnet_mappings() OWNER TO pcapuser;

-- Create initial partition
SELECT manage_subnet_partitions();