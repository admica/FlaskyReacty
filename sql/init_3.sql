-- PostgreSQL dumped from database version 16.6 (Ubuntu 16.6-0ubuntu0.24.04.1)
-- Part 3/3

-- Name: subnet_location_map_1733529600; Type: TABLE; Schema: public; Owner: pcapuser
CREATE TABLE public.subnet_location_map_1733529600 (
    src_subnet cidr NOT NULL,
    dst_subnet cidr NOT NULL,
    src_location varchar(50) NOT NULL,
    dst_location varchar(50) NOT NULL,
    first_seen bigint NOT NULL,
    last_seen bigint NOT NULL,
    packet_count bigint DEFAULT 1 NOT NULL
);

ALTER TABLE public.subnet_location_map_1733529600 OWNER TO pcapuser;

-- Name: subnet_location_map_1733533200; Type: TABLE; Schema: public; Owner: pcapuser
CREATE TABLE public.subnet_location_map_1733533200 (
    src_subnet cidr NOT NULL,
    dst_subnet cidr NOT NULL,
    src_location varchar(50) NOT NULL,
    dst_location varchar(50) NOT NULL,
    first_seen bigint NOT NULL,
    last_seen bigint NOT NULL,
    packet_count bigint DEFAULT 1 NOT NULL
);

ALTER TABLE public.subnet_location_map_1733533200 OWNER TO pcapuser;

-- Name: user_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: pcapuser
CREATE SEQUENCE public.user_sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.user_sessions_id_seq OWNER TO pcapuser;

-- Name: user_sessions; Type: TABLE; Schema: public; Owner: pcapuser
CREATE TABLE public.user_sessions (
    id integer DEFAULT nextval('public.user_sessions_id_seq'::regclass) NOT NULL,
    username character varying(255) NOT NULL,
    session_token character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    expires_at timestamp with time zone NOT NULL
);

ALTER TABLE public.user_sessions OWNER TO pcapuser;

-- Name: subnet_location_map_1733529600; Type: TABLE ATTACH; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.subnet_location_map ATTACH PARTITION public.subnet_location_map_1733529600 FOR VALUES FROM ('1733529600') TO ('1733533200');

-- Name: subnet_location_map_1733533200; Type: TABLE ATTACH; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.subnet_location_map ATTACH PARTITION public.subnet_location_map_1733533200 FOR VALUES FROM ('1733533200') TO ('1733536800');

-- Name: maintenance_operations id; Type: DEFAULT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.maintenance_operations ALTER COLUMN id SET DEFAULT nextval('public.maintenance_operations_id_seq'::regclass);

-- Name: sensor_health_summary id; Type: DEFAULT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.sensor_health_summary ALTER COLUMN id SET DEFAULT nextval('public.sensor_health_summary_id_seq'::regclass);

-- Name: admin_audit_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: pcapuser
SELECT pg_catalog.setval('public.admin_audit_log_id_seq', 1, false);

-- Name: job_status_history_id_seq; Type: SEQUENCE SET; Schema: public; Owner: pcapuser
SELECT pg_catalog.setval('public.job_status_history_id_seq', 1, false);

-- Name: jobs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: pcapuser
SELECT pg_catalog.setval('public.jobs_id_seq', 1, false);

-- Name: maintenance_operations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: pcapuser
SELECT pg_catalog.setval('public.maintenance_operations_id_seq', 1, false);

-- Name: sensor_health_summary_id_seq; Type: SEQUENCE SET; Schema: public; Owner: pcapuser
SELECT pg_catalog.setval('public.sensor_health_summary_id_seq', 1, false);

-- Name: sensor_status_history_id_seq; Type: SEQUENCE SET; Schema: public; Owner: pcapuser
SELECT pg_catalog.setval('public.sensor_status_history_id_seq', 1, false);

-- Name: user_sessions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: pcapuser
SELECT pg_catalog.setval('public.user_sessions_id_seq', 1, false);

-- Name: admin_audit_log admin_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.admin_audit_log
    ADD CONSTRAINT admin_audit_log_pkey PRIMARY KEY (id);

-- Name: admin_users admin_users_pkey; Type: CONSTRAINT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.admin_users
    ADD CONSTRAINT admin_users_pkey PRIMARY KEY (username);

-- Name: devices devices_pkey; Type: CONSTRAINT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.devices
    ADD CONSTRAINT devices_pkey PRIMARY KEY (sensor, port, name);

-- Name: devices devices_sensor_name_key; Type: CONSTRAINT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.devices
    ADD CONSTRAINT devices_sensor_name_key UNIQUE (sensor, name);

-- Name: job_status_history job_status_history_pkey; Type: CONSTRAINT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.job_status_history
    ADD CONSTRAINT job_status_history_pkey PRIMARY KEY (id);

-- Name: jobs jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_pkey PRIMARY KEY (id);

-- Name: locations locations_pkey; Type: CONSTRAINT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.locations
    ADD CONSTRAINT locations_pkey PRIMARY KEY (site);

-- Name: maintenance_operations maintenance_operations_pkey; Type: CONSTRAINT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.maintenance_operations
    ADD CONSTRAINT maintenance_operations_pkey PRIMARY KEY (id);

-- Name: sensor_health_summary sensor_health_summary_pkey; Type: CONSTRAINT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.sensor_health_summary
    ADD CONSTRAINT sensor_health_summary_pkey PRIMARY KEY (id);

-- Name: sensor_status_history sensor_status_history_pkey; Type: CONSTRAINT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.sensor_status_history
    ADD CONSTRAINT sensor_status_history_pkey PRIMARY KEY (id);

-- Name: sensors sensors_pkey; Type: CONSTRAINT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.sensors
    ADD CONSTRAINT sensors_pkey PRIMARY KEY (name);

-- Name: subnet_location_map subnet_location_map_pkey; Type: CONSTRAINT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.subnet_location_map
    ADD CONSTRAINT subnet_location_map_pkey PRIMARY KEY (last_seen, src_subnet, dst_subnet, src_location, dst_location);

-- Name: subnet_location_map_1733529600 subnet_location_map_1733529600_pkey; Type: CONSTRAINT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.subnet_location_map_1733529600
    ADD CONSTRAINT subnet_location_map_1733529600_pkey PRIMARY KEY (last_seen, src_subnet, dst_subnet, src_location, dst_location);

-- Name: subnet_location_map_1733533200 subnet_location_map_1733533200_pkey; Type: CONSTRAINT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.subnet_location_map_1733533200
    ADD CONSTRAINT subnet_location_map_1733533200_pkey PRIMARY KEY (last_seen, src_subnet, dst_subnet, src_location, dst_location);

-- Name: user_sessions user_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_pkey PRIMARY KEY (id);

-- Name: user_sessions user_sessions_session_token_key; Type: CONSTRAINT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_session_token_key UNIQUE (session_token);

-- Name: subnet_location_map_1733529600_pkey; Type: INDEX ATTACH; Schema: public; Owner: pcapuser
ALTER INDEX public.subnet_location_map_pkey ATTACH PARTITION public.subnet_location_map_1733529600_pkey;

-- Name: subnet_location_map_1733533200_pkey; Type: INDEX ATTACH; Schema: public; Owner: pcapuser
ALTER INDEX public.subnet_location_map_pkey ATTACH PARTITION public.subnet_location_map_1733533200_pkey;

-- Name: admin_users admin_changes_trigger; Type: TRIGGER; Schema: public; Owner: pcapuser
CREATE TRIGGER admin_changes_trigger AFTER INSERT OR DELETE ON public.admin_users FOR EACH ROW EXECUTE FUNCTION public.log_admin_changes();

-- Name: subnet_location_map ensure_partition_exists; Type: TRIGGER; Schema: public; Owner: pcapuser
CREATE TRIGGER ensure_partition_exists BEFORE INSERT ON public.subnet_location_map FOR EACH ROW EXECUTE FUNCTION public.create_partition_trigger();

-- Name: sensors sensor_status_change_trigger; Type: TRIGGER; Schema: public; Owner: pcapuser
CREATE TRIGGER sensor_status_change_trigger AFTER UPDATE ON public.sensors FOR EACH ROW WHEN ((old.status IS DISTINCT FROM new.status)) EXECUTE FUNCTION public.log_sensor_status_change();

-- Name: job_status_history job_status_history_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: pcapuser
ALTER TABLE ONLY public.job_status_history
    ADD CONSTRAINT job_status_history_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.jobs(id) ON DELETE CASCADE;
