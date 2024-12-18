-- PostgreSQL database version 16.6
-- All SQL files are used to load all database entities for a fresh installation and are part of one continuous flow, only split to make it easier to read and maintain.

-- Name: job_status; Type: TYPE; Schema: public; Owner: pcapuser
CREATE TYPE public.job_status AS ENUM (
    'Submitted',
    'Running',
    'Merging',
    'Complete',
    'Partial Complete',
    'Failed',
    'Aborted'
);

ALTER TYPE public.job_status OWNER TO pcapuser;

-- Name: task_status; Type: TYPE; Schema: public; Owner: pcapuser
CREATE TYPE public.task_status AS ENUM (
    'Submitted',
    'Running',
    'Retrieving',
    'Complete',
    'Failed',
    'Skipped',
    'Aborted'
);

ALTER TYPE public.task_status OWNER TO pcapuser;

-- Name: jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: pcapuser
CREATE SEQUENCE public.jobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.jobs_id_seq OWNER TO pcapuser;

-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: pcapuser
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

ALTER FUNCTION public.update_updated_at_column() OWNER TO pcapuser;

-- Name: jobs; Type: TABLE; Schema: public; Owner: pcapuser
CREATE TABLE public.jobs (
    id integer DEFAULT nextval('public.jobs_id_seq'::regclass) NOT NULL,
    location varchar(50) NOT NULL,
    description text,
    src_ip inet,
    dst_ip inet,
    event_time timestamp with time zone,
    start_time timestamp with time zone,    -- PCAP search start boundary
    end_time timestamp with time zone,      -- PCAP search end boundary
    status public.job_status DEFAULT 'Submitted'::public.job_status NOT NULL,
    submitted_by character varying(255) NOT NULL,
    result_size character varying(20),
    result_path character varying(255),
    result_message text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    started_at timestamp with time zone,    -- When job processing began
    completed_at timestamp with time zone,  -- When job processing finished
    CONSTRAINT jobs_pkey PRIMARY KEY (id),
    CONSTRAINT jobs_location_fkey FOREIGN KEY (location) REFERENCES locations(site)
);

ALTER TABLE public.jobs OWNER TO pcapuser;

-- Name: tasks; Type: TABLE; Schema: public; Owner: pcapuser
CREATE TABLE public.tasks (
    id integer NOT NULL GENERATED ALWAYS AS IDENTITY,
    job_id integer NOT NULL,
    task__id integer NOT NULL,
    sensor character varying(255) NOT NULL,
    status public.task_status DEFAULT 'Submitted'::public.task_status NOT NULL,
    pcap_size character varying(20),
    temp_path character varying(255),
    result_message text,
    start_time timestamp with time zone,    -- PCAP search start boundary
    end_time timestamp with time zone,      -- PCAP search end boundary
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    started_at timestamp with time zone,    -- When task processing began
    completed_at timestamp with time zone,  -- When task processing finished
    CONSTRAINT tasks_pkey PRIMARY KEY (id),
    CONSTRAINT tasks_job_fkey FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    CONSTRAINT tasks_sensor_fkey FOREIGN KEY (sensor) REFERENCES sensors(name)
);

ALTER TABLE public.tasks OWNER TO pcapuser;

-- Name: update_jobs_updated_at; Type: TRIGGER; Schema: public; Owner: pcapuser
CREATE TRIGGER update_jobs_updated_at
    BEFORE UPDATE ON public.jobs
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- Name: update_tasks_updated_at; Type: TRIGGER; Schema: public; Owner: pcapuser
CREATE TRIGGER update_tasks_updated_at
    BEFORE UPDATE ON public.tasks
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- Create indexes for common queries
CREATE INDEX idx_jobs_status ON public.jobs(status);
CREATE INDEX idx_jobs_location ON public.jobs(location);
CREATE INDEX idx_tasks_job_id ON public.tasks(job_id);
CREATE INDEX idx_tasks_status ON public.tasks(status);
CREATE INDEX idx_tasks_sensor ON public.tasks(sensor);

-- Set sequence ownership
ALTER SEQUENCE public.jobs_id_seq OWNED BY public.jobs.id;
