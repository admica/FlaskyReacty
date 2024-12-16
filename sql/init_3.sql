-- PostgreSQL database version 16.6
-- All SQL files are used to load all database entities for a fresh installation and are part of one continuous flow.

-- Create user sessions sequence and table
CREATE SEQUENCE public.user_sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.user_sessions_id_seq OWNER TO pcapuser;

CREATE TABLE public.user_sessions (
    id integer DEFAULT nextval('public.user_sessions_id_seq'::regclass) NOT NULL,
    username character varying(255) NOT NULL,
    session_token character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    expires_at timestamp with time zone NOT NULL,
    CONSTRAINT user_sessions_pkey PRIMARY KEY (id),
    CONSTRAINT user_sessions_session_token_key UNIQUE (session_token)
);

ALTER TABLE public.user_sessions OWNER TO pcapuser;

-- Set sequence values
SELECT pg_catalog.setval('public.admin_audit_log_id_seq', 1, false);
SELECT pg_catalog.setval('public.maintenance_operations_id_seq', 1, false);
SELECT pg_catalog.setval('public.sensor_health_summary_id_seq', 1, false);
SELECT pg_catalog.setval('public.sensor_status_history_id_seq', 1, false);
SELECT pg_catalog.setval('public.user_sessions_id_seq', 1, false);

-- Create triggers
CREATE TRIGGER admin_changes_trigger 
    AFTER INSERT OR DELETE ON public.admin_users 
    FOR EACH ROW 
    EXECUTE FUNCTION public.log_admin_changes();

CREATE TRIGGER sensor_status_change_trigger 
    AFTER UPDATE ON public.sensors 
    FOR EACH ROW 
    WHEN ((old.status IS DISTINCT FROM new.status)) 
    EXECUTE FUNCTION public.log_sensor_status_change();
