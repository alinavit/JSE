--
-- PostgreSQL database dump
--

-- Dumped from database version 14.1
-- Dumped by pg_dump version 14.1

-- Started on 2024-07-21 21:11:29

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

--
-- TOC entry 3398 (class 1262 OID 25234)
-- Name: jse; Type: DATABASE; Schema: -; Owner: postgres
--

CREATE DATABASE jse WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE = 'English_United States.1250';


ALTER DATABASE jse OWNER TO postgres;

\connect jse

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

--
-- TOC entry 235 (class 1255 OID 28022)
-- Name: find_duplicate_positions(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.find_duplicate_positions() RETURNS TABLE(pos_id bigint)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    WITH cte AS (
        SELECT
            position_id,
            DENSE_RANK() OVER (PARTITION BY title, company_name ORDER BY url) AS dense_rank
        FROM
            positions_test
        WHERE
            company_name || title IN (
                SELECT company_name || title
                FROM positions
                GROUP BY company_name, title
                HAVING COUNT(*) > 1
            )
        ORDER BY company_name, title
    )
    SELECT position_id as pos_id FROM cte WHERE dense_rank > 1;
END;
$$;


ALTER FUNCTION public.find_duplicate_positions() OWNER TO postgres;

--
-- TOC entry 246 (class 1255 OID 29554)
-- Name: latest_data_raw_bronze_to_silver(); Type: PROCEDURE; Schema: public; Owner: postgres
--

CREATE PROCEDURE public.latest_data_raw_bronze_to_silver()
    LANGUAGE plpgsql
    AS $$
---silver table contains only data of latest date_registered
--silver table make words more generic using table param_translate
DECLARE
rec RECORD;
BEGIN
	TRUNCATE TABLE positions_silver;
	
	insert into positions_silver select * from positions;
    --where date_registered = (select max(date_registered) from positions);
	
	
	call p_drop_duplicate_positions_silver();
	
	UPDATE positions_silver SET type_of_work = TRIM(type_of_work);
	UPDATE positions_silver SET experience = TRIM(experience);
	UPDATE positions_silver SET employment_type = TRIM(employment_type);
	UPDATE positions_silver SET operating_mode = TRIM(operating_mode);
	
	FOR rec IN SELECT pkey, pvalue FROM param_translate LOOP
        UPDATE positions_silver
        SET type_of_work = rec.pvalue
        WHERE type_of_work = rec.pkey;
		
		UPDATE positions_silver
        SET experience = rec.pvalue
        WHERE experience = rec.pkey;
		
		UPDATE positions_silver
        SET employment_type = rec.pvalue
        WHERE employment_type = rec.pkey;
		
		UPDATE positions_silver
        SET operating_mode = rec.pvalue
        WHERE operating_mode = rec.pkey;		
    END LOOP;
	
END;
$$;


ALTER PROCEDURE public.latest_data_raw_bronze_to_silver() OWNER TO postgres;

--
-- TOC entry 247 (class 1255 OID 51831)
-- Name: p_collect_key_words(); Type: PROCEDURE; Schema: public; Owner: postgres
--

CREATE PROCEDURE public.p_collect_key_words()
    LANGUAGE plpgsql
    AS $$

DECLARE
    v_keys VARCHAR(255); 
    v_position_id INTEGER;
    v_description VARCHAR;
	v_row RECORD;
BEGIN
    FOR v_row IN
        SELECT POSITION_ID, description FROM POSITIONS WHERE k_words_desc IS NULL
    LOOP
        v_position_id := v_row.POSITION_ID;
        v_description := v_row.description;
        
        v_keys := '';
        
        IF lower(v_description) LIKE '%sql%' THEN
            v_keys := v_keys || 'sql,';
        END IF;
        
        IF lower(v_description) LIKE '%databricks%' THEN
            v_keys := v_keys || 'databricks,';
        END IF;
        
        IF lower(v_description) LIKE '%python%' THEN
            v_keys := v_keys || 'python,';
        END IF;
		
        IF lower(v_description) LIKE '%azure data factory%'  OR lower(v_description) LIKE '%adf%' THEN
            v_keys := v_keys || 'ADF,';
        END IF;		
        
        IF lower(v_description) LIKE '%migration%' THEN
            v_keys := v_keys || 'migration,';
        END IF;
        
        IF lower(v_description) LIKE '%spark%' THEN
            v_keys := v_keys || 'spark,';
        END IF;

        IF lower(v_description) LIKE '%higher education%' THEN
            v_keys := v_keys || 'education,';
        END IF;
		
        IF lower(v_description) LIKE '%abgeschlossenes studium%' THEN
            v_keys := v_keys || 'education,';
        END IF;
		
		IF lower(v_description) LIKE '%wykształcenie%' THEN
            v_keys := v_keys || 'education,';
        END IF;
        
        IF v_keys = '' THEN
            v_keys := 'none';
        ELSE
            v_keys := rtrim(v_keys, ',');
        END IF;
        
        UPDATE POSITIONS SET k_words_desc = v_keys WHERE position_id = v_position_id;
    END LOOP;
    
END;
$$;


ALTER PROCEDURE public.p_collect_key_words() OWNER TO postgres;

--
-- TOC entry 244 (class 1255 OID 28028)
-- Name: p_drop_duplicate_positions_silver(); Type: PROCEDURE; Schema: public; Owner: postgres
--

CREATE PROCEDURE public.p_drop_duplicate_positions_silver()
    LANGUAGE plpgsql
    AS $$
BEGIN
    WITH cte AS (
        SELECT
            position_id,
            DENSE_RANK() OVER (PARTITION BY title, company_name ORDER BY url) AS dense_rank
        FROM
            positions_silver
        WHERE
            company_name || title IN (
                SELECT company_name || title
                FROM positions
                GROUP BY company_name, title
                HAVING COUNT(*) > 1
            )
        ORDER BY company_name, title
    )
    DELETE FROM positions_silver where position_id in 
	(
	SELECT position_id as pos_id FROM cte WHERE dense_rank > 1
	);
	
END;
$$;


ALTER PROCEDURE public.p_drop_duplicate_positions_silver() OWNER TO postgres;

--
-- TOC entry 248 (class 1255 OID 82930)
-- Name: p_populate_un_attractive_positions(); Type: PROCEDURE; Schema: public; Owner: postgres
--

CREATE PROCEDURE public.p_populate_un_attractive_positions()
    LANGUAGE plpgsql
    AS $$
DECLARE 
	rec RECORD;
	recdict RECORD;
BEGIN
    TRUNCATE TABLE unattractive_positions;
	
	--for every row in positions_silver
	FOR rec IN 
		SELECT position_id, key_words, company_name, title, experience FROM positions_silver WHERE date_registered = (SELECT MAX(DATE_REGISTERED) FROM POSITIONS_SILVER)
	LOOP
		--for every row in param_filter tables
		FOR recdict IN
			SELECT pkey, plogic, pcolumn FROM param_filter
		LOOP
			--populate table of unattractive positions
			IF lower(rec.key_words) LIKE '%'||LOWER(recdict.pkey)||'%' and recdict.pcolumn = 'key_words' and recdict.plogic  = 'exclude'
			THEN 
				INSERT INTO unattractive_positions VALUES(rec.position_id) ON CONFLICT(POSITION_ID) DO NOTHING;
			END IF;
			
			IF LOWER(rec.title) LIKE '%'||LOWER(recdict.pkey)||'%' and recdict.pcolumn = 'title' and recdict.plogic  = 'exclude'
			THEN 
				INSERT INTO unattractive_positions VALUES(rec.position_id) ON CONFLICT(POSITION_ID) DO NOTHING;
			END IF;			
	
			IF LOWER(rec.company_name) LIKE '%'||LOWER(recdict.pkey)||'%' and recdict.pcolumn = 'company' and recdict.plogic  = 'exclude'
			THEN 
				INSERT INTO unattractive_positions VALUES(rec.position_id) ON CONFLICT(POSITION_ID) DO NOTHING;
			END IF;		
			
			IF LOWER(rec.experience) LIKE '%'||LOWER(recdict.pkey)||'%' and recdict.pcolumn = 'experience' and recdict.plogic  = 'exclude'
			THEN 
				INSERT INTO unattractive_positions VALUES(rec.position_id) ON CONFLICT(POSITION_ID) DO NOTHING;
			END IF;	
			
		END LOOP;
	END LOOP;
	
END;
$$;


ALTER PROCEDURE public.p_populate_un_attractive_positions() OWNER TO postgres;

--
-- TOC entry 231 (class 1255 OID 30368)
-- Name: p_update_comp_ids_in_positions_silver(); Type: PROCEDURE; Schema: public; Owner: postgres
--

CREATE PROCEDURE public.p_update_comp_ids_in_positions_silver()
    LANGUAGE plpgsql
    AS $$
BEGIN
    
	UPDATE POSITIONS_SILVER silver
	SET COMPANY_ID = (
		SELECT asses.company_id
		FROM company_asses asses
		WHERE trim(LOWER(asses.company_name)) = trim(LOWER(silver.company_name))
	)
	WHERE EXISTS (
		SELECT 1
		FROM company_asses asses
		WHERE trim(LOWER(asses.company_name)) = trim(LOWER(silver.company_name))
	);
	
END;
$$;


ALTER PROCEDURE public.p_update_comp_ids_in_positions_silver() OWNER TO postgres;

--
-- TOC entry 245 (class 1255 OID 47448)
-- Name: update_status_rejected(integer, character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_status_rejected(val_position_id integer, val_comment character varying) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Update the status_end_date for the specified position_id
    UPDATE my_sendouts
    SET status_end_date = CURRENT_DATE
    WHERE position_id = val_position_id
      AND status_end_date IS NULL
      AND status != 'rejected';

    -- Insert the required columns into the same table for records with non-null status_end_date
    INSERT INTO my_sendouts (position_id, applied_date, status, status_start_date, status_end_date, hr_person, other_people, comments)
    SELECT position_id, applied_date, 'rejected', status_end_date, NULL, hr_person, other_people, val_comment
    FROM my_sendouts
    WHERE position_id = val_position_id
      AND status_end_date IS NOT NULL;
END;
$$;


ALTER FUNCTION public.update_status_rejected(val_position_id integer, val_comment character varying) OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 230 (class 1259 OID 87275)
-- Name: assessed_ids; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.assessed_ids (
    position_id integer,
    value integer
);


ALTER TABLE public.assessed_ids OWNER TO postgres;

--
-- TOC entry 3399 (class 0 OID 0)
-- Dependencies: 230
-- Name: TABLE assessed_ids; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.assessed_ids IS 'ids which I have reviewed already and left a comment. populated from csv using Python: populate_assessed_ids()';


--
-- TOC entry 216 (class 1259 OID 25318)
-- Name: company_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.company_id_seq
    START WITH 1000
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.company_id_seq OWNER TO postgres;

--
-- TOC entry 220 (class 1259 OID 25376)
-- Name: company_asses; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.company_asses (
    company_id bigint DEFAULT nextval('public.company_id_seq'::regclass) NOT NULL,
    company_name character varying(200) NOT NULL,
    score numeric,
    score_source character varying(200),
    company_size character varying(100),
    comment character varying(300)
);


ALTER TABLE public.company_asses OWNER TO postgres;

--
-- TOC entry 3400 (class 0 OID 0)
-- Dependencies: 220
-- Name: TABLE company_asses; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.company_asses IS 'assessment of companies based on informaton available online';


--
-- TOC entry 217 (class 1259 OID 25319)
-- Name: sendout_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.sendout_id_seq
    START WITH 1000
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.sendout_id_seq OWNER TO postgres;

--
-- TOC entry 219 (class 1259 OID 25369)
-- Name: my_sendouts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.my_sendouts (
    sendout_id bigint DEFAULT nextval('public.sendout_id_seq'::regclass) NOT NULL,
    position_id bigint,
    applied_date date,
    status character varying(50),
    status_start_date date,
    status_end_date date,
    hr_person character varying(500),
    other_people character varying(500),
    comments character varying(2000)
);


ALTER TABLE public.my_sendouts OWNER TO postgres;

--
-- TOC entry 3401 (class 0 OID 0)
-- Dependencies: 219
-- Name: TABLE my_sendouts; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.my_sendouts IS 'my sendouts to companies';


--
-- TOC entry 227 (class 1259 OID 82897)
-- Name: param_filter; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.param_filter (
    id_ integer NOT NULL,
    pkey character varying(50),
    pvalue character varying(50),
    plogic character varying(10),
    pcolumn character varying(50)
);


ALTER TABLE public.param_filter OWNER TO postgres;

--
-- TOC entry 3402 (class 0 OID 0)
-- Dependencies: 227
-- Name: TABLE param_filter; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.param_filter IS 'values which have to be either excluded or included into v_positions_gold view';


--
-- TOC entry 226 (class 1259 OID 53782)
-- Name: param_translate; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.param_translate (
    id_ integer NOT NULL,
    pkey character varying,
    pvalue character varying
);


ALTER TABLE public.param_translate OWNER TO postgres;

--
-- TOC entry 3403 (class 0 OID 0)
-- Dependencies: 226
-- Name: TABLE param_translate; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.param_translate IS 'values which have to be translated into more generic form in positions_silver. used by procedure latest_data_raw_bronze_to_silver';


--
-- TOC entry 215 (class 1259 OID 25317)
-- Name: positions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.positions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.positions_id_seq OWNER TO postgres;

--
-- TOC entry 218 (class 1259 OID 25362)
-- Name: positions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.positions (
    position_id bigint DEFAULT nextval('public.positions_id_seq'::regclass) NOT NULL,
    company_id integer,
    title character varying(500),
    description text,
    key_words character varying(2000),
    k_words_desc character varying(300),
    url character varying(1000) NOT NULL,
    source_name character varying(200),
    category character varying(200),
    salary character varying(200),
    date_registered date,
    type_of_work character varying(200),
    experience character varying(200),
    employment_type character varying(200),
    operating_mode character varying(200),
    company_name character varying(200)
);


ALTER TABLE public.positions OWNER TO postgres;

--
-- TOC entry 3404 (class 0 OID 0)
-- Dependencies: 218
-- Name: TABLE positions; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.positions IS 'main table';


--
-- TOC entry 221 (class 1259 OID 25985)
-- Name: positions_id_seq_test; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.positions_id_seq_test
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.positions_id_seq_test OWNER TO postgres;

--
-- TOC entry 223 (class 1259 OID 27415)
-- Name: positions_silver; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.positions_silver (
    position_id bigint,
    company_id integer,
    title character varying(500),
    description text,
    key_words character varying(2000),
    k_words_desc character varying(300),
    url character varying(1000),
    source_name character varying(200),
    category character varying(200),
    salary character varying(200),
    date_registered date,
    type_of_work character varying(200),
    experience character varying(200),
    employment_type character varying(200),
    operating_mode character varying(200),
    company_name character varying(200)
);


ALTER TABLE public.positions_silver OWNER TO postgres;

--
-- TOC entry 3405 (class 0 OID 0)
-- Dependencies: 223
-- Name: TABLE positions_silver; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.positions_silver IS 'values have been translated from param_translate table, duplicates were dropped, and key_words_desc was populated';


--
-- TOC entry 222 (class 1259 OID 26006)
-- Name: positions_test; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.positions_test (
    position_id bigint DEFAULT nextval('public.positions_id_seq_test'::regclass),
    company_id integer,
    title character varying(500),
    description text,
    key_words character varying(2000),
    k_words_desc character varying(300),
    url character varying(500),
    source_name character varying(200),
    category character varying(200),
    salary character varying(200),
    date_registered date,
    type_of_work character varying(200),
    experience character varying(200),
    employment_type character varying(200),
    operating_mode character varying(200),
    company_name character varying(200)
);


ALTER TABLE public.positions_test OWNER TO postgres;

--
-- TOC entry 228 (class 1259 OID 82924)
-- Name: unattractive_positions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.unattractive_positions (
    position_id integer NOT NULL
);


ALTER TABLE public.unattractive_positions OWNER TO postgres;

--
-- TOC entry 3406 (class 0 OID 0)
-- Dependencies: 228
-- Name: TABLE unattractive_positions; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.unattractive_positions IS 'ids which have been True for param_filter. the positions which are unattractive';


--
-- TOC entry 224 (class 1259 OID 44592)
-- Name: v_aplied; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_aplied AS
 SELECT positions.title,
    my_sendouts.status,
    positions.company_name,
    positions.salary,
    my_sendouts.status_start_date,
    my_sendouts.status_end_date,
    (my_sendouts.comments)::character varying(200) AS comments
   FROM (public.my_sendouts
     LEFT JOIN public.positions ON ((my_sendouts.position_id = positions.position_id)));


ALTER TABLE public.v_aplied OWNER TO postgres;

--
-- TOC entry 225 (class 1259 OID 47449)
-- Name: v_aplied_active; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_aplied_active AS
 SELECT my_sendouts.position_id,
    TRIM(BOTH FROM positions.title) AS title,
    my_sendouts.status,
    TRIM(BOTH FROM positions.company_name) AS company_name,
    positions.salary,
    my_sendouts.status_start_date,
    my_sendouts.status_end_date,
    (my_sendouts.comments)::character varying(200) AS comments
   FROM (public.my_sendouts
     LEFT JOIN public.positions ON ((my_sendouts.position_id = positions.position_id)))
  WHERE (my_sendouts.status_end_date IS NULL)
  ORDER BY my_sendouts.status DESC, my_sendouts.status_start_date;


ALTER TABLE public.v_aplied_active OWNER TO postgres;

--
-- TOC entry 229 (class 1259 OID 82979)
-- Name: v_positions_gold; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_positions_gold AS
 SELECT positions_silver.position_id,
    positions_silver.company_id,
    positions_silver.title,
    positions_silver.description,
    positions_silver.key_words,
    positions_silver.k_words_desc,
    positions_silver.url,
    positions_silver.source_name,
    positions_silver.category,
    positions_silver.salary,
    positions_silver.date_registered,
    positions_silver.type_of_work,
    positions_silver.experience,
    positions_silver.employment_type,
    positions_silver.operating_mode,
    positions_silver.company_name
   FROM public.positions_silver
  WHERE ((positions_silver.date_registered = ( SELECT max(positions_silver_1.date_registered) AS max
           FROM public.positions_silver positions_silver_1)) AND (NOT (positions_silver.position_id IN ( SELECT unattractive_positions.position_id
           FROM public.unattractive_positions))));


ALTER TABLE public.v_positions_gold OWNER TO postgres;

--
-- TOC entry 3235 (class 2606 OID 25382)
-- Name: company_asses company_asses_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.company_asses
    ADD CONSTRAINT company_asses_pkey PRIMARY KEY (company_id);


--
-- TOC entry 3247 (class 2606 OID 87284)
-- Name: assessed_ids fk_unique; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.assessed_ids
    ADD CONSTRAINT fk_unique UNIQUE (position_id);


--
-- TOC entry 3233 (class 2606 OID 25375)
-- Name: my_sendouts my_sendouts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.my_sendouts
    ADD CONSTRAINT my_sendouts_pkey PRIMARY KEY (sendout_id);


--
-- TOC entry 3243 (class 2606 OID 82901)
-- Name: param_filter param_filter_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.param_filter
    ADD CONSTRAINT param_filter_pkey PRIMARY KEY (id_);


--
-- TOC entry 3241 (class 2606 OID 53788)
-- Name: param_translate param_translate_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.param_translate
    ADD CONSTRAINT param_translate_pkey PRIMARY KEY (id_);


--
-- TOC entry 3229 (class 2606 OID 25368)
-- Name: positions positions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_pkey PRIMARY KEY (position_id);


--
-- TOC entry 3245 (class 2606 OID 82928)
-- Name: unattractive_positions unattractive_positions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.unattractive_positions
    ADD CONSTRAINT unattractive_positions_pkey PRIMARY KEY (position_id);


--
-- TOC entry 3237 (class 2606 OID 33022)
-- Name: company_asses unique_com_name; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.company_asses
    ADD CONSTRAINT unique_com_name UNIQUE (company_name);


--
-- TOC entry 3231 (class 2606 OID 44422)
-- Name: positions url_unique_con; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT url_unique_con UNIQUE (url);


--
-- TOC entry 3239 (class 2606 OID 26012)
-- Name: positions_test url_unique_con_test; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.positions_test
    ADD CONSTRAINT url_unique_con_test UNIQUE (url);


--
-- TOC entry 3249 (class 2606 OID 25388)
-- Name: my_sendouts my_sendouts_position_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.my_sendouts
    ADD CONSTRAINT my_sendouts_position_id_fkey FOREIGN KEY (position_id) REFERENCES public.positions(position_id) NOT VALID;


--
-- TOC entry 3250 (class 2606 OID 87278)
-- Name: assessed_ids position_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.assessed_ids
    ADD CONSTRAINT position_id_fk FOREIGN KEY (position_id) REFERENCES public.positions(position_id);


--
-- TOC entry 3248 (class 2606 OID 25383)
-- Name: positions positions_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.positions
    ADD CONSTRAINT positions_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.company_asses(company_id) NOT VALID;


-- Completed on 2024-07-21 21:11:29

--
-- PostgreSQL database dump complete
--

