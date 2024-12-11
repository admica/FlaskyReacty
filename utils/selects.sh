#!/bin/bash

echo "[ Count rows in each subnet_location_map partition ]"
psql -U pcapuser -d pcapdb -c """SELECT 
    child.relname as partition_name,
    (SELECT count(*) FROM ONLY public.subnet_location_map) as row_count
    FROM pg_inherits
    JOIN pg_class child ON pg_inherits.inhrelid = child.oid
    JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
    WHERE parent.relname = 'subnet_location_map'
    ORDER BY child.relname;"""

