-- PostgreSQL database version 16.6
-- All SQL files are used to load all database entities for a fresh installation and are part of one continuous flow, only split to make it easier to read and maintain.
-- This is Part 2 of 5


-- Name: maintenance_operations_id_seq; Type: SEQUENCE; Schema: public; Owner: pcapuser
CREATE SEQUENCE public.maintenance_operations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.maintenance_operations_id_seq OWNER TO pcapuser;

-- Name: sensor_health_summary_id_seq; Type: SEQUENCE; Schema: public; Owner: pcapuser
CREATE SEQUENCE public.sensor_health_summary_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.sensor_health_summary_id_seq OWNER TO pcapuser;

-- Name: sensor_status_history_id_seq; Type: SEQUENCE; Schema: public; Owner: pcapuser
CREATE SEQUENCE public.sensor_status_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.sensor_status_history_id_seq OWNER TO pcapuser;

-- Then create base tables that don't depend on other tables
-- Name: locations; Type: TABLE; Schema: public; Owner: pcapuser
CREATE TABLE public.locations (
    site varchar(50) NOT NULL,
    name text NOT NULL,
    latitude double precision,
    longitude double precision,
    description text,
    color text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE public.locations OWNER TO pcapuser;

CREATE TABLE public.maintenance_operations (
    id integer DEFAULT nextval('public.maintenance_operations_id_seq'::regclass) NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    operation_type character varying(50) NOT NULL,
    duration_seconds integer,
    items_processed integer,
    items_removed integer,
    details jsonb
);

ALTER TABLE public.maintenance_operations OWNER TO pcapuser;

-- Name: sensors; Type: TABLE; Schema: public; Owner: pcapuser
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
    version character varying(20)
);

ALTER TABLE public.sensors OWNER TO pcapuser;

-- Name: sensor_status_history; Type: TABLE; Schema: public; Owner: pcapuser
CREATE TABLE public.sensor_status_history (
    id integer DEFAULT nextval('public.sensor_status_history_id_seq'::regclass) NOT NULL,
    sensor_fqdn character varying(255) NOT NULL,
    sensor_port integer NOT NULL,
    old_status public.sensor_status,
    new_status public.sensor_status NOT NULL,
    change_time timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE public.sensor_status_history OWNER TO pcapuser;

-- Name: sensor_health_summary; Type: TABLE; Schema: public; Owner: pcapuser
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
    performance_metrics jsonb
);

ALTER TABLE public.sensor_health_summary OWNER TO pcapuser;

-- Name: subnet_location_map; Type: TABLE; Schema: public; Owner: pcapuser
CREATE TABLE public.subnet_location_map (
    src_subnet cidr NOT NULL,
    dst_subnet cidr NOT NULL,
    src_location varchar(50) NOT NULL,
    dst_location varchar(50) NOT NULL,
    first_seen bigint NOT NULL,
    last_seen bigint NOT NULL,
    packet_count bigint DEFAULT 1 NOT NULL
)
PARTITION BY RANGE (last_seen);

ALTER TABLE public.subnet_location_map OWNER TO pcapuser;

-- Create views after all required tables exist
-- Name: network_traffic_summary; Type: MATERIALIZED VIEW; Schema: public; Owner: pcapuser
CREATE MATERIALIZED VIEW public.network_traffic_summary AS
SELECT 
    slm.src_location,
    slm.dst_location,
    COUNT(DISTINCT slm.src_subnet) + COUNT(DISTINCT slm.dst_subnet) AS unique_subnets,
    SUM(slm.packet_count) AS total_packets,
    MIN(slm.first_seen) AS earliest_seen,
    MAX(slm.last_seen) AS latest_seen
FROM public.subnet_location_map slm
JOIN public.locations src ON src.site = slm.src_location
JOIN public.locations dst ON dst.site = slm.dst_location
WHERE src.site != dst.site  -- Exclude self-connections
GROUP BY slm.src_location, slm.dst_location
WITH NO DATA;

ALTER MATERIALIZED VIEW public.network_traffic_summary OWNER TO pcapuser;

-- Sequence ownership
ALTER SEQUENCE public.maintenance_operations_id_seq OWNED BY public.maintenance_operations.id;
ALTER SEQUENCE public.sensor_health_summary_id_seq OWNED BY public.sensor_health_summary.id;
