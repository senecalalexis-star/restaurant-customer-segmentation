-- Table: public.week

-- DROP TABLE IF EXISTS public.week;

CREATE TABLE IF NOT EXISTS public.week
(
    week_id integer NOT NULL GENERATED ALWAYS AS IDENTITY ( INCREMENT 1 START 1 MINVALUE 1 MAXVALUE 2147483647 CACHE 1 ),
    week_start timestamp without time zone NOT NULL,
    week_end timestamp without time zone NOT NULL,
    year integer NOT NULL,
    iso_year integer NOT NULL,
    month integer NOT NULL,
    CONSTRAINT week_pkey PRIMARY KEY (week_id)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.week
    OWNER to postgres;
