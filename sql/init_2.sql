-- PostgreSQL database version 16.6
-- All SQL files are used to load all database entities for a fresh installation and are part of one continuous flow.
-- This is Part 2 of 6: Base Tables and Sequences

-- Create sequences
CREATE SEQUENCE public.maintenance_operations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.maintenance_operations_id_seq OWNER TO pcapuser;

CREATE SEQUENCE public.sensor_health_summary_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.sensor_health_summary_id_seq OWNER TO pcapuser;

CREATE SEQUENCE public.sensor_status_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.sensor_status_history_id_seq OWNER TO pcapuser;

-- Create base tables
CREATE TABLE public.locations (
    site varchar(50) NOT NULL,
    name text NOT NULL,
    latitude double precision,
    longitude double precision,
    description text,
    color text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT locations_pkey PRIMARY KEY (site)
);

ALTER TABLE public.locations OWNER TO pcapuser;

CREATE TABLE public.maintenance_operations (
    id integer DEFAULT nextval('public.maintenance_operations_id_seq'::regclass) NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    operation_type character varying(50) NOT NULL,
    duration_seconds integer,
    items_processed integer,
    items_removed integer,
    details jsonb,
    CONSTRAINT maintenance_operations_pkey PRIMARY KEY (id)
);

ALTER TABLE public.maintenance_operations OWNER TO pcapuser;

CREATE TABLE public.sensors (
    name character varying(255) NOT NULL,
    status public.sensor_status DEFAULT 'Offline'::public.sensor_status NOT NULL,
    last_seen timestamp with time zone,
    fqdn character varying(255),
    location character varying(255),
    last_update timestamp with time zone,
    pcap_avail integer DEFAULT 0,
    totalspace character varying(20) DEFAULT '0'::character varying,
    usedspace character varying(20) DEFAULT '0'::character varying,
    version character varying(20),
    CONSTRAINT sensors_pkey PRIMARY KEY (name)
);

ALTER TABLE public.sensors OWNER TO pcapuser;

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
    stats_date timestamp with time zone,
    CONSTRAINT devices_pkey PRIMARY KEY (sensor, port, name),
    CONSTRAINT devices_sensor_name_key UNIQUE (sensor, name),
    CONSTRAINT devices_sensor_fkey FOREIGN KEY (sensor) REFERENCES sensors(name) ON DELETE CASCADE
);

ALTER TABLE public.devices OWNER TO pcapuser;

CREATE TABLE public.sensor_status_history (
    id integer DEFAULT nextval('public.sensor_status_history_id_seq'::regclass) NOT NULL,
    sensor_fqdn character varying(255) NOT NULL,
    sensor_port integer NOT NULL,
    old_status public.sensor_status,
    new_status public.sensor_status NOT NULL,
    change_time timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT sensor_status_history_pkey PRIMARY KEY (id)
);

ALTER TABLE public.sensor_status_history OWNER TO pcapuser;

CREATE TABLE public.sensor_health_summary (
    id integer DEFAULT nextval('public.sensor_health_summary_id_seq'::regclass) NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    duration_seconds integer,
    sensors_checked integer NOT NULL,
    sensors_online integer NOT NULL,
    sensors_offline integer NOT NULL,
    sensors_degraded integer NOT NULL,
    devices_total integer NOT NULL,
    devices_online integer NOT NULL,
    devices_offline integer NOT NULL,
    devices_degraded integer NOT NULL,
    avg_pcap_minutes integer,
    avg_disk_usage_pct integer,
    errors jsonb,
    performance_metrics jsonb,
    CONSTRAINT sensor_health_summary_pkey PRIMARY KEY (id)
);

ALTER TABLE public.sensor_health_summary OWNER TO pcapuser;

-- Set sequence ownership
ALTER SEQUENCE public.maintenance_operations_id_seq OWNED BY public.maintenance_operations.id;
ALTER SEQUENCE public.sensor_health_summary_id_seq OWNED BY public.sensor_health_summary.id;
ALTER SEQUENCE public.sensor_status_history_id_seq OWNED BY public.sensor_status_history.id;
