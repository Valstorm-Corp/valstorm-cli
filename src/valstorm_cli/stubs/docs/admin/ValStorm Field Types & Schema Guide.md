# ValStorm Field Types & Schema Guide

This guide provides an in-depth explanation of the various field types available in the ValStorm dynamic schema system. ValStorm uses a JSON-Schema inspired structure to define object properties, with custom extensions for business logic, UI rendering, and multi-tenancy.

## 📋 Core Field Properties

Every field definition in ValStorm can include several standard properties:

| Property      | Type      | Description                                                                     |
| :------------ | :-------- | :------------------------------------------------------------------------------ |
| `api_name`    | `string`  | The unique identifier for the field in API calls and database queries.          |
| `title`       | `string`  | The display label shown in the UI.                                              |
| `type`        | `string`  | The underlying data type (e.g., `string`, `number`, `boolean`, `json`, `list`). |
| `format`      | `string`  | Hints the UI on how to render the field (e.g., `date`, `email`, `lookup`).      |
| `anyOf`       | `array`   | Used primarily to allow null values: `[{"type": "string"}, {"type": "null"}]`.  |
| `required`    | `array`   | Defined at the **object level**, listing the `api_name` of mandatory fields.    |
| `pii` / `phi` | `boolean` | Flag for Personally Identifiable Information or Protected Health Information.   |
| `description` | `string`  | Internal documentation for developers.                                          |
| `help_text`   | `string`  | Tooltip text shown to end-users in the UI.                                      |

***

## Text & Input

### 1. Basic Text

Used for short strings like names, titles, or single-line inputs.

* **Type:** `string`
* **Format:** `null` (default)
* **Example:** `text_field_required` (no `anyOf`) or `text_field_not_required` (with `anyOf` including `null`).

### 2. Text Area

Used for multi-line text input.

* **Type:** `string`
* **Format:** `text-area`

### 3. Rich Content (HTML, Markdown, Rich Text)

Specialized formats for formatted content.

* **Type:** `string`
* **Formats:** `html`, `markdown`, `rich-text`

***

## 🔢 Numeric & Financial

### 1. Number

Standard integer or floating-point numbers.

* **Type:** `number`

### 2. Currency

Formats the number as a currency value in the UI.

* **Type:** `number`
* **Format:** `currency`

### 3. Percent

Renders the number as a percentage.

* **Type:** `number`
* **Format:** `percent`

***

## 🔘 Selection & Picklists

### 1. Enum

A fixed set of strings defined directly in the schema.

* **Type:** `string`
* **Format:** `enum`
* **Property:** `enum: ["Option A", "Option B"]`

### 2. Picklist (Standard)

A dropdown menu. ValStorm supports three variations:

* **Global:** Uses a tenant-wide shared list (e.g., `global_list_name: "Lead Source"`).
* **Restricted:** Only allows values defined in the API metadata.
* **Dependent:** Values change based on another field's selection (logic typically driven by tags).

### 3. Multi-Select (Multiple Dropdown)

Allows selecting multiple options from a list.

* **Type:** `list`
* **Format:** `multi-select`

***

## 🔗 Relationships & Lookups\`

Lookups are the "foreign keys" of ValStorm, connecting records across different collections.

### 1. Lookup

A single reference to another record.

* **Type:** `json`
* **Format:** `lookup`
* **Property:** `schema: "target_object_api_name"`

### 2. Lookup List

A reference to multiple records from a specific collection.

* **Type:** `list`
* **Format:** `lookup_list`
* **Property:** `schema: "target_object_api_name"`

### 3. Compound Lookup

A flexible reference that can point to records in *any* collection.

* **Type:** `json`
* **Format:** `compound_lookup`

***

## 📅 Date & Time

### 1. Date

A standard date (YYYY-MM-DD).

* **Type:** `string`
* **Format:** `date`

### 2. Date Time

A full timestamp.

* **Type:** `string`
* **Format:** `date-time`

### 3. Date List

An array of date strings.

* **Type:** `list`
* **Format:** `date_list`

***

## 🛠️ Specialized Types

### 1. Phone

Stores structured phone data.

* **Type:** `json`
* **Format:** `json` (handled via `type: phone` in UI)
* **Default Structure:** `{"friendly_number": "", "country_code": "", "phone_number": "", "extension": ""}`

### 2. Address

Stores geo-location and address components.

* **Type:** `object`
* **Format:** `address`

### 3. Image

Handles file uploads for images.

* **Type:** `object`
* **Format:** `image`

### 4. Boolean

A simple true/false toggle.

* **Type:** `boolean`

### 5. Color & Icon

UI-specific fields for selecting hex codes or system icons.

* **Type:** `string`
* **Formats:** `color`, `icon`

***

## 🧬 System & Advanced

### 1. Availability / User Availability

Used for scheduling and agent presence logic.

* **Type:** `json`
* **Formats:** `availability`, `user_availability`

### 2. Raw JSON / List

For storing unstructured or complex nested data that doesn't fit standard types.

* **Types:** `json`, `list`
* **Format:** `json` (for the JSON type)

## Comprehensive JSON View

Below is a showing of all of the possible field types in side a JSON object. This is mainly for inspection by developers to understand the underlying data model.

```json
{
  "app": "",
  "description": "",
  "exclusive_ownership": false,
  "junction_object": false,
  "ownership": false,
  "properties": {
    "api_name": {
      "title": "Api Name",
      "type": "string",
      "api_name": "api_name"
    },
    "text_field_not_required": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Text Field Not Requireds",
      "title": "Text Field Not Required",
      "custom": false,
      "api_name": "text_field_not_required"
    },
    "text_field_required": {
      "type": "string",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Text Field Requireds",
      "title": "Text Field Required",
      "custom": false,
      "api_name": "text_field_required"
    },
    "text_area_not_required": {
      "format": "text-area",
      "type": "string",
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Text Area Not Requireds",
      "title": "Text Area Not Required",
      "custom": false,
      "api_name": "text_area_not_required"
    },
    "text_area_required": {
      "format": "text-area",
      "type": "string",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Text Area Requireds",
      "title": "Text Area Required",
      "custom": false,
      "api_name": "text_area_required"
    },
    "picklist_global": {
      "restricted": false,
      "global": true,
      "global_list_name": "Lead Source",
      "schema": null,
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "picklist",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Picklist Globals",
      "title": "Picklist Global",
      "custom": false,
      "api_name": "picklist_global"
    },
    "picklist_restricted_to_api_values": {
      "restricted": true,
      "global": false,
      "global_list_name": null,
      "schema": null,
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "picklist",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Picklist Restricted to API Valuess",
      "title": "Picklist Restricted to API Values",
      "custom": false,
      "api_name": "picklist_restricted_to_api_values"
    },
    "picklist_dependent": {
      "restricted": false,
      "global": false,
      "global_list_name": null,
      "schema": null,
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "picklist",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "Pick list with dependencies that are generated by tags",
      "help_text": "Pick list with dependencies that are generated by tags",
      "plural_name": "Picklist Dependents",
      "title": "Picklist Dependent",
      "custom": false,
      "api_name": "picklist_dependent"
    },
    "multiple_dropdown": {
      "restricted": false,
      "global": false,
      "global_list_name": null,
      "schema": null,
      "format": "multi-select",
      "anyOf": [
        {
          "type": "list"
        },
        {
          "type": "null"
        }
      ],
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Multiple Dropdowns",
      "title": "Multiple Dropdown",
      "custom": false,
      "api_name": "multiple_dropdown"
    },
    "enum_field": {
      "enum": [
        "One",
        "Two",
        "Three"
      ],
      "anyOf": [
        {
          "enum": [
            "One",
            "Two",
            "Three"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "enum",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Enum Fields",
      "title": "Enum Field",
      "custom": false,
      "api_name": "enum_field"
    },
    "phone": {
      "anyOf": [
        {
          "type": "phone"
        },
        {
          "type": "null"
        }
      ],
      "format": "json",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "PHones",
      "default": {
        "friendly_number": "",
        "country_code": "",
        "phone_number": "",
        "extension": ""
      },
      "title": "PHone",
      "custom": false,
      "api_name": "phone"
    },
    "email": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "email",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Emails",
      "title": "Email",
      "custom": false,
      "api_name": "email"
    },
    "number": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Numbers",
      "title": "Number",
      "format": "",
      "custom": false,
      "api_name": "number"
    },
    "currency": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "format": "currency",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Currencys",
      "title": "Currency",
      "custom": false,
      "api_name": "currency"
    },
    "percent": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "format": "percent",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Percents",
      "title": "Percent",
      "custom": false,
      "api_name": "percent"
    },
    "image": {
      "anyOf": [
        {
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "format": "image",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Images",
      "title": "Image",
      "custom": false,
      "api_name": "image"
    },
    "address": {
      "anyOf": [
        {
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "format": "address",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Addresss",
      "title": "Address",
      "custom": false,
      "api_name": "address"
    },
    "date": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "date",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Dates",
      "title": "Date",
      "custom": false,
      "api_name": "date"
    },
    "date_time": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "date-time",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Date Times",
      "title": "Date Time",
      "custom": false,
      "api_name": "date_time"
    },
    "boolean": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Booleans",
      "title": "Boolean",
      "format": "",
      "custom": false,
      "api_name": "boolean"
    },
    "json": {
      "default": null,
      "format": "json",
      "type": "json",
      "anyOf": [
        {
          "type": "json"
        },
        {
          "type": "null"
        }
      ],
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "JSONs",
      "title": "JSON",
      "custom": false,
      "api_name": "json"
    },
    "list": {
      "anyOf": [
        {
          "type": "list"
        },
        {
          "type": "null"
        }
      ],
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Lists",
      "title": "List",
      "format": "",
      "custom": false,
      "api_name": "list"
    },
    "link": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "link",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Links",
      "title": "Link",
      "custom": false,
      "api_name": "link"
    },
    "html": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "html",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Htmls",
      "title": "Html",
      "custom": false,
      "api_name": "html"
    },
    "rich_text": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "rich-text",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Rich Texts",
      "title": "Rich Text",
      "custom": false,
      "api_name": "rich_text"
    },
    "markdown": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "markdown",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Markdowns",
      "title": "Markdown",
      "custom": false,
      "api_name": "markdown"
    },
    "availability": {
      "anyOf": [
        {
          "type": "json"
        },
        {
          "type": "null"
        }
      ],
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Availabilitys",
      "title": "Availability",
      "format": "availability",
      "custom": false,
      "api_name": "availability"
    },
    "user_availability": {
      "anyOf": [
        {
          "type": "json"
        },
        {
          "type": "null"
        }
      ],
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "User Availabilitys",
      "title": "User Availability",
      "format": "user_availability",
      "custom": false,
      "api_name": "user_availability"
    },
    "color": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "color",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Colors",
      "title": "Color",
      "custom": false,
      "api_name": "color"
    },
    "icon": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "icon",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Icons",
      "title": "Icon",
      "custom": false,
      "api_name": "icon"
    },
    "date_list": {
      "anyOf": [
        {
          "type": "list"
        },
        {
          "type": "null"
        }
      ],
      "format": "date_list",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Date Lists",
      "title": "Date List",
      "custom": false,
      "api_name": "date_list"
    },
    "lookup": {
      "anyOf": [
        {
          "type": "json"
        },
        {
          "type": "null"
        }
      ],
      "format": "lookup",
      "schema": "object_api_name",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Lookups",
      "title": "Lookup",
      "custom": false,
      "api_name": "lookup"
    },
    "lookup_list": {
      "anyOf": [
        {
          "type": "list"
        },
        {
          "type": "null"
        }
      ],
      "format": "lookup_list",
      "schema": "object_api_name",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Lookup Lists",
      "title": "Lookup List",
      "custom": false,
      "api_name": "lookup_list"
    },
    "compound_lookup": {
      "anyOf": [
        {
          "type": "json"
        },
        {
          "type": "null"
        }
      ],
      "format": "compound_lookup",
      "app": "",
      "pii": false,
      "phi": false,
      "description": "",
      "help_text": "",
      "plural_name": "Compound Lookups",
      "title": "Compound Lookup",
      "custom": false,
      "api_name": "compound_lookup"
    }
  },
  "relates_to_any_object": false,
  "required": [
    "text_field_required",
    "text_area_required",
    "api_name"
  ],
  "title": "Testing",
  "type": "object",
  "id": "a037f889-49fb-458b-9872-33b33c9b4e0b",
  "api_name": "testing",
  "custom": false
}
```