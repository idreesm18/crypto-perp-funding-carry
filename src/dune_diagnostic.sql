-- Diagnostic: compare address formats between cex.addresses and bitcoin.outputs
-- Run each section separately (comment out the others)
-- This tells us exactly what cast is needed for the join

-- SECTION A: Sample Bitcoin addresses from cex.addresses after cast
-- (tells us what format they're stored in)
SELECT
    cex_name,
    from_utf8(address)  AS address_str,
    length(address)     AS n_bytes
FROM cex.addresses
WHERE blockchain = 'bitcoin'
LIMIT 20

-- SECTION B: Sample receiving addresses from bitcoin.outputs (recent)
-- SELECT
--     address,
--     length(address) AS n_chars,
--     SUM(value)      AS total_btc
-- FROM bitcoin.outputs
-- WHERE block_time >= TIMESTAMP '2024-01-01'
-- GROUP BY 1, 2
-- ORDER BY 3 DESC
-- LIMIT 20
