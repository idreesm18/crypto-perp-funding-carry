-- Hourly USDT exchange inflows (Ethereum) via Dune Analytics
--
-- HOW TO USE:
--   1. Go to https://dune.com/queries and create a new query
--   2. Paste this SQL and click Run
--   3. Save the query and note the query ID from the URL
--   4. Set DUNE_USDT_QUERY_ID in src/5_onchain.py
--
-- Rationale: Chi, Chu & Hao (2024, arXiv:2411.06327) find that USDT inflows
-- to exchanges positively predict BTC and ETH returns at 1-6h frequency,
-- while BTC/ETH inflows themselves lack predictive power for returns.
-- Stablecoin inflows are cleaner signal: USDT on exchanges = dry powder
-- about to buy crypto → basis expansion → higher funding.
--
-- tokens.transfers is Dune's curated cross-chain ERC-20 transfer table.
-- amount is already in display units (USDT, 6 decimals pre-adjusted).
-- USDT contract: 0xdAC17F958D2ee523a2206206994597C13D831ec7

WITH exchange_addrs AS (
    SELECT address
    FROM cex.addresses
    WHERE blockchain = 'ethereum'
)

SELECT
    date_trunc('hour', t.block_time)  AS hour,
    SUM(t.amount)                     AS usdt_inflow
FROM tokens.transfers AS t
INNER JOIN exchange_addrs AS a
    ON t.to = a.address
WHERE t.blockchain      = 'ethereum'
  AND t.token_standard  = 'erc20'
  AND t.contract_address = 0xdAC17F958D2ee523a2206206994597C13D831ec7
  AND t.block_time      >= TIMESTAMP '2020-01-01'
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
-- SELECT date_trunc('hour', t.block_time) AS hour, SUM(t.amount) AS usdt_inflow
-- FROM tokens.transfers AS t
-- INNER JOIN exchange_addrs AS a ON t.to = a.address
-- WHERE t.blockchain = 'ethereum' AND t.token_standard = 'erc20'
--   AND t.contract_address = 0xdAC17F958D2ee523a2206206994597C13D831ec7
--   AND t.block_time >= TIMESTAMP '2020-01-01' AND t.block_time < TIMESTAMP '2021-01-01'
-- GROUP BY 1 ORDER BY 1

-- 2021
-- WITH exchange_addrs AS (
--     SELECT address FROM cex.addresses WHERE blockchain = 'ethereum'
-- )
-- SELECT date_trunc('hour', t.block_time) AS hour, SUM(t.amount) AS usdt_inflow
-- FROM tokens.transfers AS t
-- INNER JOIN exchange_addrs AS a ON t.to = a.address
-- WHERE t.blockchain = 'ethereum' AND t.token_standard = 'erc20'
--   AND t.contract_address = 0xdAC17F958D2ee523a2206206994597C13D831ec7
--   AND t.block_time >= TIMESTAMP '2021-01-01' AND t.block_time < TIMESTAMP '2022-01-01'
-- GROUP BY 1 ORDER BY 1

-- 2022
-- WITH exchange_addrs AS (
--     SELECT address FROM cex.addresses WHERE blockchain = 'ethereum'
-- )
-- SELECT date_trunc('hour', t.block_time) AS hour, SUM(t.amount) AS usdt_inflow
-- FROM tokens.transfers AS t
-- INNER JOIN exchange_addrs AS a ON t.to = a.address
-- WHERE t.blockchain = 'ethereum' AND t.token_standard = 'erc20'
--   AND t.contract_address = 0xdAC17F958D2ee523a2206206994597C13D831ec7
--   AND t.block_time >= TIMESTAMP '2022-01-01' AND t.block_time < TIMESTAMP '2023-01-01'
-- GROUP BY 1 ORDER BY 1

-- 2023
-- WITH exchange_addrs AS (
--     SELECT address FROM cex.addresses WHERE blockchain = 'ethereum'
-- )
-- SELECT date_trunc('hour', t.block_time) AS hour, SUM(t.amount) AS usdt_inflow
-- FROM tokens.transfers AS t
-- INNER JOIN exchange_addrs AS a ON t.to = a.address
-- WHERE t.blockchain = 'ethereum' AND t.token_standard = 'erc20'
--   AND t.contract_address = 0xdAC17F958D2ee523a2206206994597C13D831ec7
--   AND t.block_time >= TIMESTAMP '2023-01-01' AND t.block_time < TIMESTAMP '2024-01-01'
-- GROUP BY 1 ORDER BY 1

-- 2024-2026
-- WITH exchange_addrs AS (
--     SELECT address FROM cex.addresses WHERE blockchain = 'ethereum'
-- )
-- SELECT date_trunc('hour', t.block_time) AS hour, SUM(t.amount) AS usdt_inflow
-- FROM tokens.transfers AS t
-- INNER JOIN exchange_addrs AS a ON t.to = a.address
-- WHERE t.blockchain = 'ethereum' AND t.token_standard = 'erc20'
--   AND t.contract_address = 0xdAC17F958D2ee523a2206206994597C13D831ec7
--   AND t.block_time >= TIMESTAMP '2024-01-01'
-- GROUP BY 1 ORDER BY 1
