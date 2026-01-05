-- =============================================
--ANALYSIS : customer segmentation
--Objective : Optimize upselling strategy
-- =============================================

--MASTER QUERY:
--Use for :
--SECTION 1 : Weekly Sales Distribution
--Question 1 : How are the different groups distributed by week?
--SECTION 2 : Upper-quartile variance by group
--Question 2 : What is the upsell potential of each group?
WITH party_size AS (
    SELECT
        bt.bill_id,
        bt.total,
        b.date,
        EXTRACT(HOUR FROM b.time) AS hour,
        -
        ROUND(SUM(
		-- LOGIC: Estimated Customer Count
        -- Since the POS doesn't track covers, I created a point system:
        -- Appetizer/Dessert = 1 point | Main/Kid Menu = 2 points
            CASE 
                WHEN i.category_id IN (1) THEN 1
                WHEN i.category_id IN (2,) THEN 2
                ELSE 0
            END * bi.quantity
        )) AS customer_count,
        SUM(CASE WHEN i.category_id IN (1,2,3,4,5) THEN i.price * bi.quantity ELSE 0 END) / bt.total AS food_ratio,
        (bt.total / NULLIF(ROUND(SUM(
            CASE 
                WHEN i.category_id IN (1) THEN 1
                WHEN i.category_id IN (2,) THEN 2
                ELSE 0
            END * bi.quantity
        )),0)) AS spend_per_customer
    FROM bill_total AS bt
    JOIN bill_items AS bi ON bi.bill_id = bt.bill_id
    JOIN item AS i ON i.item_id = bi.item_id
    JOIN bill_id AS b ON b.bill_id = bt.bill_id
    WHERE bt.total > 0
	-- Remove negative bill
      AND bt.total < 500
	-- Exclude bill over 500$, all the bill over 500$ were organize party, last reel table was 490$
      AND b.date BETWEEN '2025-06-15' AND '2025-09-15'
	-- Keep only bill with at least 1 food item
      AND EXISTS (
          SELECT 1
          FROM bill_items AS bis
          JOIN item AS i2 ON i2.item_id = bis.item_id
          WHERE bis.bill_id = bt.bill_id
            AND i2.category_id IN (1,2,3,5)
      )
    GROUP BY bt.bill_id, bt.total, b.date, b.time
),
spend_thresholds AS (
    SELECT
        percentile_cont(0.25) WITHIN GROUP (ORDER BY spend_per_customer) AS q1,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY spend_per_customer) AS q3
    FROM party_size
)
SELECT
    ps.bill_id,
	ps.date,
    ps.customer_count,
    ps.total,
    ps.spend_per_customer,
    ps.hour,
    ps.food_ratio,
    
    -- Party size tier
    CASE WHEN ps.customer_count <= 5.5 THEN 'Small' ELSE 'Big' END AS party_size_tier,
    
    -- Spend tier per customer using dynamic Q1/Q3
    CASE 
        WHEN ps.spend_per_customer <= st.q1 THEN 'Low'
        WHEN ps.spend_per_customer <= st.q3 THEN 'Medium'
        ELSE 'High'
    END AS spend_tier,
    
    -- Time bin
    CASE WHEN ps.hour < 18 THEN 'Early' ELSE 'Late' END AS time_bin,
    
    -- Food ratio tier
    CASE WHEN ps.food_ratio < 0.5 THEN 'Drink-heavy' ELSE 'Food-heavy' END AS food_ratio_tier,
    
    -- Assign unique customer group number 1–24
    ((CASE WHEN ps.customer_count <= 5.5 THEN 0 ELSE 1 END) * 12) +
    ((CASE 
        WHEN ps.spend_per_customer <= st.q1 THEN 0
        WHEN ps.spend_per_customer <= st.q3 THEN 1
        ELSE 2
      END) * 4) +
    ((CASE WHEN ps.hour < 18 THEN 0 ELSE 1 END) * 2) +
    (CASE WHEN ps.food_ratio < 0.5 THEN 0 ELSE 1 END) + 1 AS customer_group_id

FROM party_size ps
CROSS JOIN spend_thresholds st
WHERE spend_per_customer IS NOT NULL
ORDER BY customer_group_id;


--SECTION 3 : Distribution of Item Categories by Customer Group
--Question 3 : How is spending distributed across categories for each group?

SELECT 
    customer_group_id,
    COUNT(r.bill_id) AS item_volume
FROM bill_items AS bi
JOIN rfm AS r ON r.bill_id = bi.bill_id
JOIN item AS i ON i.item_id = bi.item_id
-- Variable: Filter changed based on target category (Alcohol, Food, Soft Drink)
WHERE i.category_id IN (TARGET_IDS) 
GROUP BY customer_group_id
ORDER BY customer_group_id;