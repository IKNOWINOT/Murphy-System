```sql
SELECT 
  c.segment, 
  SUM(o.total) AS total_revenue
FROM 
  orders o
JOIN 
  customers c ON o.customer_id = c.id
WHERE 
  EXTRACT(YEAR FROM o.created_at) = 2025
GROUP BY 
  c.segment
ORDER BY 
  total_revenue DESC
LIMIT 5;
```