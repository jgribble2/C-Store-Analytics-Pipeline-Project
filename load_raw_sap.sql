-- ==========================================================================
-- Load the synthetic SAP extract into Snowflake (RAW layer)
--
-- Every column lands as VARCHAR, the way a real SAP extract usually lands.
-- Type casting, renaming, and sign handling happen later in dbt staging.
--
-- Run this in a Snowsight worksheet. Step 3 has two options for getting the
-- CSVs onto the stage.
-- ==========================================================================

-- 1. Warehouse, database, schema --------------------------------------------
CREATE WAREHOUSE IF NOT EXISTS CSTORE_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60          -- seconds idle before it stops burning credits
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

CREATE DATABASE IF NOT EXISTS CSTORE;
CREATE SCHEMA IF NOT EXISTS CSTORE.RAW_SAP;
USE WAREHOUSE CSTORE_WH;
USE SCHEMA CSTORE.RAW_SAP;

-- 2. File format and stage --------------------------------------------------
CREATE OR REPLACE FILE FORMAT SAP_CSV
  TYPE = CSV
  SKIP_HEADER = 1
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  EMPTY_FIELD_AS_NULL = TRUE
  TRIM_SPACE = FALSE;        -- keep leading zeros and fixed-width keys intact

CREATE OR REPLACE STAGE SAP_STAGE FILE_FORMAT = SAP_CSV;

-- 3. Upload the CSVs to @SAP_STAGE ------------------------------------------
--   Option A (no install): In Snowsight, open Data > Databases > CSTORE >
--     RAW_SAP > Stages > SAP_STAGE and upload the 7 CSV files.
--   Option B (Snowflake CLI or SnowSQL), from the folder with the CSVs:
--     PUT file://sap_raw/*.csv @CSTORE.RAW_SAP.SAP_STAGE AUTO_COMPRESS=TRUE;
LIST @SAP_STAGE;

-- 4. Raw tables (all VARCHAR, SAP names) ------------------------------------
CREATE OR REPLACE TABLE T001W (
  MANDT VARCHAR, WERKS VARCHAR, NAME1 VARCHAR, STRAS VARCHAR, ORT01 VARCHAR,
  REGIO VARCHAR, PSTLZ VARCHAR, LAND1 VARCHAR, VKORG VARCHAR);

CREATE OR REPLACE TABLE ZSTORE_ATTR (
  MANDT VARCHAR, WERKS VARCHAR, STORE_FORMAT VARCHAR, FUEL_FLAG VARCHAR, SQ_FT VARCHAR,
  FUEL_POSITIONS VARCHAR, DISTRICT VARCHAR, OPEN_DATE VARCHAR, CLOSE_DATE VARCHAR);

CREATE OR REPLACE TABLE T023T (
  MANDT VARCHAR, SPRAS VARCHAR, MATKL VARCHAR, WGBEZ VARCHAR);

CREATE OR REPLACE TABLE MARA (
  MANDT VARCHAR, MATNR VARCHAR, ERSDA VARCHAR, LVORM VARCHAR, MTART VARCHAR,
  MATKL VARCHAR, MEINS VARCHAR, BRGEW VARCHAR, GEWEI VARCHAR);

CREATE OR REPLACE TABLE MAKT (
  MANDT VARCHAR, MATNR VARCHAR, SPRAS VARCHAR, MAKTX VARCHAR);

CREATE OR REPLACE TABLE VBRK (
  MANDT VARCHAR, VBELN VARCHAR, FKART VARCHAR, VKORG VARCHAR, FKDAT VARCHAR, ERDAT VARCHAR,
  ERZET VARCHAR, KUNAG VARCHAR, WAERK VARCHAR, NETWR VARCHAR, MWSBK VARCHAR,
  FKSTO VARCHAR, SFAKN VARCHAR);

CREATE OR REPLACE TABLE VBRP (
  MANDT VARCHAR, VBELN VARCHAR, POSNR VARCHAR, MATNR VARCHAR, MATKL VARCHAR, WERKS VARCHAR,
  FKIMG VARCHAR, VRKME VARCHAR, NETWR VARCHAR, WAVWR VARCHAR, MWSBP VARCHAR);

-- 5. Load -------------------------------------------------------------------
-- PATTERN matches the file whether or not it was gzipped on upload.
COPY INTO T001W       FROM @SAP_STAGE PATTERN = '.*T001W[.]csv.*';
COPY INTO ZSTORE_ATTR FROM @SAP_STAGE PATTERN = '.*ZSTORE_ATTR[.]csv.*';
COPY INTO T023T       FROM @SAP_STAGE PATTERN = '.*T023T[.]csv.*';
COPY INTO MARA        FROM @SAP_STAGE PATTERN = '.*MARA[.]csv.*';
COPY INTO MAKT        FROM @SAP_STAGE PATTERN = '.*MAKT[.]csv.*';
COPY INTO VBRK        FROM @SAP_STAGE PATTERN = '.*VBRK[.]csv.*';
COPY INTO VBRP        FROM @SAP_STAGE PATTERN = '.*VBRP[.]csv.*';

-- 6. Sanity checks ----------------------------------------------------------
-- Expected with default settings: 20 stores, 132 materials,
-- 343,898 headers, 671,275 line items.
SELECT 'T001W' AS tbl, COUNT(*) AS row_count FROM T001W
UNION ALL SELECT 'ZSTORE_ATTR', COUNT(*) FROM ZSTORE_ATTR
UNION ALL SELECT 'T023T', COUNT(*) FROM T023T
UNION ALL SELECT 'MARA', COUNT(*) FROM MARA
UNION ALL SELECT 'MAKT', COUNT(*) FROM MAKT
UNION ALL SELECT 'VBRK', COUNT(*) FROM VBRK
UNION ALL SELECT 'VBRP', COUNT(*) FROM VBRP;

-- Document type mix: mostly ZPOS, a few ZRET (returns) and S1 (cancellations)
SELECT FKART, COUNT(*) FROM VBRK GROUP BY FKART ORDER BY 2 DESC;

-- Leading zeros survived the load (should be 18)
SELECT DISTINCT LENGTH(MATNR) FROM MARA;

-- Every line item has a header (should be 0)
SELECT COUNT(*) FROM VBRP p LEFT JOIN VBRK k ON p.VBELN = k.VBELN WHERE k.VBELN IS NULL;
