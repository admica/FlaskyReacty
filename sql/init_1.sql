-- PostgreSQL dumped from database version 16.6 (Ubuntu 16.6-0ubuntu0.24.04.1)
-- Part 1/3

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;
ALTER SCHEMA public OWNER TO pcapuser;

-- Name: job_status; Type: TYPE; Schema: public; Owner: pcapuser
CREATE TYPE public.job_status AS ENUM (
    'Submitted',
    'Running',
    'Retrieving',
    'Complete',
    'Incomplete',
    'Cancelled'
);

ALTER TYPE public.job_status OWNER TO pcapuser;

-- Name: sensor_status; Type: TYPE; Schema: public; Owner: pcapuser
CREATE TYPE public.sensor_status AS ENUM (
    'Online',
    'Offline',
    'Maintenance',
    'Busy',
    'Degraded'
);

ALTER TYPE public.sensor_status OWNER TO pcapuser;

-- Name: device_status; Type: TYPE; Schema: public; Owner: pcapuser
CREATE TYPE public.device_status AS ENUM (
    'Online',
    'Offline',
    'Degraded'
);

ALTER TYPE public.device_status OWNER TO pcapuser;

-- Name: cleanup_old_subnet_mappings(); Type: FUNCTION; Schema: public; Owner: pcapuser
CREATE FUNCTION public.cleanup_old_subnet_mappings() RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    cutoff_time bigint;
    partition_name text;
    rows_deleted integer;
BEGIN
    cutoff_time := EXTRACT(EPOCH FROM NOW() - INTERVAL '24 hours')::bigint;

    -- Delete old partitions
    FOR partition_name IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE tablename LIKE 'subnet_location_map_%'
        AND split_part(tablename, '_', 4)::bigint < cutoff_time
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS %I', partition_name);
    END LOOP;

    -- Log the cleanup operation
    INSERT INTO maintenance_operations (
        timestamp,
        operation_type,
        duration_seconds,
        items_processed,
        items_removed,
        details
    ) VALUES (
        NOW(),
        'cleanup_subnet_mappings',
        0,
        0,  -- We don't track number of partitions in this version
        0,
        jsonb_build_object(
            'action', 'cleanup_subnet_mappings',
            'cutoff_time', cutoff_time
        )
    );
END;
$$;

ALTER FUNCTION public.cleanup_old_subnet_mappings() OWNER TO pcapuser;

-- Name: create_hourly_partition(bigint); Type: FUNCTION; Schema: public; Owner: pcapuser
CREATE FUNCTION public.create_hourly_partition(partition_timestamp bigint) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    partition_name text;
    start_range bigint;
    end_range bigint;
BEGIN
    -- Calculate the hour-aligned timestamp
    start_range := partition_timestamp - (partition_timestamp % 3600);
    end_range := start_range + 3600;
    partition_name := 'subnet_location_map_' || start_range::text;

    -- Create the partition if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = partition_name) THEN
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF subnet_location_map
            FOR VALUES FROM (%L) TO (%L)',
            partition_name, start_range, end_range
        );
        -- Set ownership
        EXECUTE format('ALTER TABLE %I OWNER TO pcapuser', partition_name);
    END IF;
END;
$$;

ALTER FUNCTION public.create_hourly_partition(partition_timestamp bigint) OWNER TO pcapuser;

-- Name: create_location_tables(text); Type: FUNCTION; Schema: public; Owner: pcapuser
CREATE FUNCTION public.create_location_tables(location text) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Create source subnet table
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS public.loc_src_%I (
            subnet cidr NOT NULL,
            count bigint,
            first_seen bigint,
            last_seen bigint,
            sensor character varying(255) NOT NULL,
            device character varying(255) NOT NULL,
            CONSTRAINT loc_src_%I_pkey PRIMARY KEY (subnet, sensor, device)
        )', location, location);

    -- Create destination subnet table
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS public.loc_dst_%I (
            subnet cidr NOT NULL,
            count bigint,
            first_seen bigint,
            last_seen bigint,
            sensor character varying(255) NOT NULL,
            device character varying(255) NOT NULL,
            CONSTRAINT loc_dst_%I_pkey PRIMARY KEY (subnet, sensor, device)
        )', location, location);

    -- Set ownership
    EXECUTE format('ALTER TABLE public.loc_src_%I OWNER TO pcapuser', location);
    EXECUTE format('ALTER TABLE public.loc_dst_%I OWNER TO pcapuser', location);
END;
$$;

ALTER FUNCTION public.create_location_tables(location text) OWNER TO pcapuser;

-- Name: create_partition_trigger(); Type: FUNCTION; Schema: public; Owner: pcapuser
CREATE FUNCTION public.create_partition_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    PERFORM create_hourly_partition(NEW.last_seen);
    RETURN NEW;
END;
$$;

ALTER FUNCTION public.create_partition_trigger() OWNER TO pcapuser;

-- Name: log_admin_changes(); Type: FUNCTION; Schema: public; Owner: pcapuser
CREATE FUNCTION public.log_admin_changes() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO admin_audit_log (action, username, changed_by)
        VALUES ('ADD', NEW.username, NEW.added_by);
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO admin_audit_log (action, username, changed_by)
        VALUES ('REMOVE', OLD.username, current_user);
    END IF;
    RETURN NULL;
END;
$$;

ALTER FUNCTION public.log_admin_changes() OWNER TO pcapuser;

-- Name: log_sensor_status_change(); Type: FUNCTION; Schema: public; Owner: pcapuser
CREATE FUNCTION public.log_sensor_status_change() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.status != OLD.status THEN
        INSERT INTO sensor_status_history (
            sensor_fqdn,
            sensor_port,
            old_status,
            new_status
        )
        SELECT
            NEW.fqdn,
            port,
            OLD.status,
            NEW.status
        FROM devices
        WHERE sensor = NEW.name;
    END IF;
    RETURN NEW;
END;
$$;

ALTER FUNCTION public.log_sensor_status_change() OWNER TO pcapuser;

-- Name: refresh_network_traffic_summary(); Type: FUNCTION; Schema: public; Owner: pcapuser
CREATE FUNCTION public.refresh_network_traffic_summary() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Try concurrent refresh first
    BEGIN
        REFRESH MATERIALIZED VIEW CONCURRENTLY network_traffic_summary;
    EXCEPTION WHEN OTHERS THEN
        -- Fall back to regular refresh if concurrent fails
        REFRESH MATERIALIZED VIEW network_traffic_summary;
    END;
END;
$$;

ALTER FUNCTION public.refresh_network_traffic_summary() OWNER TO pcapuser;

-- Name: admin_audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: pcapuser
CREATE SEQUENCE public.admin_audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.admin_audit_log_id_seq OWNER TO pcapuser;

SET default_tablespace = '';

SET default_table_access_method = heap;

-- Name: admin_audit_log; Type: TABLE; Schema: public; Owner: pcapuser
CREATE TABLE public.admin_audit_log (
    id integer DEFAULT nextval('public.admin_audit_log_id_seq'::regclass) NOT NULL,
    action character varying(50) NOT NULL,
    username character varying(255) NOT NULL,
    changed_by character varying(255) NOT NULL,
    change_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE public.admin_audit_log OWNER TO pcapuser;

-- Name: admin_users; Type: TABLE; Schema: public; Owner: pcapuser
CREATE TABLE public.admin_users (
    username character varying(255) NOT NULL,
    added_by character varying(255) NOT NULL,
    added_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE public.admin_users OWNER TO pcapuser;

-- Name: devices; Type: TABLE; Schema: public; Owner: pcapuser
CREATE TABLE public.devices (
    sensor character varying(255) NOT NULL,
    port integer NOT NULL,
    name character varying(255) NOT NULL,
    fqdn character varying(255),
    description text,
    device_type character varying(50) NOT NULL,
    status public.device_status DEFAULT 'Offline'::public.device_status NOT NULL,
    last_checked timestamp with time zone,
    runtime bigint DEFAULT 0,
    workers integer DEFAULT 0,
    src_subnets integer DEFAULT 0,
    dst_subnets integer DEFAULT 0,
    uniq_subnets integer DEFAULT 0,
    avg_idle_time integer DEFAULT 0,
    avg_work_time integer DEFAULT 0,
    overflows integer DEFAULT 0,
    size character varying(50) DEFAULT '0'::character varying,
    version character varying(50),
    output_path character varying(255),
    proc text,
    stats_date timestamp with time zone
);

ALTER TABLE public.devices OWNER TO pcapuser;
