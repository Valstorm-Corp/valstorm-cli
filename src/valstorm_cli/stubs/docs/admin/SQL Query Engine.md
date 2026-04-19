# Query Engine Documentation

This query engine allows you to interact with your data using a familiar SQL-like syntax while offering powerful, custom extensions for handling dynamic dates, user context, nested lookups, and specialized field types like phone numbers.

## Core Syntax Overview

The engine supports standard SQL clauses, including:

* `SELECT` (Specific fields, `*`, or `table.*`)
* `FROM` (Target object/collection)
* `JOIN ... ON ...` (Multi-join support)
* `WHERE` (Filters, including complex `( )`, `AND`, `OR` logic)
* `ORDER BY` (Sorting via `ASC` or `DESC`)
* `LIMIT` and `OFFSET` (Pagination)

## Special Context Keywords

### 1. The `ME` Keyword

You can use `ME` (or `'ME'`, `"me"`) in your `WHERE` clause to automatically filter records owned by or related to the currently authenticated user.

* **Example:** Find all contacts owned by the current user.
```sql
SELECT name, email FROM contact WHERE owner = ME

```



### 2. The `PHONE:` Resolver

The `PHONE:` prefix allows you to search across *all* phone fields on an object simultaneously without manually chaining `OR` conditions. It supports both exact matches (`=`) and partial matches (`LIKE`).

* **Example:** Find any lead where *any* phone field matches a specific number.
```sql
SELECT name, phone FROM lead WHERE PHONE: = '+15551234567'

```


* **Example:** Find companies with a phone number starting with a specific area code.
```sql
SELECT name, phone FROM company WHERE PHONE: LIKE '+1555%'

```



### 3. Automatic Lookup Resolution

When querying against a `lookup` or `compound_lookup` field (like `company`, `owner`, or `created_by`), you do not need to append `.id`. The engine automatically resolves `WHERE company = '123'` to `WHERE company.id = '123'`.

---

## Date & Time Special Keywords

The engine features a highly intelligent datetime parser. When using these keywords with an equals sign (`=`), the engine automatically translates them into a time **range** (e.g., `>= start_of_period AND <= end_of_period`).

### Standard Relative Ranges

These keywords evaluate based on the current date and time:

* **Days:** `today`, `yesterday`, `tomorrow`, `this_day`, `last_day`
* **Weeks:** `this_week`, `last_week`, `next_week`
* **Months:** `this_month`, `last_month`, `next_month`
* **Quarters:** `last_quarter`, `next_quarter`
* **Years:** `this_year`, `last_year`, `next_year`
* **Trailing/Future blocks:** `last_7_days`, `last_30_days`, `last_90_days`, `next_7_days`, `next_30_days`, `next_90_days`

### Parameterized Relative Ranges (N-based)

You can specify the exact number of periods to look back or forward using a colon syntax (e.g., `keyword:N`).

* **Days:** `last_n_days:10`, `next_n_days:5`
* **Weeks:** `last_n_weeks:3`, `next_n_weeks:2`
* **Months:** `last_n_months:6`, `next_n_months:12`
* **Years:** `last_n_years:2`, `next_n_years:5`
* **Time:** `last_n_hours:24`, `next_n_hours:4`, `last_n_minutes:15`, `next_n_minutes:30`
* **Specific Weekdays:** `last_n_mondays:3`, `next_n_fridays:2` *(Works for all days of the week)*

### Contextual Specific Ranges

You can pass an ISO date string to these keywords to get the full range containing that specific date.

* `month_of:'2024-05-15'` (Resolves to May 1st - May 31st, 2024)
* `week_of:'2024-05-15'` (Resolves to the Sunday-Saturday week containing May 15th)
* `year_of:'2024-05-15'`
* `day_of:'2024-05-15'`

---

## Working Examples by Object

### Leads (`lead`)

**1. Recent high-value leads assigned to me:**

```sql
SELECT name, status, loan_amount 
FROM lead 
WHERE owner = ME AND created_date = this_week AND loan_amount > 500000 
ORDER BY loan_amount DESC

```

**2. Leads that went unresponsive in the last 30 days:**

```sql
SELECT name, email, phone 
FROM lead 
WHERE status = 'Unresponsive' AND unresponsive_date_time = last_30_days

```

**3. Complex pipeline filtering (Using Parentheses):**

```sql
SELECT * FROM lead 
WHERE (status = 'New' OR status_reason = 'Needs Follow Up') 
  AND lead_source = 'Website' 
  AND created_date = last_n_days:14

```

### Contacts (`contact`)

**1. Finding a contact by a partial phone number:**

```sql
SELECT first_name, last_name, email 
FROM contact 
WHERE PHONE: LIKE '%5551234%' AND do_not_call = false

```

**2. Contacts that opted into SMS this month:**

```sql
SELECT name, phone 
FROM contact 
WHERE sms_opt_in = true AND created_date = this_month

```

### Companies (`company`)

**1. Large tech companies added recently:**

```sql
SELECT name, industry, employees 
FROM company 
WHERE industry = 'Technology' AND employees >= 1000 AND created_date = last_quarter

```

**2. Companies missing billing addresses (Null checks):**

```sql
SELECT name, website 
FROM company 
WHERE billing_address IS NULL AND annual_revenue > 1000000

```

### Notes (`note`)

**1. Notes created by me on specific days of the week:**

```sql
SELECT name, plain_notes, related_to 
FROM note 
WHERE created_by = ME AND created_date = last_n_fridays:4

```

### Advanced Joins

**1. Fetching Leads alongside their related Company data:**

```sql
SELECT lead.name, lead.status, company.name, company.industry 
FROM lead 
JOIN company ON lead.company = company.id 
WHERE lead.status = 'Preapproved' AND company.annual_revenue > 500000

```

---

# 🔍 Valstorm Query Engine Cheat Sheet

## 1. The Basics

Your queries follow standard SQL syntax but are supercharged for your CRM data.

* **Format:** `SELECT [fields] FROM [object] WHERE [conditions] ORDER BY [field] LIMIT [number]`
* **Select All:** Use `*` to get all fields, or `table.*` when doing joins.
* **Null Checks:** Use `IS NULL` or `IS NOT NULL`.
* **Grouping:** Use parentheses `()` to group `AND` / `OR` logic.

## 2. Magic Filters

Use these special keywords in your `WHERE` clause to instantly filter complex data.

| Keyword | What It Does | Example |
| --- | --- | --- |
| **`ME`** | Automatically filters for records owned by or related to your logged-in user account. | `WHERE owner = ME` |
| **`PHONE:`** | Searches *all* phone fields on an object simultaneously. Supports `=` and `LIKE`. | `WHERE PHONE: LIKE '%5551234%'` |
| **Lookups** | No need to add `.id` for lookups. The engine resolves them automatically. | `WHERE company = '123'` |

## 3. Dynamic Date & Time Keywords

Never hardcode a date again. Use these exact keywords with an equals sign (`=`) to automatically filter by time ranges.

### Relative Ranges (Based on right now)

* **Days:** `today`, `yesterday`, `tomorrow`, `this_day`, `last_day`
* **Weeks:** `this_week`, `last_week`, `next_week`
* **Months:** `this_month`, `last_month`, `next_month`
* **Quarters:** `last_quarter`, `next_quarter`
* **Years:** `this_year`, `last_year`, `next_year`
* **Blocks:** `last_7_days`, `last_30_days`, `last_90_days`, `next_7_days`, `next_30_days`, `next_90_days`

### Number-Based Ranges (Replace N with a number)

* **Days/Weeks:** `last_n_days:14`, `next_n_weeks:2`
* **Months/Years:** `last_n_months:6`, `next_n_years:1`
* **Granular:** `last_n_hours:24`, `last_n_minutes:30`
* **Specific Days:** `last_n_mondays:3`, `next_n_fridays:2` *(Works for all days)*

### Contextual Ranges (Pass a specific date)

* `month_of:'2024-05-15'` *(Finds the whole month of May)*
* `week_of:'2024-05-15'` *(Finds the specific week)*
* `year_of:'2024-05-15'` *(Finds the specific year)*

---

## 4. Copy & Paste Examples

**My Recent High-Value Leads**

```sql
SELECT name, status, loan_amount FROM lead WHERE owner = ME AND created_date = this_week AND loan_amount > 500000 ORDER BY loan_amount DESC
```

**Contacts Who Opted into SMS This Month**

```sql
SELECT first_name, last_name, phone FROM contact WHERE sms_opt_in = true AND created_date = this_month
```

**Search for a Phone Number Everywhere**

```sql
SELECT name, email FROM contact WHERE PHONE: LIKE '%5551234%'
```

**Complex Pipeline Filter**

```sql
SELECT * FROM lead WHERE (status = 'New' OR status_reason = 'Needs Follow Up') AND lead_source = 'Website' AND created_date = last_n_days:14
```


**Join Leads with Company Data**

```sql
SELECT lead.name, lead.status, company.name, company.industry FROM lead JOIN company ON lead.company = company.id WHERE lead.status = 'Preapproved'
```
