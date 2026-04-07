-- Hourly BTC exchange inflows via Dune Analytics
--
-- HOW TO USE:
--   1. Go to https://dune.com/queries and create a new query
--   2. Paste this SQL and click Run
--   3. After results load: Download CSV
--   4. Save to: carry_project/data/dune_btc_inflows.csv
--
-- Strategy: materialise the 761 exchange addresses into a CTE first so the
-- planner can broadcast-join the small table and avoid a full UTXO scan.
-- If this still times out on the free tier, use the year-by-year workaround
-- at the bottom and union the downloaded CSVs.

WITH exchange_addrs AS (
    -- 761 known Bitcoin exchange addresses, pulled once
    SELECT from_utf8(address) AS address
    FROM cex.addresses
    WHERE blockchain = 'bitcoin'
)

SELECT
    date_trunc('hour', o.block_time)  AS hour,
    SUM(o.value)                      AS btc_inflow
FROM bitcoin.outputs AS o
INNER JOIN exchange_addrs AS a
    ON o.address = a.address
WHERE o.block_time >= TIMESTAMP '2020-01-01'
GROUP BY 1
ORDER BY 1


-- ============================================================
-- YEAR-BY-YEAR WORKAROUND (if the query above times out)
-- Run each block separately, download 5 CSVs, combine in Python
-- ============================================================

-- 2020
-- WITH exchange_addrs AS (
--     SELECT from_utf8(address) AS address
--     FROM cex.addresses WHERE blockchain = 'bitcoin'
-- )
-- SELECT date_trunc('hour', o.block_time) AS hour, SUM(o.value) AS btc_inflow
-- FROM bitcoin.outputs AS o
-- INNER JOIN exchange_addrs AS a ON o.address = a.address
-- WHERE o.block_time >= TIMESTAMP '2020-01-01' AND o.block_time < TIMESTAMP '2021-01-01'
-- GROUP BY 1 ORDER BY 1

-- 2021
-- WITH exchange_addrs AS (
--     SELECT from_utf8(address) AS address
--     FROM cex.addresses WHERE blockchain = 'bitcoin'
-- )
-- SELECT date_trunc('hour', o.block_time) AS hour, SUM(o.value) AS btc_inflow
-- FROM bitcoin.outputs AS o
-- INNER JOIN exchange_addrs AS a ON o.address = a.address
-- WHERE o.block_time >= TIMESTAMP '2021-01-01' AND o.block_time < TIMESTAMP '2022-01-01'
-- GROUP BY 1 ORDER BY 1

-- 2022
-- WITH exchange_addrs AS (
--     SELECT from_utf8(address) AS address
--     FROM cex.addresses WHERE blockchain = 'bitcoin'
-- )
-- SELECT date_trunc('hour', o.block_time) AS hour, SUM(o.value) AS btc_inflow
-- FROM bitcoin.outputs AS o
-- INNER JOIN exchange_addrs AS a ON o.address = a.address
-- WHERE o.block_time >= TIMESTAMP '2022-01-01' AND o.block_time < TIMESTAMP '2023-01-01'
-- GROUP BY 1 ORDER BY 1

-- 2023
-- WITH exchange_addrs AS (
--     SELECT from_utf8(address) AS address
--     FROM cex.addresses WHERE blockchain = 'bitcoin'
-- )
-- SELECT date_trunc('hour', o.block_time) AS hour, SUM(o.value) AS btc_inflow
-- FROM bitcoin.outputs AS o
-- INNER JOIN exchange_addrs AS a ON o.address = a.address
-- WHERE o.block_time >= TIMESTAMP '2023-01-01' AND o.block_time < TIMESTAMP '2024-01-01'
-- GROUP BY 1 ORDER BY 1

-- 2024-2026
-- WITH exchange_addrs AS (
--     SELECT from_utf8(address) AS address
--     FROM cex.addresses WHERE blockchain = 'bitcoin'
-- )
-- SELECT date_trunc('hour', o.block_time) AS hour, SUM(o.value) AS btc_inflow
-- FROM bitcoin.outputs AS o
-- INNER JOIN exchange_addrs AS a ON o.address = a.address
-- WHERE o.block_time >= TIMESTAMP '2024-01-01'
-- GROUP BY 1 ORDER BY 1
