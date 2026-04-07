-- Hourly ETH exchange inflows via Dune Analytics
--
-- HOW TO USE:
--   1. Go to https://dune.com/queries and create a new query
--   2. Paste this SQL and click Run
--   3. After results load: save query ID from URL for use in 5_onchain.py
--
-- Strategy: materialise the 4366 exchange addresses into a CTE first so the
-- planner can broadcast-join the small table and avoid a full traces scan.
-- If this still times out on the free tier, use the year-by-year workaround
-- at the bottom.
--
-- ethereum.traces captures all native ETH value transfers (including internal).
-- value is in wei; divide by 1e18 to get ETH.
-- Filters: value > 0, success = true, exclude delegatecall (no value transfer).

WITH exchange_addrs AS (
    -- 4366 known Ethereum exchange addresses, pulled once
    SELECT address
    FROM cex.addresses
    WHERE blockchain = 'ethereum'
)

SELECT
    date_trunc('hour', t.block_time)         AS hour,
    SUM(CAST(t.value AS DOUBLE) / 1e18)      AS eth_inflow
FROM ethereum.traces AS t
INNER JOIN exchange_addrs AS a
    ON t.to = a.address
WHERE t.block_time  >= TIMESTAMP '2020-01-01'
  AND t.value        > UINT256 '0'
  AND t.success      = true
  AND t.call_type   != 'delegatecall'
GROUP BY 1
ORDER BY 1


-- ============================================================
-- YEAR-BY-YEAR WORKAROUND (if the query above times out)
-- Run each block separately, results auto-merged by 5_onchain.py
-- ============================================================

-- 2020
-- WITH exchange_addrs AS (
--     SELECT address FROM cex.addresses WHERE blockchain = 'ethereum'
-- )
-- SELECT date_trunc('hour', t.block_time) AS hour, SUM(CAST(t.value AS DOUBLE) / 1e18) AS eth_inflow
-- FROM ethereum.traces AS t
-- INNER JOIN exchange_addrs AS a ON t.to = a.address
-- WHERE t.block_time >= TIMESTAMP '2020-01-01' AND t.block_time < TIMESTAMP '2021-01-01'
--   AND t.value > UINT256 '0' AND t.success = true AND t.call_type != 'delegatecall'
-- GROUP BY 1 ORDER BY 1

-- 2021
-- WITH exchange_addrs AS (
--     SELECT address FROM cex.addresses WHERE blockchain = 'ethereum'
-- )
-- SELECT date_trunc('hour', t.block_time) AS hour, SUM(CAST(t.value AS DOUBLE) / 1e18) AS eth_inflow
-- FROM ethereum.traces AS t
-- INNER JOIN exchange_addrs AS a ON t.to = a.address
-- WHERE t.block_time >= TIMESTAMP '2021-01-01' AND t.block_time < TIMESTAMP '2022-01-01'
--   AND t.value > UINT256 '0' AND t.success = true AND t.call_type != 'delegatecall'
-- GROUP BY 1 ORDER BY 1

-- 2022
-- WITH exchange_addrs AS (
--     SELECT address FROM cex.addresses WHERE blockchain = 'ethereum'
-- )
-- SELECT date_trunc('hour', t.block_time) AS hour, SUM(CAST(t.value AS DOUBLE) / 1e18) AS eth_inflow
-- FROM ethereum.traces AS t
-- INNER JOIN exchange_addrs AS a ON t.to = a.address
-- WHERE t.block_time >= TIMESTAMP '2022-01-01' AND t.block_time < TIMESTAMP '2023-01-01'
--   AND t.value > UINT256 '0' AND t.success = true AND t.call_type != 'delegatecall'
-- GROUP BY 1 ORDER BY 1

-- 2023
-- WITH exchange_addrs AS (
--     SELECT address FROM cex.addresses WHERE blockchain = 'ethereum'
-- )
-- SELECT date_trunc('hour', t.block_time) AS hour, SUM(CAST(t.value AS DOUBLE) / 1e18) AS eth_inflow
-- FROM ethereum.traces AS t
-- INNER JOIN exchange_addrs AS a ON t.to = a.address
-- WHERE t.block_time >= TIMESTAMP '2023-01-01' AND t.block_time < TIMESTAMP '2024-01-01'
--   AND t.value > UINT256 '0' AND t.success = true AND t.call_type != 'delegatecall'
-- GROUP BY 1 ORDER BY 1

-- 2024-2026
-- WITH exchange_addrs AS (
--     SELECT address FROM cex.addresses WHERE blockchain = 'ethereum'
-- )
-- SELECT date_trunc('hour', t.block_time) AS hour, SUM(CAST(t.value AS DOUBLE) / 1e18) AS eth_inflow
-- FROM ethereum.traces AS t
-- INNER JOIN exchange_addrs AS a ON t.to = a.address
-- WHERE t.block_time >= TIMESTAMP '2024-01-01'
--   AND t.value > UINT256 '0' AND t.success = true AND t.call_type != 'delegatecall'
-- GROUP BY 1 ORDER BY 1
