-- PostgreSQL dumped from database version 16.6 (Ubuntu 16.6-0ubuntu0.24.04.1)
-- Part 4/4 - Post-locations constraints

-- Add foreign key constraints to subnet_location_map
ALTER TABLE public.subnet_location_map
    ADD CONSTRAINT subnet_location_map_src_location_fkey 
    FOREIGN KEY (src_location) REFERENCES locations(site);

ALTER TABLE public.subnet_location_map
    ADD CONSTRAINT subnet_location_map_dst_location_fkey 
    FOREIGN KEY (dst_location) REFERENCES locations(site);

-- Create indexes for better join performance
CREATE INDEX idx_subnet_location_map_src_loc ON public.subnet_location_map(src_location);
CREATE INDEX idx_subnet_location_map_dst_loc ON public.subnet_location_map(dst_location);

-- Create indexes for subnet lookups
CREATE INDEX idx_subnet_location_map_src_subnet ON public.subnet_location_map USING gist (src_subnet inet_ops);
CREATE INDEX idx_subnet_location_map_dst_subnet ON public.subnet_location_map USING gist (dst_subnet inet_ops);