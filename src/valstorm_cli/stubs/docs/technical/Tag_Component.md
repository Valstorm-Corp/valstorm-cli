# Building a TagCreatorComponent for the Tag Object

I have this app builder component that is hyper specific to build the list_filter object

/Users/jared/Documents/Code/monorepo/packages/components/AppBuilder/components/Utility/ListViewSettings
/Users/jared/Documents/Code/monorepo/packages/components/AppBuilder/components/Utility/ListViewSettings/index.ts
/Users/jared/Documents/Code/monorepo/packages/components/AppBuilder/components/Utility/ListViewSettings/ListViewSettings.component.tsx
/Users/jared/Documents/Code/monorepo/packages/components/AppBuilder/components/Utility/ListViewSettings/ListViewSettings.props.ts
/Users/jared/Documents/Code/monorepo/packages/components/AppBuilder/components/Utility/ListViewSettings/ListViewSettings.schema.ts
/Users/jared/Documents/Code/monorepo/packages/components/AppBuilder/components/Utility/ListViewSettings/README.md


Example of how tags are used can be found here
/Users/jared/Documents/Code/monorepo/packages/components/Inputs/Complex/PicklistEdit.tsx


The schema for list_filter is this

```json
{
  "properties": {
    "id": {
      "title": "Id",
      "type": "string",
      "api_name": "id",
      "custom": false
    },
    "name": {
      "title": "Name",
      "type": "string",
      "api_name": "name",
      "custom": false
    },
    "created_date": {
      "None": null,
      "date-time": "date-time",
      "default": null,
      "format": "date-time",
      "schema": null,
      "title": "Created Date",
      "type": "string",
      "api_name": "created_date",
      "custom": false
    },
    "modified_date": {
      "None": null,
      "date-time": "date-time",
      "default": null,
      "format": "date-time",
      "schema": null,
      "title": "Modified Date",
      "type": "string",
      "api_name": "modified_date",
      "custom": false
    },
    "created_by": {
      "default": null,
      "format": "lookup",
      "modify": false,
      "system": true,
      "title": "Created By",
      "type": "json",
      "schema": "user",
      "api_name": "created_by",
      "custom": false
    },
    "modified_by": {
      "default": null,
      "format": "lookup",
      "modify": false,
      "system": true,
      "title": "Modified By",
      "type": "json",
      "schema": "user",
      "api_name": "modified_by",
      "custom": false
    },
    "query": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "phi": false,
      "description": "The SQL query that controls this list view",
      "help_text": "The SQL query that controls this list view",
      "plural_name": "Queries",
      "title": "Query",
      "schema": "",
      "format": "text-area",
      "sensitive": false,
      "encrypted": false,
      "custom": false,
      "api_name": "query"
    },
    "object": {
      "type": "json",
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "title": "Object",
      "schema": "schemas",
      "format": "lookup",
      "sensitive": false,
      "encrypted": false,
      "api_name": "object",
      "custom": false
    },
    "settings": {
      "default": "{}",
      "format": "json",
      "type": "json",
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "title": "Settings",
      "api_name": "settings",
      "custom": false
    },
    "table_columns": {
      "anyOf": [
        {
          "type": "list"
        },
        {
          "type": "null"
        }
      ],
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "phi": false,
      "description": "The metadata of the columns for a table view",
      "help_text": "The metadata of the columns for a table view",
      "plural_name": "Table Columns",
      "title": "Table Columns",
      "schema": "",
      "format": "",
      "sensitive": false,
      "encrypted": false,
      "custom": false,
      "api_name": "table_columns"
    },
    "kanban_column": {
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
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "phi": false,
      "description": "The metadata of a kanban views column",
      "help_text": "The metadata of a kanban views column",
      "plural_name": "Kanban Columns",
      "title": "Kanban Column",
      "custom": false,
      "api_name": "kanban_column"
    },
    "kanban_swim_lane": {
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
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "phi": false,
      "description": "The metadata of the kanban swimlane, if any",
      "help_text": "The metadata of the kanban swimlane, if any",
      "plural_name": "Kanban Swim Lanes",
      "title": "Kanban Swim Lane",
      "custom": false,
      "api_name": "kanban_swim_lane"
    },
    "kanban_card_fields": {
      "anyOf": [
        {
          "type": "list"
        },
        {
          "type": "null"
        }
      ],
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "phi": false,
      "description": "The metadata of the fields on each kanban card",
      "help_text": "The metadata of the fields on each kanban card",
      "plural_name": "Kanban Card Fields",
      "title": "Kanban Card Fields",
      "format": "",
      "custom": false,
      "api_name": "kanban_card_fields"
    },
    "list_fields": {
      "anyOf": [
        {
          "type": "list"
        },
        {
          "type": "null"
        }
      ],
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "phi": false,
      "description": "The fields that will be present in a list view",
      "help_text": "The fields that will be present in a list view",
      "plural_name": "List Fields",
      "title": "List Fields",
      "format": "",
      "custom": false,
      "api_name": "list_fields"
    },
    "default_view": {
      "enum": [
        "list",
        "table",
        "kanban",
        "json"
      ],
      "anyOf": [
        {
          "enum": [
            "list",
            "table",
            "kanban",
            "json"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "format": "enum",
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "phi": false,
      "description": "The default view for this list filter",
      "help_text": "The default view for this list filter",
      "plural_name": "Default Views",
      "title": "Default View",
      "custom": false,
      "api_name": "default_view"
    },
    "query_mode": {
      "enum": [
        "UI Builder",
        "Custom SQL",
        "Mongo Query"
      ],
      "type": "string",
      "format": "enum",
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "phi": false,
      "description": "It dictates exactly how the frontend should render and how the backend should behave.",
      "help_text": "It dictates exactly how the frontend should render and how the backend should behave.",
      "plural_name": "Query Modes",
      "default": "Custom SQL",
      "title": "Query Mode",
      "custom": false,
      "api_name": "query_mode"
    },
    "ui_configuration": {
      "default": "{}",
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
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "phi": false,
      "description": "This will hold the entire state of the visual builder. Keeping this as a single JSON object prevents you from polluting your database schema with dozens of individual columns (like limit, offset, selected_fields) that become completely useless if the user switches to custom_sql",
      "help_text": "This will hold the entire state of the visual builder. Keeping this as a single JSON object prevents you from polluting your database schema with dozens of individual columns (like limit, offset, selected_fields) that become completely useless if the user switches to custom_sql",
      "plural_name": "Ui Configurations",
      "title": "Ui Configuration",
      "custom": false,
      "api_name": "ui_configuration"
    }
  },
  "required": [
    "id",
    "created_by",
    "modified_by",
    "name"
  ],
  "title": "List Filter",
  "type": "object",
  "id": "e14eb1ec-bc16-4b25-98ad-c2f916cffed1",
  "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
  "api_name": "list_filter",
  "all_records_standard": false,
  "description": "Used to control list views and filter their data",
  "exclusive_ownership": false,
  "git_tracking": false,
  "git_tracking_records": false,
  "icon": "FilterListIcon",
  "junction_object": false,
  "name": "List Filter",
  "ownership": false,
  "relates_to_any_object": false,
  "standard": false,
  "created_by": {
    "id": "b1b63071-b217-42c0-8202-e66fdbe3ec05",
    "schema_id": "f5e6501e-f157-4c35-9a04-f9e00db883f4",
    "schema_api_name": "user",
    "schema_title": "User",
    "name": "Valstorm Admin"
  },
  "modified_by": {
    "id": "b1b63071-b217-42c0-8202-e66fdbe3ec05",
    "schema_id": "f5e6501e-f157-4c35-9a04-f9e00db883f4",
    "schema_api_name": "user",
    "schema_title": "User",
    "name": "Valstorm Admin"
  }
}
```


I need to create a TagCreatorComponent that is hyper specific to the different types of tags that can be created. Here is the schema

```
{
  "properties": {
    "id": {
      "title": "Id",
      "type": "string",
      "api_name": "id"
    },
    "name": {
      "title": "Name",
      "type": "string",
      "api_name": "name"
    },
    "created_date": {
      "None": null,
      "date-time": "date-time",
      "default": null,
      "format": "date-time",
      "schema": null,
      "title": "Created Date",
      "type": "string",
      "api_name": "created_date"
    },
    "modified_date": {
      "None": null,
      "date-time": "date-time",
      "default": null,
      "format": "date-time",
      "schema": null,
      "title": "Modified Date",
      "type": "string",
      "api_name": "modified_date"
    },
    "created_by": {
      "default": null,
      "format": "lookup",
      "modify": false,
      "system": true,
      "title": "Created By",
      "type": "json",
      "schema": "user",
      "api_name": "created_by",
      "custom": false
    },
    "modified_by": {
      "default": null,
      "format": "lookup",
      "modify": false,
      "system": true,
      "title": "Modified By",
      "type": "json",
      "schema": "user",
      "api_name": "modified_by",
      "custom": false
    },
    "object": {
      "schema": "schemas",
      "anyOf": [
        {
          "type": "json"
        },
        {
          "type": "null"
        }
      ],
      "format": "lookup",
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "description": "",
      "help_text": "",
      "plural_name": "",
      "title": "Object",
      "sensitive": false,
      "encrypted": false,
      "custom": false,
      "api_name": "object"
    },
    "field_api_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "description": "",
      "help_text": "",
      "plural_name": "",
      "title": "Field Api Name",
      "schema": "",
      "sensitive": false,
      "encrypted": false,
      "custom": false,
      "api_name": "field_api_name"
    },
    "value": {
      "type": "string",
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "description": "",
      "help_text": "",
      "plural_name": "",
      "title": "Value",
      "schema": "",
      "sensitive": false,
      "encrypted": false,
      "custom": false,
      "api_name": "value"
    },
    "label": {
      "type": "string",
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "description": "",
      "help_text": "",
      "plural_name": "",
      "title": "Label",
      "schema": "",
      "sensitive": false,
      "encrypted": false,
      "custom": false,
      "api_name": "label"
    },
    "global": {
      "type": "boolean",
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "description": "",
      "help_text": "Turns this into a reusable tag across restricted fields",
      "plural_name": "Globals",
      "default": "false",
      "title": "Global",
      "schema": "",
      "format": "",
      "sensitive": false,
      "encrypted": false,
      "custom": false,
      "api_name": "global"
    },
    "global_list_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "description": "The name of the global list if you specify this as reusable",
      "help_text": "The name of the global list if you specify this as reusable",
      "plural_name": "Global List Names",
      "title": "Global List Name",
      "custom": false,
      "api_name": "global_list_name"
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
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "phi": false,
      "description": "Controls the background color of the tag",
      "help_text": "Controls the background color of the tag",
      "plural_name": "Colors",
      "title": "Color",
      "custom": false,
      "api_name": "color"
    },
    "order": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "phi": false,
      "description": "Setting the order will allow tags to sort based on the order",
      "help_text": "Setting the order will allow tags to sort based on the order",
      "plural_name": "Orders",
      "title": "Order",
      "format": "",
      "custom": false,
      "api_name": "order"
    },
    "dependent_field_api_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "phi": false,
      "description": "Set this if this tag should only be available based on the value of another field",
      "help_text": "Set this if this tag should only be available based on the value of another field",
      "plural_name": "Dependent Field Api Names",
      "title": "Dependent Field Api Name",
      "custom": false,
      "api_name": "dependent_field_api_name"
    },
    "dependent_values": {
      "anyOf": [
        {
          "type": "list"
        },
        {
          "type": "null"
        }
      ],
      "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
      "pii": false,
      "phi": false,
      "description": "This tag will only be available to select if one of the values in this list are present",
      "help_text": "This tag will only be available to select if one of the values in this list are present",
      "plural_name": "Dependent Values",
      "title": "Dependent Values",
      "format": "",
      "custom": false,
      "api_name": "dependent_values"
    }
  },
  "required": [
    "id",
    "name"
  ],
  "title": "Tag",
  "type": "object",
  "id": "3005c959-2a2f-415c-97ee-8e7107d7ee86",
  "app": "87b5148f-1825-4762-a179-0e2363a4e2b6",
  "description": "Used for value assignments. Useful for filtering or specifying which values can be used in drop downs AKA picklists.",
  "api_name": "tag",
  "custom": false,
  "children": {
    "lead": [
      "tag"
    ]
  },
  "all_records_standard": false,
  "exclusive_ownership": false,
  "git_tracking": false,
  "git_tracking_records": false,
  "icon": "LabelIcon",
  "junction_object": false,
  "name": "Tag",
  "ownership": false,
  "relates_to_any_object": false,
  "standard": false,
  "created_by": {
    "id": "b1b63071-b217-42c0-8202-e66fdbe3ec05",
    "schema_id": "f5e6501e-f157-4c35-9a04-f9e00db883f4",
    "schema_api_name": "user",
    "schema_title": "User",
    "name": "Valstorm Admin"
  },
  "modified_by": {
    "id": "b1b63071-b217-42c0-8202-e66fdbe3ec05",
    "schema_id": "f5e6501e-f157-4c35-9a04-f9e00db883f4",
    "schema_api_name": "user",
    "schema_title": "User",
    "name": "Valstorm Admin"
  }
}
```
the value and label fields should always be the same. Just show people value to enter.

The following fields are very special, and we will apply custom inputs to them.


## Object
- object -> if someone selects this then we must allow the field_api_name to populate with the fields from that object so they can select which field this tag belongs to. This will allow us to only show relevant tags when we are showing tags for a specific field on the frontend

## Global
- global -> if checked, we will want to set the global_list_name. We should allow the user to use any existing global_list_name (found from existing tags on the settings.tag array) or free form enter text for a new one. These aren't saved as a record in the database so pretty much it is a unique value from all global tags that exist.

## Color
- color -> this should just be a color picker that allows the user to select the background color for the tag. This will be stored as a hex code or a tailwind color value.

## Order
- order -> this should just be a number input that allows the user to specify the order for this tag. The lower the number the more to the left this tag will be shown when showing tags on a kanban. We sort drop downs and kanbans by this value

## Dependent Field
- dependent_field_api_name -> This filters the tag to only be available if another field (the dependent field) has a value that is in the dependent_values list. So if I have a tag called "Show me only if status is Nurture" I would set dependent_field_api_name to "status" and dependent_values to ["Nurture"]. Then this tag would only be available to select if the status field has the value Nurture.


## Examples

### Global - Tag list
```json
{
    "id": "d5fb3654-983f-4c03-928f-1fdd94cf0169",
    "name": "Global - Tags - Journalism",
    "object": null,
    "field_api_name": null,
    "value": "Journalism",
    "label": "Journalism",
    "global": true,
    "global_list_name": "Tags",
    "color": null,
    "order": null,
    "dependent_field_api_name": null,
    "dependent_values": null,
}
```

### Object Examples

#### Field Specific
field specific tags only show up for specific fields on a specific object.

```json
{
    "id": "656c12c8-6ea6-49d3-b77e-2a244410b2f6",
    "object": {
      "id": "efef89ad-66b4-4f09-a966-d5a8712d377d",
      "name": "Lead",
      "schema_id": "efef89ad-66b4-4f09-a966-d5a8712d377d",
      "schema_api_name": "lead",
      "schema_title": "Lead"
    },
    "field_api_name": "status",
    "name": "Lead - status - Nurture",
    "value": "Nurture",
    "label": "Nurture",
    "schema": "3005c959-2a2f-415c-97ee-8e7107d7ee86",
    "global": false,
    "global_list_name": null,
    "color": "teal",
    "order": 5,
    "dependent_field_api_name": null,
    "dependent_values": null
  }
```


#### Dependent Field Example
Dependent field tags only show up if another field has a specific value. In this example we will only show this tag if the status field has the value "Lost". This is useful for tags that only make sense in certain contexts. In this example it only makes sense to have the "Do Not Contact" tag if the lead has already been marked as "Lost". So we set the dependent_field_api_name to "status" and dependent_values to ["Lost"]. Then when we are showing tags for a lead, we will check if the lead's status is "Lost" and if it is then we will show this tag as an option to select.

```json
{
    "id": "4054f686-fca6-46d1-9f80-b2cfeb81cf15",
    "name": "Lead - status_reason - Do Not Contact",
    "created_date": "2026-02-24T13:33:49.253000Z",
    "modified_date": "2026-02-24T13:33:49.253000Z",
    "created_by": {
      "id": "b1b63071-b217-42c0-8202-e66fdbe3ec05",
      "schema_id": "f5e6501e-f157-4c35-9a04-f9e00db883f4",
      "schema_api_name": "user",
      "schema_title": "User",
      "name": "Valstorm Admin"
    },
    "modified_by": {
      "id": "b1b63071-b217-42c0-8202-e66fdbe3ec05",
      "schema_id": "f5e6501e-f157-4c35-9a04-f9e00db883f4",
      "schema_api_name": "user",
      "schema_title": "User",
      "name": "Valstorm Admin"
    },
    "object": {
      "id": "efef89ad-66b4-4f09-a966-d5a8712d377d",
      "name": "Lead",
      "schema_id": "efef89ad-66b4-4f09-a966-d5a8712d377d",
      "schema_api_name": "lead",
      "schema_title": "Lead"
    },
    "field_api_name": "status_reason",
    "value": "Do Not Contact",
    "label": "Do Not Contact",
    "global": false,
    "global_list_name": null,
    "color": "red",
    "order": 3,
    "dependent_field_api_name": "status",
    "dependent_values": [
      "Lost"
    ]
}
```