# Formula System

## Use Cases

* **Dynamic Calculations**: Allow users to create and manage formulas that can perform dynamic calculations based on various inputs.
  * Example 1: get todays date
  * Example 2: calculate the sum of two numbers
  * Example 3: check if a condition is true or false
* **CUD Validations**: Implement Validation rules where it uses formulas to look at the data being created, updated, or deleted and determine if the operation should be allowed.
  * Example 1: Prevent a user from creating a record if a certain field is empty
  * Example 2: Prevent a user from updating a record if a certain condition is not
  * Example 3: Prevent a user from deleting a record if it is linked to another record
* **Workflow Automation**: Use formulas calculate values inside of an automation. These can be used in field assignments, decisions, and more
  * Example 1: A formula that gets the current date and adds 7 days to it, which can be used to set a due date for a task
  * Example 2: A formula that checks if a certain field is empty, which can be used in a decision element to determine the next step in a workflow
  * Example 3: A formula that calculates the total price of an order by multiplying the quantity by the unit price, which can be used to update a field on the order record
* **Formula Fields**: Create formula fields that automatically calculate values based on other fields in the record. The happens after the data is pulled from the database, but before it is displayed to the user. This allows for real-time calculations and dynamic data presentation without the need for manual updates.
  * Example 1: A formula field that calculates the age of a person based on their birthdate
  * Example 2: A formula field that concatenates the first name and last name fields to create a full name
  * Example 3: A formula field that calculates the total price of an order by multiplying the quantity by the unit price

## Formula Types

Formulas must always return a value, and that value must be of a specific type OR null. The formula types are:

* **String**: A sequence of characters, such as "Hello, World!" or "John Doe".
* **Number**: A numerical value, such as 42 or 3.14.
* **Boolean**: A value that can be either true or false.
* **Date**: A date value, such as January 1, 2024.
* **DateTime**: A date and time value, such as January 1, 2024 at 12:00 PM.
* **Time**: A time value, such as 12:00 PM.

## Where Formulas Should be Calculated
Formulas are calculated on the backend. They can be written on the frontend, but they will be sent to the backend for calculation. This allows for more complex calculations and ensures that the formulas are calculated consistently across all users and devices.

---

## Technical Specification

This section defines the technical implementation details of the formula engine.

### Formula Syntax

The formula syntax is designed to be readable and expressive, drawing inspiration from common spreadsheet applications.

*   **Variables**: Data is accessed using Mustache-style tags. This allows for accessing nested data within the context.
    *   **Syntax**: `{{ path.to.variable }}`
    *   **Example**: `{{ new_record.amount }}`

*   **Functions**: Functions are uppercase and arguments are enclosed in parentheses. Arguments can be literals, variables, or other functions.
    *   **Syntax**: `FUNCTION_NAME(argument1, argument2, ...)`
    *   **Example**: `IF({{ new_record.amount }} > 1000, "High Value", "Standard")`

*   **Literals**:
    *   **String**: Enclosed in double quotes (`"Hello World"`).
    *   **Number**: Standard numerical format (`123.45`).
    *   **Boolean**: `TRUE` or `FALSE`.

### Operators

The following operators are supported, with standard precedence rules.

*   **Arithmetic**: `+` (Add), `-` (Subtract), `*` (Multiply), `/` (Divide), `^` (Power).
*   **Comparison**: `=` (Equal), `!=` or `<>` (Not Equal), `<` (Less Than), `>` (Greater Than), `<=` (Less Than or Equal), `>=` (Greater Than or Equal).
*   **String Concatenation**: `&` (e.g., `{{ first_name }} & " " & {{ last_name }}`).

### Data Context

All formula evaluations occur within a `context`. This is a JSON-like data structure (a Python dictionary) that provides the data the formula can access.

**Example Context:**
```json
{
  "new_record": {
    "first_name": "Jane",
    "last_name": "Doe",
    "amount": 1500,
    "status": "active"
  },
  "old_record": {
    "amount": 1200
  },
  "User": {
    "id": "user-abc-123",
    "department": "Sales"
  }
}
```

**Formula using this context:**
`IF({{ new_record.amount }} > 1000 AND {{ User.department }} = "Sales", "Flag for Review", "Auto-Approve")`

### Standard Function Library

The engine will provide a rich library of built-in functions.

*   **Logical Functions**:
    *   `IF(condition, value_if_true, value_if_false)`
    *   `AND(condition1, condition2, ...)`
    *   `OR(condition1, condition2, ...)`
    *   `NOT(condition)`
    *   `ISNULL(value)`
    *   `ISBLANK(text_value)`
    *   `CASE(expression, value1, result1, value2, result2, ..., default_result)`

*   **Text Functions**:
    *   `CONCAT(text1, text2, ...)` (or use the `&` operator)
    *   `LEFT(text, num_chars)`
    *   `RIGHT(text, num_chars)`
    *   `LEN(text)`
    *   `UPPER(text)`
    *   `LOWER(text)`
    *   `TRIM(text)`
    *   `FIND(search_text, text, start_num)`
    *   `REPLACE(old_text, start_num, num_chars, new_text)`
    *   `SUBSTITUTE(text, old_text, new_text, instance_num)`

*   **Math Functions**:
    *   `SUM(number1, number2, ...)`
    *   `AVERAGE(number1, number2, ...)`
    *   `MIN(number1, number2, ...)`
    *   `MAX(number1, number2, ...)`
    *   `ROUND(number, num_digits)`
    *   `ABS(number)`
    *   `MOD(dividend, divisor)`

*   **Date & Time Functions**:
    *   `TODAY()`: Returns the current date.
    *   `NOW()`: Returns the current date and time.
    *   `YEAR(date)`
    *   `MONTH(date)`
    *   `DAY(date)`
    *   `ADD_DAYS(date, num_days)`
    *   `DATE_DIFF(date1, date2, unit)` (unit e.g., "days", "hours")
    *   `HOUR(datetime)`
    *   `MINUTE(datetime)`
    *   `SECOND(datetime)`

### Execution Model

**Security is paramount.** The formula engine will never execute user-provided strings directly.

1.  **Parsing**: The formula string will be processed by a formal parser (e.g., using the **Lark** library in Python). The parser will validate the syntax and transform the string into an Abstract Syntax Tree (AST).
2.  **Interpretation**: A custom interpreter will walk the AST. When it encounters a variable node (`{{...}}`), it will perform a safe lookup in the provided data context. When it encounters a function node, it will execute the corresponding, pre-registered Python code for that function.
3.  **Sandboxing**: This model ensures the execution is completely sandboxed. The formula can only access data explicitly passed in the context and can only perform actions defined by the registered functions. **The use of `eval()` or similar dynamic execution functions is strictly forbidden.**

### Error Handling

The engine must provide clear error feedback.

*   **Syntax Errors**: The parser will detect and report errors like mismatched parentheses, invalid operators, or malformed function calls.
*   **Runtime Errors**: The interpreter will catch errors that occur during evaluation, such as:
    *   Division by zero.
    *   Incorrect argument types for a function (e.g., `UPPER(123)`).
    *   Referencing a variable that does not exist in the context.

The API response for an evaluation should contain either the calculated `value` or a structured `error` object.

---
## Implementation Roadmap

This section outlines the recommended steps for a developer to build the formula engine based on this design document.

### **Step 0: Setup & Dependencies**

1.  **Create Directory**: Create the main directory for the formula engine module at `apps/api/app/formula`.
2.  **Add Dependency**: Add the `lark` parsing library to the `apps/api/requirements.txt` file.
    ```
    # requirements.txt
    lark-parser
    ```
3.  **File Structure**: Create the initial empty Python files.
    ```
    apps/api/app/formula/
    ├── __init__.py
    ├── formula_routes.py           # FastAPI endpoint
    ├── formula_evaluator.py     # The AST interpreter
    ├── formula_grammar.lark     # The formula grammar
    ├── formula_functions.py     # Standard library function implementations
    ├── formula_registry.py      # The function registry
    └── formula_transformer.py   # Transforms Lark tree into a usable AST
    ```

### **Step 1: Define the Grammar**

*   **File**: `apps/api/app/formula/formula_grammar.lark`
*   **Action**: Define the context-free grammar for the formula language. This will include rules for expressions, operators, function calls, literals (strings, numbers), and our `{{variable}}` syntax. Start simple and build up.

### **Step 2: Build the Parser & Transformer**

*   **File**: `apps/api/app/formula/formula_transformer.py`
*   **Action**:
    1.  Load the `.lark` grammar file.
    2.  Create a `Transformer` class that will walk the parse tree generated by Lark.
    3.  The goal of the transformer is to convert the raw parse tree into a more structured and easy-to-use Abstract Syntax Tree (AST). For example, a `function_call` node from Lark can be transformed into a `FunctionCall` dataclass.

### **Step 3: Implement the Function Registry**

*   **File**: `apps/api/app/formula/formula_functions.py` and `formula_registry.py`
*   **Action**:
    1.  In `formula_functions.py`, implement the logic for the standard library functions (e.g., a Python function `fn_upper(text)`). These functions should be pure and only operate on their inputs.
    2.  In `formula_registry.py`, create a dictionary that maps the uppercase formula function names to the actual Python function objects (e.g., `"UPPER": fn_upper`). This makes the engine extensible.

### **Step 4: Create the Evaluator**

*   **File**: `apps/api/app/formula/formula_evaluator.py`
*   **Action**: This is the core of the engine.
    1.  Create an `Evaluator` class that takes the AST from the transformer and a data `context`.
    2.  Write a method, `evaluate()`, that recursively walks the AST.
    3.  When it encounters a `Literal` node, it returns the value.
    4.  When it encounters a `Variable` node (e.g., `{{ new_record.amount }}`), it looks up the path (`new_record.amount`) in the context dictionary.
    5.  When it encounters a `FunctionCall` node, it first evaluates the arguments, then uses the `registry` to find the correct Python function and calls it with the evaluated arguments.

### **Step 5: Expose the API Endpoint**

*   **File**: `apps/api/app/formula/formula_routes.py`
*   **Action**:
    1.  Create a new FastAPI `APIRouter`.
    2.  Define a `/evaluate` endpoint that accepts a POST request with a JSON body containing `formula_string` and `context`.
    3.  In the endpoint, orchestrate the process: `string -> parser -> transformer -> evaluator -> result`.
    4.  Return the result, ensuring to catch any syntax or runtime errors and return them in a structured error response.

### **Step 6: Testing**

*   **Action**: Rigorous testing is critical. Create tests for each component in isolation:
    *   Test the parser with valid and invalid formula strings.
    *   Test each standard library function with expected and edge-case inputs.
    *   Test the evaluator's logic for operators, variables, and nested functions.
    *   Write integration tests for the API endpoint.