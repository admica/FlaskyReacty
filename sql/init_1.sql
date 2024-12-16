-- PostgreSQL database version 16.6
-- All SQL files are used to load all database entities for a fresh installation and are part of one continuous flow.

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

-- Name: create_location_tables(text); Type: FUNCTION; Schema: public; Owner: pcapuser
CREATE FUNCTION public.create_location_tables(location text) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Create source subnet table
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS public."loc_src_%s" (
            subnet cidr NOT NULL,
            count bigint,
            first_seen bigint,
            last_seen bigint,
            sensor character varying(255) NOT NULL,
            device character varying(255) NOT NULL,
            CONSTRAINT "loc_src_%s_pkey" PRIMARY KEY (subnet, sensor, device)
        )', location, location);

    -- Create destination subnet table
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS public."loc_dst_%s" (
            subnet cidr NOT NULL,
            count bigint,
            first_seen bigint,
            last_seen bigint,
            sensor character varying(255) NOT NULL,
            device character varying(255) NOT NULL,
            CONSTRAINT "loc_dst_%s_pkey" PRIMARY KEY (subnet, sensor, device)
        )', location, location);

    -- Set ownership
    EXECUTE format('ALTER TABLE public."loc_src_%s" OWNER TO pcapuser', location);
    EXECUTE format('ALTER TABLE public."loc_dst_%s" OWNER TO pcapuser', location);
END;
$$;

ALTER FUNCTION public.create_location_tables(location text) OWNER TO pcapuser;

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
    added_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT admin_users_pkey PRIMARY KEY (username)
);

ALTER TABLE public.admin_users OWNER TO pcapuser;
